"""
Three-tier document retrieval strategy.
Tier 1: Full injection (small collections)
Tier 2: Summary filtering + full text injection (medium collections)
Tier 3: Vector search (large collections)
"""

import json
import logging
from dataclasses import dataclass
from enum import Enum

from models.rag import CollectionSummary, DocChunk
from models.responses import SourceReference
from repository.document import DocumentRepository
from services.llm_service import LLMService
from vector_store.chroma_client import ChromaManager

logger = logging.getLogger(__name__)

CHARS_PER_TOKEN = 4


class RetrievalTier(Enum):
    FULL_INJECTION = "full_injection"
    SUMMARY_FILTER = "summary_filter"
    VECTOR_SEARCH = "vector_search"


@dataclass
class RetrievalResult:
    doc_chunks: list[DocChunk]
    sources: list[SourceReference]
    tier: RetrievalTier


class DocumentRetrievalService:
    def __init__(self, config, llm_service: LLMService, document_repo: DocumentRepository, chroma_manager: ChromaManager):
        self.config = config
        self.llm_service = llm_service
        self.document_repo = document_repo
        self.chroma_manager = chroma_manager
        self.retrieval_config = config.retrieval

    def _estimate_tokens(self, text: str) -> int:
        return len(text) // CHARS_PER_TOKEN

    def _select_tier(self, total_doc_chars: int, total_summary_chars: int) -> RetrievalTier:
        total_doc_tokens = total_doc_chars // CHARS_PER_TOKEN
        total_summary_tokens = total_summary_chars // CHARS_PER_TOKEN
        if total_doc_tokens <= self.retrieval_config.tier1_max_tokens:
            return RetrievalTier.FULL_INJECTION
        elif total_summary_tokens <= self.retrieval_config.tier2_max_summary_tokens:
            return RetrievalTier.SUMMARY_FILTER
        else:
            return RetrievalTier.VECTOR_SEARCH

    async def retrieve(
        self,
        collection_ids: list[str],
        user_query: str,
        collection_summaries: list[CollectionSummary],
    ) -> RetrievalResult:
        all_docs = []
        for cid in collection_ids:
            docs = self.document_repo.get_by_collection(cid, exclude_statuses=["not_found"])
            all_docs.extend(docs)

        total_doc_chars = sum(len(d.content or "") for d in all_docs)
        total_summary_chars = sum(len(d.summary or "") for d in all_docs)

        tier = self._select_tier(total_doc_chars, total_summary_chars)
        logger.info(
            f"Selected retrieval tier: {tier.value} "
            f"(doc_tokens={total_doc_chars // CHARS_PER_TOKEN}, "
            f"summary_tokens={total_summary_chars // CHARS_PER_TOKEN})"
        )

        if tier == RetrievalTier.FULL_INJECTION:
            return self._tier1_full_injection(all_docs, collection_summaries)
        elif tier == RetrievalTier.SUMMARY_FILTER:
            return await self._tier2_summary_filter(all_docs, collection_summaries, user_query)
        else:
            return await self._tier3_vector_search(collection_ids, user_query, collection_summaries)

    def _tier1_full_injection(self, docs, collection_summaries) -> RetrievalResult:
        doc_chunks = []
        sources = []
        for doc in docs:
            if not doc.content:
                continue
            col_name = doc.collection_id or "Unknown"
            doc_chunks.append(DocChunk(
                doc_name=doc.name or "Unknown",
                collection_name=col_name,
                content=doc.content,
            ))
            sources.append(SourceReference(
                document_id=doc.id or "",
                document_name=doc.name or "Unknown",
                document_uri=doc.uri or "",
                chunk_index=0,
                content_preview=doc.content[:100] + "..." if len(doc.content) > 100 else doc.content,
                relevance_score=1.0,
            ))
        return RetrievalResult(doc_chunks=doc_chunks, sources=sources, tier=RetrievalTier.FULL_INJECTION)

    async def _tier2_summary_filter(self, docs, collection_summaries, query: str) -> RetrievalResult:
        summaries_block_parts = []
        valid_docs = []
        for i, doc in enumerate(docs):
            if not doc.content:
                continue
            summary_text = doc.summary if doc.summary else (doc.content[:200] + "..." if len(doc.content) > 200 else doc.content)
            summaries_block_parts.append(f"[{len(valid_docs) + 1}] {doc.name}: {summary_text}")
            valid_docs.append(doc)

        summaries_block = "\n".join(summaries_block_parts)

        try:
            indices = await self.llm_service.filter_by_summaries(query, summaries_block)
        except Exception as e:
            logger.warning(f"Summary filter failed, falling back to vector search: {e}")
            return await self._tier3_vector_search(
                list({d.collection_id for d in valid_docs if d.collection_id}), query, collection_summaries
            )

        if not indices:
            logger.info("Summary filter returned no matches, falling back to vector search")
            return await self._tier3_vector_search(
                list({d.collection_id for d in valid_docs if d.collection_id}), query, collection_summaries
            )

        selected_docs = []
        max_tokens = self.retrieval_config.tier2_max_full_tokens
        current_tokens = 0
        for idx in indices:
            if 1 <= idx <= len(valid_docs):
                doc = valid_docs[idx - 1]
                doc_tokens = self._estimate_tokens(doc.content or "")
                if current_tokens + doc_tokens > max_tokens:
                    break
                selected_docs.append(doc)
                current_tokens += doc_tokens

        doc_chunks = []
        sources = []
        for doc in selected_docs:
            col_name = doc.collection_id or "Unknown"
            doc_chunks.append(DocChunk(
                doc_name=doc.name or "Unknown",
                collection_name=col_name,
                content=doc.content,
            ))
            sources.append(SourceReference(
                document_id=doc.id or "",
                document_name=doc.name or "Unknown",
                document_uri=doc.uri or "",
                chunk_index=0,
                content_preview=doc.content[:100] + "..." if len(doc.content) > 100 else doc.content,
                relevance_score=1.0,
            ))
        return RetrievalResult(doc_chunks=doc_chunks, sources=sources, tier=RetrievalTier.SUMMARY_FILTER)

    async def _tier3_vector_search(
        self, collection_ids: list[str], query: str, collection_summaries: list[CollectionSummary]
    ) -> RetrievalResult:
        all_results = []
        score_threshold = 0.4
        top_k = 5

        query_embedding = await self.llm_service.embed_query(query)
        for collection_id in collection_ids:
            results = await self.chroma_manager.search_similar(
                collection_name=collection_id,
                query_embedding=query_embedding,
                limit=top_k,
                score_threshold=score_threshold,
            )
            for result in results:
                result["collection_id"] = collection_id
            all_results.extend(results)

        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        all_results = all_results[: top_k * 2]

        doc_chunks = []
        sources = []
        for doc in all_results:
            doc_name = doc.get("document_name", "Unknown")
            content = doc.get("content", "")
            collection_id = doc.get("collection_id", "unknown")
            collection_name = next(
                (col.name for col in collection_summaries if col.name == collection_id), collection_id
            )
            doc_chunks.append(DocChunk(doc_name=doc_name, collection_name=collection_name, content=content))
            sources.append(SourceReference(
                document_id=doc.get("document_id", ""),
                document_name=doc_name,
                document_uri=doc.get("document_uri", ""),
                chunk_index=doc.get("chunk_index", 0),
                content_preview=content[:100] + "..." if len(content) > 100 else content,
                relevance_score=doc.get("score", 0.0),
            ))
        return RetrievalResult(doc_chunks=doc_chunks, sources=sources, tier=RetrievalTier.VECTOR_SEARCH)
