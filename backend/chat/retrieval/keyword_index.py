import logging
import re

from sqlalchemy import text

from chat.models import RetrievedDocument, SearchResult
from chat.retrieval.base import BaseIndex
from database.connection import session_context

logger = logging.getLogger(__name__)

# Maximum rows to insert per document to prevent memory/performance issues
_MAX_KEYWORD_ROWS_PER_DOC = 5000


class KeywordIndex(BaseIndex):
    def __init__(self):
        pass

    @property
    def name(self) -> str:
        return "keyword_index"

    def index_document(self, document_id: str, title: str = "", summary: str = "",
                       keywords: list[str] = None, **metadata) -> None:
        content = metadata.get("content", "")
        document_name = metadata.get("document_name", "")
        if not content:
            return

        # Combine title, summary, and content for keyword extraction
        # Title and summary are highly relevant and should be weighted
        text_to_index = ""
        if title:
            text_to_index += title + "\n"
        if summary:
            text_to_index += summary + "\n"
        text_to_index += content

        try:
            import jieba
        except ImportError:
            jieba = None

        words: set[str] = set()
        for match in re.finditer(r'\b[a-zA-Z]{4,}\b', text_to_index):
            words.add(match.group().lower())
        if jieba:
            for word in jieba.cut(text_to_index):
                if len(word) >= 2:
                    words.add(word)

        rows = []
        total_rows = 0
        for word in words:
            if total_rows >= _MAX_KEYWORD_ROWS_PER_DOC:
                logger.warning(
                    "KeywordIndex: reached max rows (%d) for document %s, "
                    "truncating index.",
                    _MAX_KEYWORD_ROWS_PER_DOC, document_id
                )
                break
            count = 0
            for match in re.finditer(re.escape(word), text_to_index, re.IGNORECASE):
                if count >= 50:
                    break
                pos = match.start()
                snippet = text_to_index[max(0, pos - 50):pos + 50]
                rows.append({
                    "word": word,
                    "doc_id": document_id,
                    "doc_name": document_name,
                    "snippet": snippet,
                    "pos": pos
                })
                count += 1
                total_rows += 1

        with session_context() as session:
            session.execute(text(
                "DELETE FROM keyword_occurrences WHERE document_id = :doc_id"
            ), {"doc_id": document_id})

            if rows:
                session.execute(text("""
                    INSERT INTO keyword_occurrences
                    (keyword, document_id, document_name, context_snippet, position)
                    VALUES (:word, :doc_id, :doc_name, :snippet, :pos)
                """), rows)

    async def search(self, query: str, top_k: int = 20,
              filters: dict | None = None, collection_ids: list[str] | None = None) -> SearchResult:
        # Extract keywords using the same logic as indexing
        words: set[str] = set()
        for match in re.finditer(r'\b[a-zA-Z]{4,}\b', query):
            words.add(match.group().lower())
        try:
            import jieba
            for word in jieba.cut(query):
                if len(word) >= 2:
                    words.add(word)
        except ImportError:
            pass

        keywords = list(words)
        if not keywords:
            return SearchResult(
                documents=[],
                search_type="keyword",
                total_found=0
            )

        # Build parameterized IN clause for cross-database compatibility
        placeholders = ", ".join(f":kw{i}" for i in range(len(keywords)))
        params: dict = {f"kw{i}": kw for i, kw in enumerate(keywords)}
        params["top_k"] = top_k

        with session_context() as session:
            sql = f"""
                SELECT ko.document_id, d.name as document_name,
                       COUNT(DISTINCT ko.keyword) as match_count,
                       STRING_AGG(DISTINCT ko.context_snippet, ' | ') as snippets
                FROM keyword_occurrences ko
                JOIN documents d ON ko.document_id = d.id
                WHERE ko.keyword IN ({placeholders})
                  AND d.status = 'indexed'
            """

            if collection_ids:
                col_placeholders = ", ".join(f":cid{i}" for i in range(len(collection_ids)))
                sql += f" AND d.collection_id IN ({col_placeholders})"
                for i, cid in enumerate(collection_ids):
                    params[f"cid{i}"] = cid

            sql += """
                GROUP BY ko.document_id, d.name
                ORDER BY match_count DESC
                LIMIT :top_k
            """

            result = session.execute(text(sql), params)

            documents = []
            for row in result:
                documents.append(RetrievedDocument(
                    document_id=row[0],
                    document_name=row[1] or "",
                    document_uri="",
                    content=f"匹配关键词数: {row[2]}\n片段: {(row[3] or '')[:500]}",
                    relevance_score=min(row[2] / len(keywords), 1.0),
                    source_type="keyword"
                ))

            return SearchResult(
                documents=documents,
                search_type="keyword",
                total_found=len(documents)
            )
