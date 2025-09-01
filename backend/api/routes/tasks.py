"""
Task management routes.
"""

import logging

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from api.state import get_app_state

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, request: Request):
    """
    Get task status and statistics
    """
    task_service = get_app_state(request).task_service

    return await task_service.get_task(task_id)


@router.get("/tasks/{task_id}/stream")
async def stream_task_progress(task_id: str, request: Request):
    """
    Stream task progress and logs using Server-Sent Events (SSE)
    """
    task_service = get_app_state(request).task_service

    return EventSourceResponse(task_service.get_task_stream_generator(task_id))


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, request: Request):
    task_service = get_app_state(request).task_service

    await task_service.cancel_task(task_id)


@router.get("/tasks")
async def list_tasks(
    request: Request,
    collection_id: str,
):
    app_state = get_app_state(request)
    task_service = app_state.task_service

    tasks = await task_service.list_task_responses(collection_id)
    return {
        "tasks": tasks,
    }
