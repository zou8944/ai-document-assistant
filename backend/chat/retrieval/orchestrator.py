import logging

from chat.models import CollectionInfo, QueryIntent, RetrievedDocument, SearchResult
from chat.retrieval.chunk_index import ChunkIndex
from chat.retrieval.document_index import DocumentIndex
from chat.retrieval.keyword_index import KeywordIndex

logger = logging.getLogger(__name__)


class RetrievalOrchestrator:
    def __init__(self, document_index: DocumentIndex, chunk_index: ChunkIndex, keyword_index: KeywordIndex):
        self.document_index = document_index
        self.chunk_index = chunk_index
        self.keyword_index = keyword_index

    async def retrieve(self, intent: QueryIntent, queries: list[str],
                       collection_ids: list[str] = None,
                       top_k: int = 10) -> tuple[SearchResult, list[CollectionInfo]]:
        if not queries:
            logger.warning("RetrievalOrchestrator: empty queries list, cannot retrieve.")
            return SearchResult(documents=[], search_type="", total_found=0), []

        all_documents = []
        search_type_parts = []

        for query in queries:
            if intent == QueryIntent.DIRECT_ANSWER:
                result = await self.chunk_index.search(query, top_k=5, collection_ids=collection_ids)
                all_documents.extend(result.documents)
                search_type_parts.append("chunk_vector")

            elif intent == QueryIntent.LOCATE:
                kw_result = await self.keyword_index.search(query, top_k=10)
                doc_result = await self.document_index.search(query, top_k=5)
                all_documents.extend(kw_result.documents)
                all_documents.extend(doc_result.documents)
                search_type_parts.append("keyword+document")

            elif intent == QueryIntent.RECOMMEND:
                result = await self.document_index.get_all_documents(collection_ids)
                all_documents.extend(result.documents)
                search_type_parts.append("document_all")
                break

            elif intent == QueryIntent.SUMMARIZE:
                result = await self.chunk_index.search(query, top_k=10, collection_ids=collection_ids)
                all_documents.extend(result.documents)
                search_type_parts.append("chunk_vector")

            elif intent == QueryIntent.COMPARE:
                result = await self.chunk_index.search(query, top_k=5, collection_ids=collection_ids)
                all_documents.extend(result.documents)
                search_type_parts.append("chunk_vector")

            elif intent == QueryIntent.PROCEDURE:
                result = await self.chunk_index.search(query, top_k=8, collection_ids=collection_ids)
                all_documents.extend(result.documents)
                search_type_parts.append("chunk_vector")

            elif intent == QueryIntent.SYNTHESIZE:
                result = await self.chunk_index.search(query, top_k=15, collection_ids=collection_ids)
                all_documents.extend(result.documents)
                search_type_parts.append("chunk_vector_broad")

            elif intent == QueryIntent.ANALYZE:
                chunk_result = await self.chunk_index.search(query, top_k=10, collection_ids=collection_ids)
                doc_result = await self.document_index.search(query, top_k=5)
                all_documents.extend(chunk_result.documents)
                all_documents.extend(doc_result.documents)
                search_type_parts.append("chunk_vector+document")

        # Deduplicate by document_id + chunk_index, keeping the highest relevance score
        best_docs: dict[str, RetrievedDocument] = {}
        for doc in all_documents:
            key = f"{doc.document_id}:{doc.chunk_index or 0}"
            if key not in best_docs or doc.relevance_score > best_docs[key].relevance_score:
                best_docs[key] = doc

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
