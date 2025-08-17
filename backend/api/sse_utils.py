"""
Server-Sent Events (SSE) utilities for streaming responses.
"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from fastapi.responses import StreamingResponse

from models.api_response import EventType, StreamEvent

logger = logging.getLogger(__name__)


def create_sse_response(event_generator: AsyncGenerator[StreamEvent, None]) -> StreamingResponse:
    """
    Create a Server-Sent Events streaming response.

    Args:
        event_generator: Async generator that yields StreamEvent objects

    Returns:
        StreamingResponse configured for SSE
    """

    async def stream_events():
        """Stream events in SSE format"""
        try:
            async for event in event_generator:
                # Format as SSE
                sse_data = format_sse_event(event.event, event.data)
                yield sse_data

        except Exception as e:
            logger.error(f"Error in SSE stream: {e}")
            # Send error event
            error_event = StreamEvent(
                event=EventType.ERROR,
                data={"error": str(e)}
            )
            sse_data = format_sse_event(error_event.event, error_event.data)
            yield sse_data

    return StreamingResponse(
        stream_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


def format_sse_event(event_type: str, data: dict[str, Any]) -> str:
    """
    Format data as Server-Sent Event.

    Args:
        event_type: Event type name
        data: Event data dictionary

    Returns:
        Formatted SSE string
    """
    # Convert data to JSON
    json_data = json.dumps(data, ensure_ascii=False)

    # Format as SSE
    sse_lines = []
    if event_type:
        sse_lines.append(f"event: {event_type}")
    sse_lines.append(f"data: {json_data}")
    sse_lines.append("")  # Empty line to end the event

    return "\n".join(sse_lines) + "\n"


async def create_task_progress_stream(
    task_id: str,
    task_runner: Any
) -> AsyncGenerator[StreamEvent, None]:
    """
    Create a progress stream for a task.

    Args:
        task_id: Task identifier
        task_runner: Object that manages task execution

    Yields:
        StreamEvent objects for task progress
    """
    try:
        # Send initial metadata
        yield StreamEvent(
            event=EventType.METADATA,
            data={"task_id": task_id, "status": "started"}
        )

        # Monitor task progress
        while True:
            # Get task status from runner
            status = await task_runner.get_task_status(task_id)

            if not status:
                break

            # Send progress update
            if status.get("progress"):
                yield StreamEvent(
                    event=EventType.PROGRESS,
                    data=status["progress"]
                )

            # Send logs if available
            if status.get("logs"):
                for log in status["logs"]:
                    yield StreamEvent(
                        event=EventType.LOG,
                        data=log
                    )

            # Check if task is complete
            if status.get("status") in ["success", "failed"]:
                if status["status"] == "failed":
                    yield StreamEvent(
                        event=EventType.ERROR,
                        data={"error": status.get("error", "Task failed")}
                    )
                else:
                    yield StreamEvent(
                        event=EventType.DONE,
                        data=status.get("result", {})
                    )
                break

            # Wait a bit before next check
            await asyncio.sleep(0.5)

    except Exception as e:
        logger.error(f"Error in task progress stream: {e}")
        yield StreamEvent(
            event=EventType.ERROR,
            data={"error": str(e)}
        )


async def create_chat_stream(
    message: str,
    chat_service: Any,
    chat_id: str,
    include_sources: bool = True
) -> AsyncGenerator[StreamEvent, None]:
    """
    Create a chat response stream.

    Args:
        message: User message
        chat_service: Chat service instance
        chat_id: Chat identifier
        include_sources: Whether to include source references

    Yields:
        StreamEvent objects for chat response
    """
    try:
        # Send metadata with message ID
        message_id = f"msg_{hash(message)}"  # Simplified ID generation
        yield StreamEvent(
            event=EventType.METADATA,
            data={"message_id": message_id}
        )

        # Get streaming response from chat service
        async for chunk in chat_service.stream_response(message, chat_id):
            if chunk.get("type") == "content":
                yield StreamEvent(
                    event=EventType.CONTENT,
                    data={"content": chunk["content"]}
                )
            elif chunk.get("type") == "sources" and include_sources:
                yield StreamEvent(
                    event=EventType.SOURCES,
                    data={"sources": chunk["sources"]}
                )

        # Send done event
        yield StreamEvent(
            event=EventType.DONE,
            data={}
        )

    except Exception as e:
        logger.error(f"Error in chat stream: {e}")
        yield StreamEvent(
            event=EventType.ERROR,
            data={"error": str(e)}
        )
