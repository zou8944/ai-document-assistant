import asyncio
import logging

from chat.models import CollectionInfo, QueryIntent, RetrievedDocument, SearchResult
from chat.retrieval.chunk_index import ChunkIndex
from chat.retrieval.document_index import DocumentIndex
from chat.retrieval.keyword_index import KeywordIndex

logger = logging.getLogger(__name__)


class RetrievalOrchestrator:
    def __init__(
        self,
        document_index: DocumentIndex,
        chunk_index: ChunkIndex,
        keyword_index: KeywordIndex,
    ):
        self.document_index = document_index
        self.chunk_index = chunk_index
        self.keyword_index = keyword_index

    async def retrieve(self, intent: QueryIntent, queries: list[str],
                       collection_ids: list[str] | None = None,
                       top_k: int = 25,
                       core_keywords: list[str] | None = None) -> tuple[SearchResult, list[CollectionInfo]]:
        if not queries:
            logger.warning("RetrievalOrchestrator: empty queries list, cannot retrieve.")
            return SearchResult(documents=[], search_type="", total_found=0), []

        source_weights = {
            "chunk_vector": 1.0,
            "keyword": 0.8,
            "document_index": 0.5,
        }

        all_documents = []
        search_type_parts = []

        # Chunk top-k per intent
        chunk_top_k_map = {
            QueryIntent.DIRECT_ANSWER: 5,
            QueryIntent.LOCATE: 5,
            QueryIntent.SUMMARIZE: 10,
            QueryIntent.COMPARE: 5,
            QueryIntent.PROCEDURE: 8,
            QueryIntent.SYNTHESIZE: 15,
            QueryIntent.ANALYZE: 10,
        }

        # Run all queries through all three indexes in parallel
        tasks = []
        for query in queries:
            if intent == QueryIntent.RECOMMEND:
                result = await self.document_index.get_all_documents(collection_ids)
                all_documents.extend(result.documents)
                search_type_parts.append("document_all")
                break

            chunk_top_k = chunk_top_k_map.get(intent, 5)

            tasks.append(self.chunk_index.search(query, top_k=chunk_top_k, collection_ids=collection_ids))
            tasks.append(self.document_index.search(query, top_k=15, collection_ids=collection_ids))
            tasks.append(self.keyword_index.search(query, top_k=30, collection_ids=collection_ids))
            search_type_parts.append("hybrid")

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.warning(f"RetrievalOrchestrator: search task failed: {result}")
                    continue
                all_documents.extend(result.documents)

        # Apply source weighting and deduplicate by (document_id, chunk_index)
        best_docs: dict[str, RetrievedDocument] = {}
        for doc in all_documents:
            weight = source_weights.get(doc.source_type, 1.0)
            weighted_score = doc.relevance_score * weight
            key = f"{doc.document_id}:{doc.chunk_index if doc.chunk_index is not None else 'full'}"
            if key not in best_docs or weighted_score > best_docs[key].relevance_score:
                best_docs[key] = RetrievedDocument(
                    document_id=doc.document_id,
                    document_name=doc.document_name,
                    document_uri=doc.document_uri,
                    content=doc.content,
                    relevance_score=weighted_score,
                    source_type=doc.source_type,
                    chunk_index=doc.chunk_index
                )

        unique_docs = sorted(best_docs.values(), key=lambda d: d.relevance_score, reverse=True)

        search_result = SearchResult(
            documents=unique_docs[:top_k],
            search_type="+".join(set(search_type_parts)),
            total_found=len(unique_docs)
        )

        collection_infos = []
        if collection_ids:
            for cid in collection_ids:
                col_info = await self.document_index.get_collection_info(cid)
                if col_info:
                    collection_infos.append(col_info)

        return search_result, collection_infos

    async def fetch_collection_overviews(self, collection_ids: list[str] | None = None) -> list[CollectionInfo]:
        """Lightweight overview for chitchat/meta paths: no document search, just collection metadata."""
        if not collection_ids:
            return []
        collection_infos = []
        for cid in collection_ids:
            col_info = await self.document_index.get_collection_info(cid)
            if col_info:
                collection_infos.append(col_info)
        return collection_infos
