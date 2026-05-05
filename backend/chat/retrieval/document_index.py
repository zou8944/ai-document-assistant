import json
import logging

from sqlalchemy import text

from chat.models import CollectionInfo, RetrievedDocument, SearchResult
from chat.retrieval.base import BaseIndex
from database.connection import session_context

logger = logging.getLogger(__name__)


class DocumentIndex(BaseIndex):
    def __init__(self):
        pass

    @property
    def name(self) -> str:
        return "document_index"

    def _escape_wildcard(self, query: str) -> str:
        return query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def index_document(self, document_id: str, title: str = "", summary: str = "",
                       keywords: list[str] = None, **metadata) -> None:
        """Update existing documents table with search-related fields."""
        from sqlalchemy import text

        # Build parameterised update using a whitelist of known columns
        set_clauses: list[str] = []
        params: dict = {"doc_id": document_id}

        if keywords is not None:
            set_clauses.append("keywords = :keywords")
            params["keywords"] = json.dumps(keywords)
        if "total_tokens" in metadata and metadata["total_tokens"] is not None:
            set_clauses.append("total_tokens = :tokens")
            params["tokens"] = metadata["total_tokens"]
        if "category" in metadata and metadata["category"] is not None:
            set_clauses.append("category = :category")
            params["category"] = metadata["category"]

        if not set_clauses:
            return

        sql = f"UPDATE documents SET {', '.join(set_clauses)} WHERE id = :doc_id"
        with session_context() as session:
            result = session.execute(text(sql), params)
            if result.rowcount == 0:
                logger.warning(
                    "DocumentIndex.index_document: no document found with id=%s", document_id
                )

    async def search(self, query: str, top_k: int = 10,
               filters: dict = None) -> SearchResult:
        safe_query = self._escape_wildcard(query)
        pattern = f"%{safe_query}%"

        with session_context() as session:
            sql = """
                SELECT id, name, summary, keywords, uri
                FROM documents
                WHERE status = 'indexed'
                  AND (name ILIKE :query ESCAPE '\\' OR summary ILIKE :query ESCAPE '\\')
            """
            params: dict = {"query": pattern, "top_k": top_k}

            if filters and filters.get("collection_id"):
                sql += " AND collection_id = :col_id"
                params["col_id"] = filters["collection_id"]

            sql += " ORDER BY name LIMIT :top_k"

            result = session.execute(text(sql), params)

            documents = []
            for row in result:
                documents.append(RetrievedDocument(
                    document_id=row[0],
                    document_name=row[1],
                    document_uri=row[4] or "",
                    content=f"{row[1]}\n{row[2] or ''}",
                    relevance_score=0.8,
                    source_type="document_index"
                ))

            return SearchResult(
                documents=documents,
                search_type="document_index",
                total_found=len(documents)
            )

    async def get_all_documents(self, collection_ids: list[str] = None,
                          limit: int = 1000) -> SearchResult:
        with session_context() as session:
            sql = """
                SELECT id, name, summary, keywords, total_tokens, uri
                FROM documents
                WHERE status = 'indexed'
            """
            params: dict = {"limit": limit}
            if collection_ids:
                placeholders = ", ".join(f":cid{i}" for i in range(len(collection_ids)))
                sql += f" AND collection_id IN ({placeholders})"
                for i, cid in enumerate(collection_ids):
                    params[f"cid{i}"] = cid
            sql += " ORDER BY name LIMIT :limit"

            result = session.execute(text(sql), params)
            documents = []
            for row in result:
                kw = json.loads(row[3]) if row[3] else []
                documents.append(RetrievedDocument(
                    document_id=row[0],
                    document_name=row[1],
                    document_uri=row[5] or "",
                    content=f"标题: {row[1]}\n摘要: {row[2] or ''}\n关键词: {', '.join(kw)}",
                    relevance_score=1.0,
                    source_type="document_index"
                ))
            return SearchResult(
                documents=documents,
                search_type="document_index_all",
                total_found=len(documents)
            )

    async def get_collection_info(self, collection_id: str) -> CollectionInfo | None:
        with session_context() as session:
            result = session.execute(text("""
                SELECT id, name, description, readme_content,
                       categories_json, document_count
                FROM collections WHERE id = :cid
            """), {"cid": collection_id})
            row = result.fetchone()
            if not row:
                return None

            # Sum total_tokens from documents in this collection
            total_tokens_result = session.execute(text("""
                SELECT COALESCE(SUM(total_tokens), 0)
                FROM documents
                WHERE collection_id = :cid AND status = 'indexed'
            """), {"cid": collection_id})
            total_tokens = total_tokens_result.scalar() or 0

            return CollectionInfo(
                collection_id=row[0],
                name=row[1],
                description=row[2] or "",
                readme_content=row[3] or "",
                categories=json.loads(row[4]) if row[4] else [],
                document_count=row[5] or 0,
                total_tokens=total_tokens
            )

    async def get_all_collections(self) -> list[CollectionInfo]:
        with session_context() as session:
            result = session.execute(text("""
                SELECT id, name, description, readme_content,
                       categories_json, document_count
                FROM collections
                ORDER BY name
            """))
            collections = []
            for row in result:
                collections.append(CollectionInfo(
                    collection_id=row[0],
                    name=row[1],
                    description=row[2] or "",
                    readme_content=row[3] or "",
                    categories=json.loads(row[4]) if row[4] else [],
                    document_count=row[5] or 0,
                    total_tokens=0
                ))
            return collections
