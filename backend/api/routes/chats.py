"""
Chat management and conversation routes.
"""

import json
import logging

from fastapi import APIRouter, Request, status
from sse_starlette.sse import EventSourceResponse

from api.response_utils import (
    raise_bad_request,
    raise_internal_error,
    raise_not_found,
    success_response,
)
from models.requests import ChatMessageRequest, CreateChatRequest, UpdateChatRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chats", status_code=status.HTTP_201_CREATED)
async def create_chat(request_data: CreateChatRequest, request: Request):
    """
    Create a new chat conversation

    Args:
        request_data: Chat creation request data

    Returns:
        Created chat information
    """
    try:
        chat_service = request.app.state.chat_service

        # Validate collections exist
        collection_service = request.app.state.collection_service
        for collection_id in request_data.collection_ids:
            collection = await collection_service.get_collection(collection_id)
            if not collection:
                raise_bad_request(f"Collection '{collection_id}' not found")

        # Create chat
        chat = await chat_service.create_chat(
            name=request_data.name,
            collection_ids=request_data.collection_ids
        )

        if not chat:
            raise_internal_error("Failed to create chat")

        logger.info(f"Created chat {chat.chat_id} with name '{chat.name}'")

        return success_response(data=chat.dict())

    except Exception as e:
        logger.error(f"Failed to create chat: {e}")
        raise_internal_error(f"Failed to create chat: {str(e)}")


@router.get("/chats")
async def list_chats(
    request: Request,
    offset: int = 0,
    limit: int = 50
):
    """
    List chat conversations

    Args:
        offset: Offset for pagination
        limit: Limit for pagination

    Returns:
        List of chat conversations
    """
    try:
        chat_service = request.app.state.chat_service

        chats = await chat_service.list_chats(offset=offset, limit=limit)

        return success_response(data={
            "chats": [chat.dict() for chat in chats],
            "offset": offset,
            "limit": limit,
            "total": len(chats)  # Could implement proper count if needed
        })

    except Exception as e:
        logger.error(f"Failed to list chats: {e}")
        raise_internal_error(f"Failed to list chats: {str(e)}")


@router.get("/chats/{chat_id}")
async def get_chat(chat_id: str, request: Request):
    """
    Get chat information

    Args:
        chat_id: Chat ID

    Returns:
        Chat information
    """
    try:
        chat_service = request.app.state.chat_service

        chat = await chat_service.get_chat(chat_id)

        if not chat:
            raise_not_found(f"Chat '{chat_id}' not found")

        return success_response(data=chat.dict())

    except Exception as e:
        logger.error(f"Failed to get chat: {e}")
        raise_internal_error(f"Failed to get chat: {str(e)}")


@router.put("/chats/{chat_id}")
async def update_chat(
    chat_id: str,
    request_data: UpdateChatRequest,
    request: Request
):
    """
    Update chat information

    Args:
        chat_id: Chat ID
        request_data: Chat update request data

    Returns:
        Updated chat information
    """
    try:
        chat_service = request.app.state.chat_service

        # Validate collections exist if provided
        if request_data.collection_ids:
            collection_service = request.app.state.collection_service
            for collection_id in request_data.collection_ids:
                collection = await collection_service.get_collection(collection_id)
                if not collection:
                    raise_bad_request(f"Collection '{collection_id}' not found")

        # Update chat
        chat = await chat_service.update_chat(
            chat_id=chat_id,
            name=request_data.name,
            collection_ids=request_data.collection_ids
        )

        if not chat:
            raise_not_found(f"Chat '{chat_id}' not found")

        logger.info(f"Updated chat {chat_id}")

        return success_response(data=chat.dict())

    except Exception as e:
        logger.error(f"Failed to update chat: {e}")
        raise_internal_error(f"Failed to update chat: {str(e)}")


@router.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str, request: Request):
    """
    Delete a chat conversation

    Args:
        chat_id: Chat ID

    Returns:
        Success status
    """
    try:
        chat_service = request.app.state.chat_service

        success = await chat_service.delete_chat(chat_id)

        if not success:
            raise_not_found(f"Chat '{chat_id}' not found")

        logger.info(f"Deleted chat {chat_id}")

        return success_response(data={
            "chat_id": chat_id,
            "deleted": True
        })

    except Exception as e:
        logger.error(f"Failed to delete chat: {e}")
        raise_internal_error(f"Failed to delete chat: {str(e)}")


@router.get("/chats/{chat_id}/messages")
async def get_chat_messages(
    chat_id: str,
    request: Request,
    offset: int = 0,
    limit: int = 50
):
    """
    Get messages for a chat

    Args:
        chat_id: Chat ID
        offset: Offset for pagination
        limit: Limit for pagination

    Returns:
        List of chat messages
    """
    try:
        chat_service = request.app.state.chat_service

        # Verify chat exists
        chat = await chat_service.get_chat(chat_id)
        if not chat:
            raise_not_found(f"Chat '{chat_id}' not found")

        messages = await chat_service.get_chat_messages(
            chat_id=chat_id,
            offset=offset,
            limit=limit
        )

        return success_response(data={
            "messages": [message.dict() for message in messages],
            "offset": offset,
            "limit": limit,
            "total": len(messages)  # Could implement proper count if needed
        })

    except Exception as e:
        logger.error(f"Failed to get chat messages: {e}")
        raise_internal_error(f"Failed to get chat messages: {str(e)}")


@router.post("/chats/{chat_id}/chat")
async def send_message(
    chat_id: str,
    request_data: ChatMessageRequest,
    request: Request
):
    """
    Send a message and get AI response (synchronous)

    Args:
        chat_id: Chat ID
        request_data: Message request data

    Returns:
        AI response message
    """
    try:
        chat_service = request.app.state.chat_service

        # Verify chat exists
        chat = await chat_service.get_chat(chat_id)
        if not chat:
            raise_not_found(f"Chat '{chat_id}' not found")

        # Send message and get response
        response_message = await chat_service.send_message(
            chat_id=chat_id,
            user_message=request_data.message
        )

        if not response_message:
            raise_internal_error("Failed to generate AI response")

        logger.info(f"Generated response for chat {chat_id}")

        return success_response(data=response_message.dict())

    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        raise_internal_error(f"Failed to send message: {str(e)}")


@router.post("/chats/{chat_id}/chat/stream")
async def send_message_stream(
    chat_id: str,
    request_data: ChatMessageRequest,
    request: Request
):
    """
    Send a message and get AI response (streaming via SSE)

    Args:
        chat_id: Chat ID
        request_data: Message request data

    Returns:
        SSE stream with AI response
    """
    try:
        chat_service = request.app.state.chat_service

        # Verify chat exists
        chat = await chat_service.get_chat(chat_id)
        if not chat:
            raise_not_found(f"Chat '{chat_id}' not found")

        async def event_generator():
            """Generate SSE events for streaming response"""
            try:
                # Send metadata
                yield {
                    "event": "metadata",
                    "data": json.dumps({
                        "chat_id": chat_id,
                        "user_message": request_data.message,
                        "collections": chat.collection_ids
                    })
                }

                # Save user message first
                from database.connection import get_db_session_context
                from repository.chat import ChatMessageRepository

                with get_db_session_context() as session:
                    message_repo = ChatMessageRepository(session)
                    user_msg = message_repo.add_message(
                        chat_id=chat_id,
                        role="user",
                        content=request_data.message
                    )

                # Send user message saved event
                yield {
                    "event": "user_message",
                    "data": json.dumps({
                        "message_id": user_msg.id,
                        "content": request_data.message
                    })
                }

                # Retrieve relevant documents
                yield {
                    "event": "status",
                    "data": json.dumps({"status": "retrieving_documents"})
                }

                relevant_docs = await chat_service._retrieve_from_multiple_collections(
                    request_data.message,
                    chat.collection_ids,
                    top_k_per_collection=3
                )

                # Send sources found
                sources = chat_service._format_sources(relevant_docs)
                yield {
                    "event": "sources",
                    "data": json.dumps({
                        "sources": [source.dict() for source in sources],
                        "count": len(sources)
                    })
                }

                # Generate AI response
                yield {
                    "event": "status",
                    "data": json.dumps({"status": "generating_response"})
                }

                # Format context and get conversation history
                context = chat_service._format_context(relevant_docs)

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

                # Stream the LLM response
                from rag.prompt_templates import get_rag_prompt
                prompt = get_rag_prompt()

                # Create streaming chain
                chain = prompt | chat_service.llm

                # Stream response chunks
                full_response = ""
                async for chunk in chain.astream({
                    "context": full_context,
                    "question": request_data.message
                }):
                    content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    if content:
                        full_response += content
                        yield {
                            "event": "content",
                            "data": json.dumps({"content": content})
                        }

                # Save complete AI response
                with get_db_session_context() as session:
                    message_repo = ChatMessageRepository(session)
                    ai_msg = message_repo.add_message(
                        chat_id=chat_id,
                        role="assistant",
                        content=full_response,
                        sources=json.dumps([source.dict() for source in sources]),
                        metadata=json.dumps({
                            "model": chat_service.config.openai_model_name,
                            "sources_count": len(sources),
                            "collections_searched": chat.collection_ids
                        })
                    )

                # Send completion event
                yield {
                    "event": "done",
                    "data": json.dumps({
                        "message_id": ai_msg.id,
                        "sources_count": len(sources),
                        "total_content_length": len(full_response)
                    })
                }

            except Exception as e:
                logger.error(f"Error in streaming response: {e}")
                yield {
                    "event": "error",
                    "data": json.dumps({
                        "message": f"Error generating response: {str(e)}"
                    })
                }

        return EventSourceResponse(event_generator())

    except Exception as e:
        logger.error(f"Failed to start streaming response: {e}")
        raise_internal_error(f"Failed to start streaming response: {str(e)}")
