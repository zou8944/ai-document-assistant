"""
Task management routes.
"""

import logging

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from api.state import get_app_state
from exception import HTTPBadRequestException

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


@router.get("/tasks/{task_id}/logs")
async def get_task_logs(
    task_id: str,
    request: Request,
    limit: int | None = None,
    offset: int = 0,
):
    """
    Get task logs (non-streaming, for historical viewing).
    If limit is omitted, returns all logs.
    """
    task_service = get_app_state(request).task_service

    logs = await task_service.get_task_logs(task_id, limit=limit, offset=offset)
    total = task_service.task_log_repo.count_by_task(task_id)
    return {"logs": logs, "total": total}


@router.post("/tasks/{task_id}/stop")
async def stop_task(task_id: str, request: Request):
    """
    Gracefully stop a running task
    """
    task_service = get_app_state(request).task_service

    success = await task_service.stop_task(task_id)
    if not success:
        raise HTTPBadRequestException("任务不存在或不在执行中")
    return {"success": True}


@router.post("/tasks/{task_id}/restart")
async def restart_task(task_id: str, request: Request):
    """
    Restart a completed or stopped task from scratch
    """
    task_service = get_app_state(request).task_service

    return await task_service.restart_task(task_id)


@router.post("/tasks/{task_id}/cleanup")
async def cleanup_task(task_id: str, request: Request):
    """
    Cleanup all resources produced by a task and reset it to pending
    """
    task_service = get_app_state(request).task_service

    success = await task_service.cleanup_task(task_id)
    return {"success": success}


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, request: Request, cleanup_resources: bool = False):
    """
    Permanently delete a task. Set cleanup_resources=true to also remove
    documents, vectors and crawl cache produced by the task.
    """
    task_service = get_app_state(request).task_service

    success = await task_service.delete_task(task_id, cleanup_resources)
    if not success:
        raise HTTPBadRequestException("任务不存在")
    return {"success": True}


@router.get("/tasks")
async def list_tasks(
    request: Request,
    collection_id: str | None = None,
    status: str | None = None,
    task_type: str | None = None,
):
    """
    List tasks with optional filters
    """
    app_state = get_app_state(request)
    task_service = app_state.task_service

    if collection_id:
        tasks = await task_service.list_task_responses(collection_id)
    else:
        tasks = task_service.task_repo.list_tasks_with_filters(
            status=status, task_type=task_type, limit=200
        )
        tasks = [task_service._to_response(t) for t in tasks]

    return {"tasks": tasks}


@router.post("/tasks/restart-pending")
async def restart_pending_tasks(request: Request):
    """
    Restart all failed tasks.
    Pending tasks are already in the worker queue (re-queued at startup).
    """
    task_service = get_app_state(request).task_service

    restarted = []
    failed_tasks = task_service.task_repo.list_tasks_with_filters(status="failed")
    for task in failed_tasks:
        try:
            await task_service.restart_task(task.id)
            restarted.append(task.id)
        except Exception as e:
            logger.warning(f"Failed to restart task {task.id}: {e}")

    return {"restarted": restarted}
