"""Stop endpoint for in-flight agent chat requests."""

from fastapi import APIRouter, HTTPException

from chat.agent_service import get_cancel_token

router = APIRouter(prefix="/chats", tags=["chat"])


@router.post("/{chat_id}/messages/stop")
async def stop_generation(chat_id: str, message_id: str):
    """Cancel an in-flight agent chat generation.

    The frontend must include the `message_id` that was pre-assigned
    when the SSE stream started.
    """
    token = get_cancel_token(chat_id, message_id)
    if token is None:
        raise HTTPException(status_code=404, detail="No active generation found")

    token.cancel()
    return {"status": "cancelled"}
