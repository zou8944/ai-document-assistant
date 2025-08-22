"""
Query service for RAG-based document questioning with streaming support.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any, Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from config import get_config
from models.responses import SourceInfo
from models.streaming import ContentChunk, DoneChunk, ErrorChunk, ProgressChunk, SourcesChunk
from rag.prompt_templates import format_sources, get_rag_prompt
from vector_store.chroma_client import ChromaManager

logger = logging.getLogger(__name__)


class QueryResult:
    """Result object for query operations"""

    def __init__(self, answer: str, sources: list[SourceInfo], confidence: float, question: str):
        self.answer = answer
        self.sources = sources
        self.confidence = confidence
        self.question = question


class DocumentRetriever:
    """Custom retriever that wraps ChromaDB operations"""

    def __init__(self, chroma_manager: ChromaManager, collection_name: str,
                 embeddings, top_k: int = 5):
        self.chroma_manager = chroma_manager
        self.collection_name = collection_name
        self.embeddings = embeddings
        self.top_k = top_k

    async def retrieve_documents(self, query: str) -> list[dict[str, Any]]:
        """Retrieve relevant documents for a query"""
        # Generate query embedding
        query_embedding = await self.embeddings.aembed_query(query)

        # Search similar documents
        results = await self.chroma_manager.search_similar(
            collection_name=self.collection_name,
            query_embedding=query_embedding,
            limit=self.top_k,
            score_threshold=0.3
        )

        return results


class QueryService:
    """
    Service for handling document queries with both synchronous and streaming responses.
    """

    def __init__(self, config=None):
        """Initialize query service"""
        self.config = config or get_config()

        # Initialize ChromaDB manager (shared across retrievers)
        from vector_store.chroma_client import create_chroma_manager
        self.chroma_manager = create_chroma_manager(self.config)

        # Initialize embeddings
        embeddings_kwargs = self.config.get_openai_embeddings_kwargs()
        self.embeddings = OpenAIEmbeddings(**embeddings_kwargs)

        # Initialize LLM for answer generation
        chat_kwargs = self.config.get_openai_chat_kwargs()
        self.llm = ChatOpenAI(**chat_kwargs)

        # Initialize streaming LLM
        self.streaming_llm = ChatOpenAI(**{**chat_kwargs, "streaming": True})

        # Get prompt template
        self.prompt = get_rag_prompt()

        # Cache for active retrievers by collection
        self._retrievers: dict[str, DocumentRetriever] = {}

        logger.info("QueryService initialized successfully")

    def _get_retriever(self, collection_name: str) -> DocumentRetriever:
        """Get or create a retriever for the specified collection"""
        if collection_name not in self._retrievers:
            self._retrievers[collection_name] = DocumentRetriever(
                chroma_manager=self.chroma_manager,
                collection_name=collection_name,
                embeddings=self.embeddings,
                top_k=5
            )
        return self._retrievers[collection_name]

    def _format_context(self, documents: list[dict[str, Any]]) -> str:
        """Format retrieved documents as context for the LLM"""
        if not documents:
            return "未找到相关文档。"

        context_parts = []
        for i, doc in enumerate(documents, 1):
            source = doc.get('source', 'Unknown')
            content = doc.get('content', '')

            context_part = f"[文档 {i}] 来源: {source}\n内容: {content}"
            context_parts.append(context_part)

        return "\n\n".join(context_parts)

    def _format_sources(self, documents: list[dict[str, Any]]) -> list[SourceInfo]:
        """Format documents as SourceInfo objects"""
        sources = []
        for doc in documents:
            source_info = SourceInfo(
                source=doc.get('source', 'Unknown'),
                content_preview=(doc.get('content', '')[:200] + "..."
                               if len(doc.get('content', '')) > 200
                               else doc.get('content', '')),
                score=doc.get('score', 0),
                start_index=doc.get('start_index', 0)
            )
            sources.append(source_info)
        return sources

    async def check_collection_exists(self, collection_name: str) -> bool:
        """Check if a collection exists in the vector store"""
        try:
            info = await self.chroma_manager.get_collection_info(collection_name)
            return info is not None
        except Exception:
            return False

    async def query_documents(self, question: str, collection_name: str = "documents") -> QueryResult:
        """
        Perform synchronous query and return complete result.

        Args:
            question: User question
            collection_name: Collection to query

        Returns:
            QueryResult with answer and sources
        """
        logger.info(f"Processing query for collection '{collection_name}': {question}")

        # Check if collection exists
        if not await self.check_collection_exists(collection_name):
            return QueryResult(
                answer=f"Collection '{collection_name}' not found. Please process documents first.",
                sources=[],
                confidence=0.0,
                question=question
            )

        # Retrieve relevant documents
        retriever = self._get_retriever(collection_name)
        relevant_docs = await retriever.retrieve_documents(question)

        if not relevant_docs:
            return QueryResult(
                answer="抱歉，我在提供的文档中没有找到与您的问题相关的信息。请确认您的问题是否在文档范围内，或者尝试用不同的方式提问。",
                sources=[],
                confidence=0.0,
                question=question
            )

        # Format context for LLM
        context = self._format_context(relevant_docs)

        # Generate answer using LLM
        chain = self.prompt | self.llm | StrOutputParser()
        answer = await chain.ainvoke({
            "context": context,
            "question": question
        })

        # Calculate confidence based on retrieval scores
        avg_score = sum(doc.get('score', 0) for doc in relevant_docs) / len(relevant_docs)
        confidence = min(avg_score * 2, 1.0)  # Scale to 0-1 range

        # Format sources
        sources = self._format_sources(relevant_docs)

        # Add formatted source citations to answer
        source_citation = format_sources([s.model_dump() for s in sources])
        if source_citation:
            answer += source_citation

        logger.info(f"Successfully generated answer with {len(relevant_docs)} sources")

        return QueryResult(
            answer=answer,
            sources=sources,
            confidence=confidence,
            question=question
        )

    async def query_documents_stream(self, question: str,
                                   collection_name: str = "documents") -> AsyncGenerator[Any, None]:
        """
        Perform streaming query and yield response chunks.

        Args:
            question: User question
            collection_name: Collection to query

        Yields:
            Stream chunks (ProgressChunk, ContentChunk, SourcesChunk, DoneChunk, ErrorChunk)
        """
        logger.info(f"Processing streaming query for collection '{collection_name}': {question}")

        # Phase 1: Check collection
        yield ProgressChunk(message="检查文档集合...")

        if not await self.check_collection_exists(collection_name):
            yield ErrorChunk(error=f"Collection '{collection_name}' not found. Please process documents first.")
            return

        # Phase 2: Retrieve documents
        yield ProgressChunk(message="正在检索相关文档...")

        retriever = self._get_retriever(collection_name)
        relevant_docs = await retriever.retrieve_documents(question)

        if not relevant_docs:
            yield ContentChunk(content="抱歉，我在提供的文档中没有找到与您的问题相关的信息。请确认您的问题是否在文档范围内，或者尝试用不同的方式提问。")
            yield DoneChunk(confidence=0.0)
            return

        # Phase 3: Prepare context
        yield ProgressChunk(message="正在准备上下文...")
        context = self._format_context(relevant_docs)

        # Phase 4: Stream LLM response
        yield ProgressChunk(message="正在生成回答...")

        chain = self.prompt | self.streaming_llm

        async for chunk in chain.astream({
            "context": context,
            "question": question
        }):
            if hasattr(chunk, 'content') and chunk.content:
                yield ContentChunk(content=chunk.content)

        # Phase 5: Send sources and finish
        sources = self._format_sources(relevant_docs)
        yield SourcesChunk(sources=sources)

        # Calculate final confidence
        avg_score = sum(doc.get('score', 0) for doc in relevant_docs) / len(relevant_docs)
        confidence = min(avg_score * 2, 1.0)

        yield DoneChunk(confidence=confidence)

        logger.info(f"Successfully completed streaming query with {len(relevant_docs)} sources")

    async def batch_query(self, questions: list[str], collection_name: str = "documents") -> list[QueryResult]:
        """Process multiple questions in batch"""
        tasks = [self.query_documents(question, collection_name) for question in questions]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions in results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_result = QueryResult(
                    answer=f"处理问题时出错：{str(result)}",
                    sources=[],
                    confidence=0.0,
                    question=questions[i] if i < len(questions) else "Unknown"
                )
                processed_results.append(error_result)
            else:
                processed_results.append(result)

        return processed_results

    async def get_collection_info(self, collection_name: str) -> Optional[dict[str, Any]]:
        """Get information about a collection"""
        return await self.chroma_manager.get_collection_info(collection_name)

    def close(self):
        """Close connections and cleanup resources"""
        if hasattr(self, 'chroma_manager'):
            self.chroma_manager.close()
        logger.info("QueryService resources closed")
