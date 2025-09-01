"""
Chat management and conversation routes.
"""

import logging

from fastapi import APIRouter, Request, status
from sse_starlette.sse import EventSourceResponse

from api.state import get_app_state
from exception import (
    HTTPBadRequestException,
    HTTPInternalServerErrorException,
    HTTPNotFoundException,
)
from models.requests import ChatMessageRequest, CreateChatRequest, UpdateChatRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chats", status_code=status.HTTP_201_CREATED)
async def create_chat(request_data: CreateChatRequest, request: Request):
    """
    Create a new chat conversation
    """
    chat_service = get_app_state(request).chat_service
    collection_service = get_app_state(request).collection_service

    # Validate collections exist
    for collection_id in request_data.collection_ids:
        collection = await collection_service.get_collection(collection_id)
        if not collection:
            raise HTTPBadRequestException(f"Collection '{collection_id}' not found")

    # Create chat
    chat = await chat_service.create_chat(
        name=request_data.name,
        collection_ids=request_data.collection_ids
    )

    logger.info(f"Created chat {chat.chat_id} with name '{chat.name}'")

    return chat


@router.get("/chats")
async def list_chats(
    request: Request,
    offset: int = 0,
    limit: int = 50
):
    """
    List chat conversations
    """
    chat_service = get_app_state(request).chat_service

    chats = await chat_service.list_chats(offset=offset, limit=limit)

    return {
        "chats": [chat.model_dump() for chat in chats],
        "offset": offset,
        "limit": limit,
        "total": len(chats)  # Could implement proper count if needed
    }


@router.get("/chats/{chat_id}")
async def get_chat(chat_id: str, request: Request):
    """
    Get chat information
    """
    chat_service = get_app_state(request).chat_service

    chat = await chat_service.get_chat(chat_id)

    if not chat:
        raise HTTPNotFoundException(f"Chat '{chat_id}' not found")

    return chat


@router.put("/chats/{chat_id}")
async def update_chat(
    chat_id: str,
    request_data: UpdateChatRequest,
    request: Request
):
    """
    Update chat information
    """
    app_state = get_app_state(request)
    chat_service = app_state.chat_service
    collection_service = app_state.collection_service

    # Validate collections exist if provided
    if request_data.collection_ids:
        for collection_id in request_data.collection_ids:
            collection = await collection_service.get_collection(collection_id)
            if not collection:
                raise HTTPBadRequestException(f"Collection '{collection_id}' not found")

    # Update chat
    chat = await chat_service.update_chat(
        chat_id=chat_id,
        name=request_data.name,
        collection_ids=request_data.collection_ids
    )

    if not chat:
        raise HTTPNotFoundException(f"Chat '{chat_id}' not found")

    logger.info(f"Updated chat {chat_id}")

    return chat


@router.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str, request: Request):
    """
    Delete a chat conversation
    """
    chat_service = get_app_state(request).chat_service

    success = await chat_service.delete_chat(chat_id)

    if not success:
        raise HTTPNotFoundException(f"Chat '{chat_id}' not found")

    logger.info(f"Deleted chat {chat_id}")

    return {
        "chat_id": chat_id,
        "deleted": True
    }


@router.get("/chats/{chat_id}/messages")
async def get_chat_messages(
    chat_id: str,
    request: Request,
    offset: int = 0,
    limit: int = 50
):
    """
    Get messages for a chat
    """
    chat_service = get_app_state(request).chat_service

    # Verify chat exists
    chat = await chat_service.get_chat(chat_id)
    if not chat:
        raise HTTPNotFoundException(f"Chat '{chat_id}' not found")

    messages = await chat_service.get_chat_messages(
        chat_id=chat_id,
        offset=offset,
        limit=limit
    )
    total = await chat_service.count_chat_messages(chat_id)

    return {
        "messages": [message.model_dump() for message in messages],
        "offset": offset,
        "limit": limit,
        "total": total
    }


@router.post("/chats/{chat_id}/chat")
async def send_message(
    chat_id: str,
    request_data: ChatMessageRequest,
    request: Request
):
    """
    Send a message and get AI response (synchronous)
    """
    chat_service = get_app_state(request).chat_service

    # Send message and get response
    response_message = await chat_service.chat(
        chat_id=chat_id,
        user_message=request_data.message
    )

    if not response_message:
        raise HTTPInternalServerErrorException("Failed to generate AI response")

    logger.info(f"Generated response for chat {chat_id}")

    return response_message


@router.post("/chats/{chat_id}/chat/stream")
async def send_message_stream(
    chat_id: str,
    request_data: ChatMessageRequest,
    request: Request
):
    """
    Send a message and get AI response (streaming via SSE)
    """
    chat_service = get_app_state(request).chat_service

    return EventSourceResponse(chat_service.chat_stream_generator(
        chat_id=chat_id,
        user_message=request_data.message
    ))
