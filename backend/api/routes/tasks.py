"""
Task management routes.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from api.response_utils import (
    raise_not_found,
    success_response,
)
from api.state import get_app_state

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, request: Request):
    """
    Get task status and statistics
    """
    task_service = get_app_state(request).task_service

    task = await task_service.get_task(task_id)
    if not task:
        raise_not_found(f"Task '{task_id}' not found")

    return success_response(data=task)


@router.get("/tasks/{task_id}/stream")
async def stream_task_progress(task_id: str, request: Request):
    """
    Stream task progress and logs using Server-Sent Events (SSE)
    """
    task_service = get_app_state(request).task_service

    # Verify task exists
    task = await task_service.get_task(task_id)
    if not task:
        raise_not_found(f"Task '{task_id}' not found")
        return

    async def event_generator():
        """Generate SSE events for task progress"""
        # Send initial metadata
        yield {
            "event": "metadata",
            "data": json.dumps({
                "task_id": task_id,
                "type": task.type,
                "collection_id": task.collection_id
            })
        }

        last_progress = -1
        offset = 0
        while True:
            # Get current task status
            current_task = await task_service.get_task(task_id)
            task_logs = await task_service.get_task_logs(task_id, limit=100, offset=offset)
            assert current_task

            # Send progress update if changed
            current_progress = current_task.progress_percentage or 0
            if current_progress != last_progress:
                yield {
                    "event": "progress",
                    "data": json.dumps({
                        "percentage": current_progress,
                        "stats": current_task.stats
                    })
                }
                last_progress = current_progress

            # send task logs
            for log in task_logs:
                yield {
                    "event": "log",
                    "data": json.dumps({
                        "level": log.level,
                        "message": log.message,
                        "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                        "details": json.loads(log.details) if log.details else {}
                    })
                }
            offset += len(task_logs)

            # check if task is completed
            if current_task.status == "success":
                yield {
                    "event": "done",
                    "data": json.dumps({
                        "duration_ms": None  # Could calculate if needed
                    })
                }
                break
            elif current_task.status == "failed":
                yield {
                    "event": "error",
                    "data": json.dumps({
                        "message": current_task.error_message
                    })
                }
                break

            # Wait before next check
            await asyncio.sleep(1.0)

    return EventSourceResponse(event_generator())


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, request: Request):
    task_service = get_app_state(request).task_service

    await task_service.cancel_task(task_id)
    return success_response()


@router.get("/tasks")
async def list_tasks(
    request: Request,
    collection_id: str,
):
    app_state = get_app_state(request)
    task_service = app_state.task_service

    tasks = task_service.list_task_responses(collection_id)
    return success_response(data={
        "tasks": tasks,
    })
