"""
RAG retrieval chain implementation using LangChain with Qdrant vector store.
Following 2024 best practices for document question answering with source citations.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from langchain_community.chat_models.openai import ChatOpenAI
from langchain_community.embeddings.openai import OpenAIEmbeddings
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel

from ..vector_store.qdrant_client import QdrantManager
from .prompt_templates import format_sources, get_rag_prompt

logger = logging.getLogger(__name__)


class QueryResponse(BaseModel):
    """Structured response for RAG queries"""
    answer: str
    sources: List[Dict[str, Any]]
    confidence: float = 0.0
    query: str = ""


class DocumentRetriever:
    """Custom retriever that wraps Qdrant operations"""

    def __init__(self, qdrant_manager: QdrantManager, collection_name: str,
                 embeddings, top_k: int = 5):
        self.qdrant_manager = qdrant_manager
        self.collection_name = collection_name
        self.embeddings = embeddings
        self.top_k = top_k

    async def retrieve_documents(self, query: str) -> List[Dict[str, Any]]:
        """Retrieve relevant documents for a query"""
        try:
            # Generate query embedding
            query_embedding = await self.embeddings.aembed_query(query)

            # Search similar documents
            results = await self.qdrant_manager.search_similar(
                collection_name=self.collection_name,
                query_embedding=query_embedding,
                limit=self.top_k,
                score_threshold=0.3
            )

            return results

        except Exception as e:
            logger.error(f"Document retrieval failed: {e}")
            return []


class RetrievalChain:
    """
    Main RAG retrieval chain with LLM integration and source citation.
    Provides question answering with context from vector-stored documents.
    """

    def __init__(self, collection_name: str, qdrant_host: str = "localhost",
                 qdrant_port: int = 6334, openai_api_key: Optional[str] = None):
        """
        Initialize RAG retrieval chain.

        Args:
            collection_name: Qdrant collection name
            qdrant_host: Qdrant server host
            qdrant_port: Qdrant server port
            openai_api_key: OpenAI API key (if None, will try environment variable)
        """
        self.collection_name = collection_name

        # Initialize components
        try:
            # Qdrant manager
            self.qdrant_manager = QdrantManager(host=qdrant_host, port=qdrant_port)

            # Embeddings (using OpenAI as example, can be swapped)
            self.embeddings = OpenAIEmbeddings(
                model="text-embedding-ada-002",
                openai_api_key=openai_api_key
            )

            # LLM for answer generation
            self.llm = ChatOpenAI(
                model="gpt-3.5-turbo",
                temperature=0.1,  # Low temperature for factual answers
                openai_api_key=openai_api_key
            )

            # Document retriever
            self.retriever = DocumentRetriever(
                qdrant_manager=self.qdrant_manager,
                collection_name=collection_name,
                embeddings=self.embeddings,
                top_k=5
            )

            # Prompt template
            self.prompt = get_rag_prompt()

            logger.info(f"Initialized RetrievalChain for collection '{collection_name}'")

        except Exception as e:
            logger.error(f"Failed to initialize RetrievalChain: {e}")
            raise

    def _format_context(self, documents: List[Dict[str, Any]]) -> str:
        """Format retrieved documents as context"""
        if not documents:
            return "未找到相关文档。"

        context_parts = []
        for i, doc in enumerate(documents, 1):
            source = doc.get('source', 'Unknown')
            content = doc.get('content', '')

            context_part = f"[文档 {i}] 来源: {source}\n内容: {content}"
            context_parts.append(context_part)

        return "\n\n".join(context_parts)

    async def query(self, question: str, include_sources: bool = True) -> QueryResponse:
        """
        Answer a question using RAG.

        Args:
            question: User question
            include_sources: Whether to include source citations

        Returns:
            QueryResponse with answer and source information
        """
        try:
            # Retrieve relevant documents
            logger.info(f"Processing query: {question}")
            relevant_docs = await self.retriever.retrieve_documents(question)

            if not relevant_docs:
                return QueryResponse(
                    answer="抱歉，我在提供的文档中没有找到与您的问题相关的信息。请确认您的问题是否在文档范围内，或者尝试用不同的方式提问。",
                    sources=[],
                    confidence=0.0,
                    query=question
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
            sources = []
            if include_sources:
                for doc in relevant_docs:
                    source_info = {
                        "source": doc.get('source', 'Unknown'),
                        "content_preview": doc.get('content', '')[:200] + "..." if len(doc.get('content', '')) > 200 else doc.get('content', ''),
                        "score": doc.get('score', 0),
                        "start_index": doc.get('start_index', 0)
                    }
                    sources.append(source_info)

                # Add formatted sources to answer
                source_citation = format_sources(sources)
                if source_citation:
                    answer += source_citation

            logger.info(f"Successfully generated answer with {len(relevant_docs)} sources")

            return QueryResponse(
                answer=answer,
                sources=sources,
                confidence=confidence,
                query=question
            )

        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            return QueryResponse(
                answer=f"抱歉，处理您的问题时出现错误：{str(e)}",
                sources=[],
                confidence=0.0,
                query=question
            )

    async def batch_query(self, questions: List[str]) -> List[QueryResponse]:
        """Process multiple questions in batch"""
        tasks = [self.query(question) for question in questions]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions in results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_response = QueryResponse(
                    answer=f"处理问题时出错：{str(result)}",
                    sources=[],
                    confidence=0.0,
                    query=questions[i] if i < len(questions) else "Unknown"
                )
                processed_results.append(error_response)
            else:
                processed_results.append(result)

        return processed_results

    async def get_collection_stats(self) -> Optional[Dict[str, Any]]:
        """Get statistics about the current collection"""
        return await self.qdrant_manager.get_collection_info(self.collection_name)

    def close(self):
        """Close connections and cleanup resources"""
        try:
            self.qdrant_manager.close()
            logger.info("Closed RetrievalChain resources")
        except Exception as e:
            logger.error(f"Error closing RetrievalChain: {e}")


# Convenience function for creating retrieval chain
def create_retrieval_chain(collection_name: str, qdrant_host: str = "localhost",
                          qdrant_port: int = 6334, openai_api_key: Optional[str] = None) -> RetrievalChain:
    """Create and return a RetrievalChain instance"""
    return RetrievalChain(
        collection_name=collection_name,
        qdrant_host=qdrant_host,
        qdrant_port=qdrant_port,
        openai_api_key=openai_api_key
    )
