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

from api.state import get_app_state
from exception import HTTPInternalServerErrorException, HTTPNotFoundException
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
    """
    # Get enhanced chat service
    app_state = get_app_state(request)

    enhanced_service = app_state.enhanced_chat_service
    if not enhanced_service:
        # Fall back to creating service on demand
        app_state = get_app_state(request)

        chat_service = app_state.chat_service
        enhanced_service = EnhancedChatService(
            base_service=chat_service,
            enable_intent_analysis=enable_intent_analysis,
            enable_cache=enable_cache,
            enable_summary_overview=enable_summary_overview
        )

    # Verify chat exists
    chat = await enhanced_service.base_service.get_chat(chat_id)
    if not chat:
        raise HTTPNotFoundException(f"Chat '{chat_id}' not found")

    # Send enhanced message
    response = await enhanced_service.send_enhanced_message(
        chat_id=chat_id,
        user_message=request_data.message,
        retrieval_strategy=retrieval_strategy,
        include_sources=getattr(request_data, 'include_sources', True)
    )

    if not response:
        raise HTTPInternalServerErrorException("Failed to generate enhanced AI response")

    logger.info(f"Generated enhanced response for chat {chat_id}")

    return response


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
    """
    # Get enhanced chat service
    app_state = get_app_state(request)

    enhanced_service = app_state.enhanced_chat_service
    if not enhanced_service:
        # Fall back to creating service on demand
        app_state = get_app_state(request)

        chat_service = app_state.chat_service
        enhanced_service = EnhancedChatService(
            base_service=chat_service,
            enable_intent_analysis=enable_intent_analysis,
            enable_cache=enable_cache,
            enable_summary_overview=enable_summary_overview
        )

    # Verify chat exists
    chat = await enhanced_service.base_service.get_chat(chat_id)
    if not chat:
        raise HTTPNotFoundException(f"Chat '{chat_id}' not found")

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


@router.get("/chats/{chat_id}/intent-analysis")
async def analyze_message_intent(
    chat_id: str,
    message: str = Query(..., description="Message to analyze"),
    request: Request = None
):
    """
    Analyze the intent of a message without sending it
    """
    assert request
    # Get enhanced chat service
    app_state = get_app_state(request)

    enhanced_service = app_state.enhanced_chat_service
    if not enhanced_service:
        app_state = get_app_state(request)

        chat_service = app_state.chat_service
        enhanced_service = EnhancedChatService(
            base_service=chat_service,
            enable_intent_analysis=True
        )

    # Verify chat exists
    chat = await enhanced_service.base_service.get_chat(chat_id)
    if not chat:
        raise HTTPNotFoundException(f"Chat '{chat_id}' not found")

    # Analyze intent
    intent_analysis = await enhanced_service.analyze_intent(message)

    logger.info(f"Analyzed intent for message in chat {chat_id}")

    return intent_analysis


@router.get("/chats/{chat_id}/cache-stats")
async def get_cache_statistics(
    chat_id: str,
    request: Request
):
    """
    Get cache statistics for a chat's collection
    """
    # Get enhanced chat service
    app_state = get_app_state(request)

    enhanced_service = app_state.enhanced_chat_service
    if not enhanced_service:
        app_state = get_app_state(request)

        chat_service = app_state.chat_service
        enhanced_service = EnhancedChatService(
            base_service=chat_service,
            enable_cache=True
        )

    # Verify chat exists
    chat = await enhanced_service.base_service.get_chat(chat_id)
    if not chat:
        raise HTTPNotFoundException(f"Chat '{chat_id}' not found")

    # Get cache stats
    cache_stats = enhanced_service.get_cache_stats()

    return cache_stats or {
        "message": "Cache not enabled or no statistics available"
    }


@router.delete("/chats/{chat_id}/cache")
async def clear_cache(
    chat_id: str,
    request: Request,
    cache_type: Optional[str] = Query(None, description="Type of cache to clear (query_results, intent, embeddings)")
):
    """
    Clear cache for a chat
    """
    # Get enhanced chat service
    app_state = get_app_state(request)

    enhanced_service = app_state.enhanced_chat_service
    if not enhanced_service:
        app_state = get_app_state(request)

        chat_service = app_state.chat_service
        enhanced_service = EnhancedChatService(
            base_service=chat_service,
            enable_cache=True
        )

    # Verify chat exists
    chat = await enhanced_service.base_service.get_chat(chat_id)
    if not chat:
        raise HTTPNotFoundException(f"Chat '{chat_id}' not found")

    # Clear cache
    cleared_count = enhanced_service.clear_cache(cache_type)

    logger.info(f"Cleared {cleared_count} cache entries for chat {chat_id}")

    return {
        "cleared_count": cleared_count,
        "cache_type": cache_type or "all"
    }
