"""Trace/transcript routes for chat messages."""

import json
import logging

from fastapi import APIRouter, Request, status

from api.state import get_app_state
from exception import HTTPNotFoundException

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/chats/{chat_id}/messages/{message_id}/trace", status_code=status.HTTP_200_OK)
async def get_message_trace(chat_id: str, message_id: str, request: Request):
    """Get the full agent trace for a message.

    Returns the agent_trace JSON from ChatMessage.message_metadata.
    If the message has no agent_trace, returns 404.
    """
    chat_message_repo = get_app_state(request).chat_message_repo
    message = chat_message_repo.get_by_id(message_id)

    if message is None or message.chat_id != chat_id:
        raise HTTPNotFoundException(f"Message '{message_id}' not found in chat '{chat_id}'")

    try:
        metadata = json.loads(message.message_metadata or "{}")
    except json.JSONDecodeError:
        metadata = {}

    agent_trace = metadata.get("agent_trace")
    if agent_trace is None:
        raise HTTPNotFoundException(f"Message '{message_id}' has no agent trace")

    return agent_trace
