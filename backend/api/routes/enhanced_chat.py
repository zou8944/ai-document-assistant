"""
Enhanced chat routes with advanced retrieval capabilities.
Implements P2-4 advanced retrieval features including intent analysis,
hybrid search strategies, and caching.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Query, Request
from sse_starlette.sse import EventSourceResponse

from api.response_utils import (
    raise_internal_error,
    raise_not_found,
    success_response,
)
from models.requests import ChatMessageRequest
from services.enhanced_chat_service import EnhancedChatService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chats/{chat_id}/chat/enhanced")
async def send_enhanced_message(
    chat_id: str,
    request_data: ChatMessageRequest,
    request: Request,
    enable_intent_analysis: bool = Query(True, description="Enable intelligent intent analysis"),
    enable_cache: bool = Query(True, description="Enable smart caching"),
    enable_summary_overview: bool = Query(True, description="Enable summary-based overview generation"),
    retrieval_strategy: str = Query("auto", description="Retrieval strategy: auto, semantic, hybrid")
):
    """
    Send a message with enhanced retrieval capabilities (synchronous)

    Features:
    - Intent-based retrieval strategy selection
    - Hybrid semantic + keyword search
    - Smart caching for improved performance
    - Summary-based overview generation

    Args:
        chat_id: Chat ID
        request_data: Message request data
        enable_intent_analysis: Whether to enable intent analysis
        enable_cache: Whether to enable caching
        enable_summary_overview: Whether to enable summary overview
        retrieval_strategy: Retrieval strategy to use

    Returns:
        Enhanced AI response with metadata
    """
    try:
        # Get enhanced chat service
        enhanced_service = request.app.state.enhanced_chat_service
        if not enhanced_service:
            # Fall back to creating service on demand
            chat_service = request.app.state.chat_service
            enhanced_service = EnhancedChatService(
                base_service=chat_service,
                enable_intent_analysis=enable_intent_analysis,
                enable_cache=enable_cache,
                enable_summary_overview=enable_summary_overview
            )

        # Verify chat exists
        chat = await enhanced_service.base_service.get_chat(chat_id)
        if not chat:
            raise_not_found(f"Chat '{chat_id}' not found")

        # Send enhanced message
        response = await enhanced_service.send_enhanced_message(
            chat_id=chat_id,
            user_message=request_data.message,
            retrieval_strategy=retrieval_strategy,
            include_sources=getattr(request_data, 'include_sources', True)
        )

        if not response:
            raise_internal_error("Failed to generate enhanced AI response")

        logger.info(f"Generated enhanced response for chat {chat_id}")

        return success_response(data=response.dict())

    except Exception as e:
        logger.error(f"Failed to send enhanced message: {e}")
        raise_internal_error(f"Failed to send enhanced message: {str(e)}")


@router.post("/chats/{chat_id}/chat/enhanced/stream")
async def send_enhanced_message_stream(
    chat_id: str,
    request_data: ChatMessageRequest,
    request: Request,
    enable_intent_analysis: bool = Query(True, description="Enable intelligent intent analysis"),
    enable_cache: bool = Query(True, description="Enable smart caching"),
    enable_summary_overview: bool = Query(True, description="Enable summary-based overview generation"),
    retrieval_strategy: str = Query("auto", description="Retrieval strategy: auto, semantic, hybrid")
):
    """
    Send a message with enhanced retrieval capabilities (streaming via SSE)

    Features:
    - Intent-based retrieval strategy selection
    - Hybrid semantic + keyword search
    - Smart caching for improved performance
    - Summary-based overview generation
    - Real-time streaming with detailed progress

    Args:
        chat_id: Chat ID
        request_data: Message request data
        enable_intent_analysis: Whether to enable intent analysis
        enable_cache: Whether to enable caching
        enable_summary_overview: Whether to enable summary overview
        retrieval_strategy: Retrieval strategy to use

    Returns:
        SSE stream with enhanced AI response and metadata
    """
    try:
        # Get enhanced chat service
        enhanced_service = request.app.state.enhanced_chat_service
        if not enhanced_service:
            # Fall back to creating service on demand
            chat_service = request.app.state.chat_service
            enhanced_service = EnhancedChatService(
                base_service=chat_service,
                enable_intent_analysis=enable_intent_analysis,
                enable_cache=enable_cache,
                enable_summary_overview=enable_summary_overview
            )

        # Verify chat exists
        chat = await enhanced_service.base_service.get_chat(chat_id)
        if not chat:
            raise_not_found(f"Chat '{chat_id}' not found")

        async def event_generator():
            """Generate SSE events for enhanced streaming response"""
            try:
                # Send initial metadata
                yield {
                    "event": "metadata",
                    "data": json.dumps({
                        "chat_id": chat_id,
                        "user_message": request_data.message,
                        "collections": chat.collection_ids,
                        "enhanced_features": {
                            "intent_analysis": enable_intent_analysis,
                            "cache_enabled": enable_cache,
                            "summary_overview": enable_summary_overview,
                            "retrieval_strategy": retrieval_strategy
                        }
                    })
                }

                # Stream enhanced response
                async for event in enhanced_service.send_enhanced_message_stream(
                    chat_id=chat_id,
                    user_message=request_data.message,
                    retrieval_strategy=retrieval_strategy,
                    include_sources=getattr(request_data, 'include_sources', True)
                ):
                    yield event

            except Exception as e:
                logger.error(f"Error in enhanced streaming response: {e}")
                yield {
                    "event": "error",
                    "data": json.dumps({
                        "message": f"Error generating enhanced response: {str(e)}"
                    })
                }

        return EventSourceResponse(event_generator())

    except Exception as e:
        logger.error(f"Failed to start enhanced streaming response: {e}")
        raise_internal_error(f"Failed to start enhanced streaming response: {str(e)}")


@router.get("/chats/{chat_id}/intent-analysis")
async def analyze_message_intent(
    chat_id: str,
    message: str = Query(..., description="Message to analyze"),
    request: Request = None
):
    """
    Analyze the intent of a message without sending it

    Args:
        chat_id: Chat ID
        message: Message to analyze

    Returns:
        Intent analysis results
    """
    try:
        # Get enhanced chat service
        enhanced_service = request.app.state.enhanced_chat_service
        if not enhanced_service:
            chat_service = request.app.state.chat_service
            enhanced_service = EnhancedChatService(
                base_service=chat_service,
                enable_intent_analysis=True
            )

        # Verify chat exists
        chat = await enhanced_service.base_service.get_chat(chat_id)
        if not chat:
            raise_not_found(f"Chat '{chat_id}' not found")

        # Analyze intent
        intent_analysis = await enhanced_service.analyze_intent(message)

        logger.info(f"Analyzed intent for message in chat {chat_id}")

        return success_response(data=intent_analysis)

    except Exception as e:
        logger.error(f"Failed to analyze intent: {e}")
        raise_internal_error(f"Failed to analyze intent: {str(e)}")


@router.get("/chats/{chat_id}/cache-stats")
async def get_cache_statistics(
    chat_id: str,
    request: Request
):
    """
    Get cache statistics for a chat's collection

    Args:
        chat_id: Chat ID

    Returns:
        Cache statistics
    """
    try:
        # Get enhanced chat service
        enhanced_service = request.app.state.enhanced_chat_service
        if not enhanced_service:
            chat_service = request.app.state.chat_service
            enhanced_service = EnhancedChatService(
                base_service=chat_service,
                enable_cache=True
            )

        # Verify chat exists
        chat = await enhanced_service.base_service.get_chat(chat_id)
        if not chat:
            raise_not_found(f"Chat '{chat_id}' not found")

        # Get cache stats
        cache_stats = enhanced_service.get_cache_stats()

        return success_response(data=cache_stats or {
            "message": "Cache not enabled or no statistics available"
        })

    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise_internal_error(f"Failed to get cache stats: {str(e)}")


@router.delete("/chats/{chat_id}/cache")
async def clear_cache(
    chat_id: str,
    request: Request,
    cache_type: Optional[str] = Query(None, description="Type of cache to clear (query_results, intent, embeddings)")
):
    """
    Clear cache for a chat

    Args:
        chat_id: Chat ID
        cache_type: Optional specific cache type to clear

    Returns:
        Cache clear results
    """
    try:
        # Get enhanced chat service
        enhanced_service = request.app.state.enhanced_chat_service
        if not enhanced_service:
            chat_service = request.app.state.chat_service
            enhanced_service = EnhancedChatService(
                base_service=chat_service,
                enable_cache=True
            )

        # Verify chat exists
        chat = await enhanced_service.base_service.get_chat(chat_id)
        if not chat:
            raise_not_found(f"Chat '{chat_id}' not found")

        # Clear cache
        cleared_count = enhanced_service.clear_cache(cache_type)

        logger.info(f"Cleared {cleared_count} cache entries for chat {chat_id}")

        return success_response(data={
            "cleared_count": cleared_count,
            "cache_type": cache_type or "all"
        })

    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise_internal_error(f"Failed to clear cache: {str(e)}")


@router.get("/enhanced-retrieval/strategies")
async def get_available_strategies():
    """
    Get available retrieval strategies and their descriptions

    Returns:
        List of available retrieval strategies
    """
    try:
        strategies = {
            "auto": {
                "name": "Automatic",
                "description": "Automatically selects the best strategy based on query intent analysis",
                "features": ["Intent analysis", "Dynamic strategy selection", "Optimized for query type"]
            },
            "semantic": {
                "name": "Semantic Search",
                "description": "Pure vector-based semantic similarity search",
                "features": ["Vector similarity", "Context understanding", "Semantic matching"]
            },
            "hybrid": {
                "name": "Hybrid Search",
                "description": "Combines semantic search with keyword matching and ranking",
                "features": ["Vector similarity", "Keyword matching", "Relevance fusion", "Best of both worlds"]
            }
        }

        return success_response(data={
            "strategies": strategies,
            "default": "auto",
            "recommended": "auto"
        })

    except Exception as e:
        logger.error(f"Failed to get retrieval strategies: {e}")
        raise_internal_error(f"Failed to get retrieval strategies: {str(e)}")
