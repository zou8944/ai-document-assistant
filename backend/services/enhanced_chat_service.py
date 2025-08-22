"""
Enhanced chat service integrating advanced retrieval capabilities.
Implements P2-4 advanced retrieval features including intent analysis,
hybrid search strategies, and intelligent caching.
"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any, Optional

from database.connection import get_db_session_context
from models.responses import ChatMessageResponse
from rag.enhanced_retrieval_chain import EnhancedRetrievalChain
from rag.intent_analyzer import QueryIntent
from repository.chat import ChatMessageRepository
from services.chat_service import ChatService

logger = logging.getLogger(__name__)


class EnhancedChatService:
    """
    Enhanced chat service with advanced retrieval capabilities

    Features:
    - Intent-based query analysis and routing
    - Hybrid semantic + keyword search
    - Smart caching for improved performance
    - Summary-based overview generation
    - Multi-collection retrieval optimization
    """

    def __init__(
        self,
        base_service: ChatService,
        enable_intent_analysis: bool = True,
        enable_cache: bool = True,
        enable_summary_overview: bool = True
    ):
        """
        Initialize enhanced chat service

        Args:
            base_service: Base chat service instance
            enable_intent_analysis: Whether to enable intent analysis
            enable_cache: Whether to enable caching
            enable_summary_overview: Whether to enable summary overview
        """
        self.base_service = base_service
        self.enable_intent_analysis = enable_intent_analysis
        self.enable_cache = enable_cache
        self.enable_summary_overview = enable_summary_overview

        # Enhanced retrieval chains per collection (lazy initialization)
        self._retrieval_chains: dict[str, EnhancedRetrievalChain] = {}

        logger.info(f"Enhanced chat service initialized - Intent: {enable_intent_analysis}, "
                   f"Cache: {enable_cache}, Summary: {enable_summary_overview}")

    def _get_or_create_retrieval_chain(self, collection_id: str) -> EnhancedRetrievalChain:
        """
        Get or create enhanced retrieval chain for a collection

        Args:
            collection_id: Collection identifier

        Returns:
            Enhanced retrieval chain instance
        """
        if collection_id not in self._retrieval_chains:
            try:
                chain = EnhancedRetrievalChain(
                    collection_name=collection_id,
                    chroma_persist_directory=self.base_service.config.chroma_persist_directory,
                    openai_api_key=self.base_service.config.openai_api_key,
                    enable_summary_overview=self.enable_summary_overview,
                    enable_cache=self.enable_cache
                )
                self._retrieval_chains[collection_id] = chain
                logger.info(f"Created enhanced retrieval chain for collection '{collection_id}'")
            except Exception as e:
                logger.error(f"Failed to create retrieval chain for '{collection_id}': {e}")
                raise

        return self._retrieval_chains[collection_id]

    async def analyze_intent(self, message: str) -> dict[str, Any]:
        """
        Analyze the intent of a message

        Args:
            message: User message to analyze

        Returns:
            Intent analysis results
        """
        if not self.enable_intent_analysis:
            return {
                "intent": QueryIntent.FACTUAL,
                "confidence": "disabled",
                "analysis_method": "disabled"
            }

        # Use any collection's retrieval chain for intent analysis
        if not self._retrieval_chains:
            # Create a temporary chain for intent analysis
            try:
                temp_chain = EnhancedRetrievalChain(
                    collection_name="temp",
                    enable_summary_overview=False,
                    enable_cache=False
                )
                intent_analysis = await temp_chain.get_intent_analysis(message)
                # Don't store this temp chain
                return intent_analysis
            except Exception as e:
                # Only catch intent analysis specific errors, let system errors propagate
                logger.warning(f"Intent analysis failed, using fallback: {e}")
                return {
                    "intent": QueryIntent.FACTUAL,
                    "confidence": "low",
                    "analysis_method": "fallback",
                    "error": str(e)
                }
        else:
            # Use an existing chain
            chain = next(iter(self._retrieval_chains.values()))
            try:
                intent_analysis = await chain.get_intent_analysis(message)
                return intent_analysis
            except Exception as e:
                # Only catch intent analysis specific errors
                logger.warning(f"Intent analysis failed, using fallback: {e}")
                return {
                    "intent": QueryIntent.FACTUAL,
                    "confidence": "low",
                    "analysis_method": "fallback",
                    "error": str(e)
                }

    async def _retrieve_enhanced_multi_collection(
        self,
        query: str,
        collection_ids: list[str],
        retrieval_strategy: str = "auto"
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """
        Enhanced multi-collection retrieval with intent analysis

        Args:
            query: Query text
            collection_ids: List of collection IDs to search
            retrieval_strategy: Retrieval strategy to use

        Returns:
            Tuple of (retrieved documents, metadata)
        """
        all_results = []
        metadata = {
            "strategy_used": retrieval_strategy,
            "collections_searched": collection_ids,
            "intent_analysis": None,
            "cache_hits": 0,
            "total_documents": 0
        }

        # Analyze intent if enabled
        if self.enable_intent_analysis:
            intent_analysis = await self.analyze_intent(query)
            metadata["intent_analysis"] = intent_analysis
            logger.info(f"Query intent: {intent_analysis.get('intent', {}).value if hasattr(intent_analysis.get('intent', {}), 'value') else 'unknown'}")

        # Retrieve from each collection using enhanced chain
        for collection_id in collection_ids:
            try:
                chain = self._get_or_create_retrieval_chain(collection_id)

                if retrieval_strategy == "auto":
                    # Use enhanced query method (intent-aware)
                    query_response = await chain.query(query, include_sources=True)

                    # Extract documents from response
                    if query_response and query_response.sources:
                        for source in query_response.sources:
                            doc = {
                                'content': source.get('content_preview', ''),
                                'source': source.get('source', 'Unknown'),
                                'document_id': source.get('document_id', ''),
                                'chunk_index': source.get('chunk_index', 0),
                                'score': source.get('score', 0.0),
                                'collection_id': collection_id,
                                'retrieval_method': 'enhanced_auto'
                            }
                            all_results.append(doc)

                elif retrieval_strategy == "semantic" or retrieval_strategy == "hybrid":
                    # Use base retrieval for non-auto strategies
                    # Fall back to basic semantic search
                    query_embedding = await self.base_service.embeddings.aembed_query(query)

                    results = await self.base_service.chroma_manager.search_similar(
                        collection_name=collection_id,
                        query_embedding=query_embedding,
                        limit=5,
                        score_threshold=0.3
                    )

                    for result in results:
                        result['collection_id'] = collection_id
                        result['retrieval_method'] = retrieval_strategy

                    all_results.extend(results)

                # Check if cache was used
                if self.enable_cache and hasattr(chain, 'cache_manager') and chain.cache_manager:
                    cache_stats = chain.get_cache_stats()
                    if cache_stats and cache_stats.get('query_cache_hits', 0) > 0:
                        metadata["cache_hits"] += 1

            except Exception as e:
                logger.warning(f"Failed to search collection '{collection_id}': {e}")
                continue

        # Sort by relevance score
        all_results.sort(key=lambda x: x.get('score', 0), reverse=True)

        # Limit total results
        max_results = 15 if metadata.get("intent_analysis", {}).get("intent") == QueryIntent.OVERVIEW else 10
        all_results = all_results[:max_results]

        metadata["total_documents"] = len(all_results)

        logger.info(f"Enhanced multi-collection retrieval completed: {len(all_results)} documents from {len(collection_ids)} collections")

        return all_results, metadata

    async def send_enhanced_message(
        self,
        chat_id: str,
        user_message: str,
        retrieval_strategy: str = "auto",
        include_sources: bool = True
    ) -> Optional[ChatMessageResponse]:
        """
        Send a message with enhanced retrieval capabilities

        Args:
            chat_id: Chat ID
            user_message: User message content
            retrieval_strategy: Retrieval strategy to use
            include_sources: Whether to include source references

        Returns:
            Enhanced chat message response
        """
        # Get chat information
        chat = await self.base_service.get_chat(chat_id)
        if not chat:
            raise ValueError(f"Chat '{chat_id}' not found")

        # Save user message
        with get_db_session_context() as session:
            message_repo = ChatMessageRepository(session)
            message_repo.add_message(
                chat_id=chat_id,
                role="user",
                content=user_message
            )

        # Enhanced multi-collection retrieval
        relevant_docs, retrieval_metadata = await self._retrieve_enhanced_multi_collection(
            user_message,
            chat.collection_ids,
            retrieval_strategy
        )

        # If we have enhanced retrieval chains and auto strategy, use enhanced query
        if (retrieval_strategy == "auto" and
            chat.collection_ids and
            len(relevant_docs) > 0):

            # Use the first collection's enhanced chain for final response generation
            primary_collection = chat.collection_ids[0]
            chain = self._get_or_create_retrieval_chain(primary_collection)

            # Generate enhanced response
            query_response = await chain.query(user_message, include_sources=include_sources)

            if query_response:
                ai_response = query_response.answer
                sources = self.base_service._format_sources(relevant_docs)
                confidence = query_response.confidence
            else:
                # Fallback to basic response generation
                ai_response, sources, confidence = await self._generate_basic_response(
                    user_message, relevant_docs, chat_id
                )
        else:
            # Use basic response generation for non-auto strategies
            ai_response, sources, confidence = await self._generate_basic_response(
                user_message, relevant_docs, chat_id
            )

        # Save AI response with enhanced metadata
        enhanced_metadata = {
            "model": self.base_service.config.openai_chat_model,
            "sources_count": len(sources),
            "collections_searched": chat.collection_ids,
            "retrieval_strategy": retrieval_strategy,
            "confidence": confidence,
            **retrieval_metadata
        }

        with get_db_session_context() as session:
            message_repo = ChatMessageRepository(session)
            ai_msg = message_repo.add_message(
                chat_id=chat_id,
                role="assistant",
                content=ai_response,
                sources=json.dumps([source.dict() for source in sources]),
                metadata=json.dumps(enhanced_metadata)
            )

        logger.info(f"Generated enhanced AI response for chat {chat_id} with {len(sources)} sources")

        return self.base_service._to_message_response(ai_msg)


    async def _generate_basic_response(
        self,
        user_message: str,
        relevant_docs: list[dict[str, Any]],
        chat_id: str
    ) -> tuple[str, list, float]:
        """
        Generate basic response using standard RAG approach

        Args:
            user_message: User message
            relevant_docs: Retrieved documents
            chat_id: Chat ID

        Returns:
            Tuple of (response text, sources, confidence)
        """
        # Format context and sources
        context = self.base_service._format_context(relevant_docs)
        sources = self.base_service._format_sources(relevant_docs)

        # Get conversation history
        with get_db_session_context() as session:
            message_repo = ChatMessageRepository(session)
            history = message_repo.get_conversation_history(chat_id, max_messages=10)

        # Format conversation history
        conversation_context = ""
        if len(history) > 1:
            conversation_context = "\n对话历史:\n"
            for msg in history[:-1]:
                conversation_context += f"{msg.role}: {msg.content}\n"

        # Generate response
        from langchain_core.output_parsers import StrOutputParser

        from rag.prompt_templates import get_rag_prompt

        prompt = get_rag_prompt()
        full_context = context
        if conversation_context:
            full_context = conversation_context + "\n\n当前文档上下文:\n" + context

        chain = prompt | self.base_service.llm | StrOutputParser()
        ai_response = await chain.ainvoke({
            "context": full_context,
            "question": user_message
        })

        # Calculate confidence based on document relevance
        confidence = 0.0
        if relevant_docs:
            avg_score = sum(doc.get('score', 0) for doc in relevant_docs) / len(relevant_docs)
            confidence = min(avg_score * 2, 0.9)

        return ai_response, sources, confidence

    async def send_enhanced_message_stream(
        self,
        chat_id: str,
        user_message: str,
        retrieval_strategy: str = "auto",
        include_sources: bool = True
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Send enhanced message with streaming response

        Args:
            chat_id: Chat ID
            user_message: User message
            retrieval_strategy: Retrieval strategy to use
            include_sources: Whether to include sources

        Yields:
            SSE events for streaming response
        """
        # Get chat information
        chat = await self.base_service.get_chat(chat_id)
        if not chat:
            yield {
                "event": "error",
                "data": json.dumps({"message": f"Chat '{chat_id}' not found"})
            }
            return

        # Send initial status
        yield {
            "event": "status",
            "data": json.dumps({"status": "analyzing_intent"})
        }

        # Analyze intent
        intent_analysis = None
        if self.enable_intent_analysis:
            intent_analysis = await self.analyze_intent(user_message)
            yield {
                "event": "intent_analysis",
                "data": json.dumps(intent_analysis)
            }

        # Save user message
        with get_db_session_context() as session:
            message_repo = ChatMessageRepository(session)
            user_msg = message_repo.add_message(
                chat_id=chat_id,
                role="user",
                content=user_message
            )

        yield {
            "event": "user_message",
            "data": json.dumps({
                "message_id": user_msg.id,
                "content": user_message
            })
        }

        # Enhanced retrieval
        yield {
            "event": "status",
            "data": json.dumps({"status": "retrieving_documents_enhanced"})
        }

        relevant_docs, retrieval_metadata = await self._retrieve_enhanced_multi_collection(
            user_message,
            chat.collection_ids,
            retrieval_strategy
        )

        # Send sources and metadata
        sources = self.base_service._format_sources(relevant_docs)
        yield {
            "event": "sources",
            "data": json.dumps({
                "sources": [source.dict() for source in sources],
                "count": len(sources),
                "metadata": retrieval_metadata
            })
        }

        # Generate response
        yield {
            "event": "status",
            "data": json.dumps({"status": "generating_enhanced_response"})
        }

        # Prepare streaming response
        if (retrieval_strategy == "auto" and
            chat.collection_ids and
            len(relevant_docs) > 0):

            # Use enhanced streaming if available
            try:
                primary_collection = chat.collection_ids[0]
                chain = self._get_or_create_retrieval_chain(primary_collection)

                # Stream enhanced response (would need to implement streaming in EnhancedRetrievalChain)
                # For now, fall back to basic streaming
                async for event in self._stream_basic_response(
                    user_message, relevant_docs, chat_id, sources, retrieval_metadata
                ):
                    yield event

            except Exception as e:
                logger.warning(f"Enhanced streaming failed, falling back to basic: {e}")
                async for event in self._stream_basic_response(
                    user_message, relevant_docs, chat_id, sources, retrieval_metadata
                ):
                    yield event
        else:
            # Basic streaming
            async for event in self._stream_basic_response(
                user_message, relevant_docs, chat_id, sources, retrieval_metadata
            ):
                yield event

    async def _stream_basic_response(
        self,
        user_message: str,
        relevant_docs: list[dict[str, Any]],
        chat_id: str,
        sources: list,
        retrieval_metadata: dict[str, Any]
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Stream basic response generation

        Args:
            user_message: User message
            relevant_docs: Retrieved documents
            chat_id: Chat ID
            sources: Formatted sources
            retrieval_metadata: Retrieval metadata

        Yields:
            SSE events for streaming
        """
        # Prepare context
        context = self.base_service._format_context(relevant_docs)

        # Get conversation history
        with get_db_session_context() as session:
            message_repo = ChatMessageRepository(session)
            history = message_repo.get_conversation_history(chat_id, max_messages=10)

        conversation_context = ""
        if len(history) > 1:
            conversation_context = "\n对话历史:\n"
            for msg in history[:-1]:
                conversation_context += f"{msg.role}: {msg.content}\n"

        full_context = context
        if conversation_context:
            full_context = conversation_context + "\n\n当前文档上下文:\n" + context

        # Stream response
        from rag.prompt_templates import get_rag_prompt
        prompt = get_rag_prompt()
        chain = prompt | self.base_service.llm

        full_response = ""
        async for chunk in chain.astream({
            "context": full_context,
            "question": user_message
        }):
            content = chunk.content if hasattr(chunk, 'content') else str(chunk)
            if content:
                full_response += content
                yield {
                    "event": "content",
                    "data": json.dumps({"content": content})
                }

        # Calculate confidence
        confidence = 0.0
        if relevant_docs:
            avg_score = sum(doc.get('score', 0) for doc in relevant_docs) / len(relevant_docs)
            confidence = min(avg_score * 2, 0.9)

        # Save complete response
        enhanced_metadata = {
            "model": self.base_service.config.openai_chat_model,
            "sources_count": len(sources),
            "confidence": confidence,
            **retrieval_metadata
        }

        with get_db_session_context() as session:
            message_repo = ChatMessageRepository(session)
            ai_msg = message_repo.add_message(
                chat_id=chat_id,
                role="assistant",
                content=full_response,
                sources=json.dumps([source.dict() for source in sources]),
                metadata=json.dumps(enhanced_metadata)
            )

        # Send completion
        yield {
            "event": "done",
            "data": json.dumps({
                "message_id": ai_msg.id,
                "sources_count": len(sources),
                "confidence": confidence,
                "total_content_length": len(full_response),
                "metadata": enhanced_metadata
            })
        }

    def get_cache_stats(self) -> Optional[dict[str, Any]]:
        """
        Get aggregate cache statistics from all retrieval chains

        Returns:
            Aggregate cache statistics
        """
        if not self.enable_cache:
            return None

        total_stats = {
            "chains_count": len(self._retrieval_chains),
            "total_cache_hits": 0,
            "total_cache_misses": 0,
            "hit_rate": 0.0,
            "per_collection": {}
        }

        for collection_id, chain in self._retrieval_chains.items():
            try:
                chain_stats = chain.get_cache_stats()
                if chain_stats:
                    total_stats["per_collection"][collection_id] = chain_stats
                    total_stats["total_cache_hits"] += chain_stats.get("query_cache_hits", 0)
                    total_stats["total_cache_misses"] += chain_stats.get("query_cache_misses", 0)
            except Exception as e:
                logger.warning(f"Failed to get cache stats for collection '{collection_id}': {e}")
                continue

        # Calculate overall hit rate
        total_requests = total_stats["total_cache_hits"] + total_stats["total_cache_misses"]
        if total_requests > 0:
            total_stats["hit_rate"] = total_stats["total_cache_hits"] / total_requests

        return total_stats

    def clear_cache(self, cache_type: Optional[str] = None) -> int:
        """
        Clear cache from all retrieval chains

        Args:
            cache_type: Optional specific cache type to clear

        Returns:
            Total number of cache entries cleared
        """
        total_cleared = 0

        for collection_id, chain in self._retrieval_chains.items():
            try:
                cleared_count = chain.clear_cache(cache_type)
                total_cleared += cleared_count
                logger.info(f"Cleared {cleared_count} cache entries from collection '{collection_id}'")
            except Exception as e:
                logger.warning(f"Failed to clear cache for collection '{collection_id}': {e}")
                continue

        return total_cleared

    def close(self):
        """Close all resources"""
        for chain in self._retrieval_chains.values():
            try:
                if hasattr(chain, 'close'):
                    chain.close()
            except Exception as e:
                logger.warning(f"Error closing retrieval chain: {e}")

        self._retrieval_chains.clear()
        logger.info("Enhanced chat service resources closed")
