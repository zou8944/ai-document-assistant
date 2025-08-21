"""
Task management routes.
"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from api.response_utils import (
    raise_internal_error,
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

    Args:
        task_id: Task ID

    Returns:
        Task information including status, progress, and statistics
    """
    try:
        app_state = get_app_state(request)

        task_service = app_state.task_service

        task = await task_service.get_task(task_id)

        if not task:
            raise_not_found(f"Task '{task_id}' not found")

        return success_response(data=task)

    except Exception as e:
        logger.error(f"Failed to get task: {e}")
        raise_internal_error(f"Failed to get task: {str(e)}")


@router.get("/tasks/{task_id}/stream")
async def stream_task_progress(task_id: str, request: Request):
    """
    Stream task progress and logs using Server-Sent Events (SSE)

    Args:
        task_id: Task ID

    Returns:
        SSE stream with task progress and log events
    """
    try:
        app_state = get_app_state(request)

        task_service = app_state.task_service

        # Verify task exists
        task = await task_service.get_task(task_id)
        if not task:
            raise_not_found(f"Task '{task_id}' not found")

        async def event_generator():
            """Generate SSE events for task progress"""
            last_progress = -1
            last_log_count = 0

            # Send initial metadata
            yield {
                "event": "metadata",
                "data": json.dumps({
                    "task_id": task_id,
                    "type": task.type,
                    "collection_id": task.collection_id
                })
            }

            while True:
                try:
                    # Get current task status
                    current_task = await task_service.get_task(task_id)
                    if not current_task:
                        break

                    # Send progress update if changed
                    current_progress = current_task.progress.get("percentage", 0)
                    if current_progress != last_progress:
                        yield {
                            "event": "progress",
                            "data": json.dumps({
                                "percentage": current_progress,
                                "stats": current_task.stats
                            })
                        }
                        last_progress = current_progress

                    # Get task logs
                    from database.connection import get_db_session_context
                    from repository.task import TaskLogRepository

                    with get_db_session_context() as session:
                        log_repo = TaskLogRepository(session)

                        # Get new logs since last check
                        logs = log_repo.get_by_task(
                            task_id=task_id,
                            offset=last_log_count,
                            limit=10
                        )

                        # Send new log entries
                        for log in reversed(logs):  # Reverse to get chronological order
                            yield {
                                "event": "log",
                                "data": json.dumps({
                                    "level": log.level,
                                    "message": log.message,
                                    "timestamp": log.timestamp.isoformat(),
                                    "details": json.loads(log.details) if log.details else {}
                                })
                            }

                        last_log_count += len(logs)

                    # Check if task is completed
                    if current_task.status in ["success", "failed"]:
                        # Send final event
                        if current_task.status == "success":
                            yield {
                                "event": "done",
                                "data": json.dumps({
                                    "chunks_indexed": current_task.progress.get("chunks_indexed", 0),
                                    "duration_ms": None  # Could calculate if needed
                                })
                            }
                        else:
                            yield {
                                "event": "error",
                                "data": json.dumps({
                                    "message": current_task.error or "Task failed"
                                })
                            }
                        break

                    # Wait before next check
                    await asyncio.sleep(1.0)

                except Exception as e:
                    logger.error(f"Error in SSE stream: {e}")
                    yield {
                        "event": "error",
                        "data": json.dumps({
                            "message": f"Stream error: {str(e)}"
                        })
                    }
                    break

        return EventSourceResponse(event_generator())

    except Exception as e:
        logger.error(f"Failed to start task stream: {e}")
        raise_internal_error(f"Failed to start task stream: {str(e)}")


@router.get("/tasks/{task_id}/logs")
async def get_task_logs(
    task_id: str,
    request: Request,
    level: Optional[str] = None,
    offset: int = 0,
    limit: int = 100
):
    """
    Get task logs with optional filtering

    Args:
        task_id: Task ID
        level: Optional log level filter (debug, info, warning, error)
        offset: Offset for pagination
        limit: Limit for pagination

    Returns:
        List of task log entries
    """
    try:
        # Get logs using repository
        app_state = get_app_state(request)

        task_service = app_state.task_service

        # Verify task exists
        task = await task_service.get_task(task_id)
        if not task:
            raise_not_found(f"Task '{task_id}' not found")

        # Get logs using TaskLogRepository
        from database.connection import get_db_session_context
        from repository.task import TaskLogRepository

        with get_db_session_context() as session:
            log_repo = TaskLogRepository(session)

            logs = log_repo.get_by_task(
                task_id=task_id,
                level=level,
                offset=offset,
                limit=limit
            )

            total_count = log_repo.count_by_task(task_id, level)

            # Convert logs to response format
            log_data = []
            for log in logs:
                log_data.append({
                    "id": log.id,
                    "level": log.level,
                    "message": log.message,
                    "timestamp": log.timestamp.isoformat(),
                    "details": json.loads(log.details) if log.details else {}
                })

            return success_response(data={
                "logs": log_data,
                "total": total_count,
                "offset": offset,
                "limit": limit
            })

    except Exception as e:
        logger.error(f"Failed to get task logs: {e}")
        raise_internal_error(f"Failed to get task logs: {str(e)}")


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, request: Request):
    """
    Cancel a running task

    Args:
        task_id: Task ID

    Returns:
        Success status
    """
    try:
        app_state = get_app_state(request)

        task_service = app_state.task_service

        # Verify task exists
        task = await task_service.get_task(task_id)
        if not task:
            raise_not_found(f"Task '{task_id}' not found")

        # Only allow canceling pending or processing tasks
        if task.status not in ["pending", "processing"]:
            return success_response(data={
                "task_id": task_id,
                "cancelled": False,
                "message": f"Task is {task.status} and cannot be cancelled"
            })

        # Mark task as failed (cancellation)
        success = await task_service.mark_task_completed(
            task_id=task_id,
            success=False,
            error_message="Task cancelled by user"
        )

        if success:
            await task_service.add_task_log(
                task_id=task_id,
                level="warning",
                message="Task cancelled by user request"
            )

        return success_response(data={
            "task_id": task_id,
            "cancelled": success
        })

    except Exception as e:
        logger.error(f"Failed to cancel task: {e}")
        raise_internal_error(f"Failed to cancel task: {str(e)}")


@router.get("/tasks")
async def list_tasks(
    request: Request,
    status: Optional[str] = None,
    task_type: Optional[str] = None,
    collection_id: Optional[str] = None,
    offset: int = 0,
    limit: int = 50
):
    """
    List tasks with optional filtering

    Args:
        status: Optional status filter (pending, processing, success, failed)
        task_type: Optional type filter (ingest_files, ingest_urls)
        collection_id: Optional collection filter
        offset: Offset for pagination
        limit: Limit for pagination

    Returns:
        List of tasks
    """
    try:
        from database.connection import get_db_session_context
        from repository.task import TaskRepository

        with get_db_session_context() as session:
            repo = TaskRepository(session)

            # Get tasks with filters using repository method
            tasks = repo.list_tasks_with_filters(
                status=status,
                task_type=task_type,
                collection_id=collection_id,
                offset=offset,
                limit=limit
            )

            # Get total count for pagination
            total_count = repo.count_tasks_with_filters(
                status=status,
                task_type=task_type,
                collection_id=collection_id
            )

            # Convert to response format
            app_state = get_app_state(request)

            task_service = app_state.task_service
            task_data = []
            for task in tasks:
                task_response = task_service._to_response(task)
                task_data.append(task_response.dict())

            return success_response(data={
                "tasks": task_data,
                "offset": offset,
                "limit": limit,
                "total": total_count
            })

    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        raise_internal_error(f"Failed to list tasks: {str(e)}")
