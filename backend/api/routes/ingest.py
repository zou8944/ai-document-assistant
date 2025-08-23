"""
Data ingestion routes for files and URLs.
"""

import logging

from fastapi import APIRouter, Request, status

from api.response_utils import (
    raise_bad_request,
    raise_internal_error,
    raise_not_found,
    success_response,
)
from api.state import get_app_state
from models.requests import IngestFilesRequest, IngestUrlsRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/collections/{collection_id}/ingest/folder", status_code=status.HTTP_202_ACCEPTED)
async def ingest_files(
    collection_id: str,
    request_data: IngestFilesRequest,
    request: Request
):
    """
    Ingest local files into a collection

    Args:
        collection_id: Target collection ID
        request_data: File ingestion request data

    Returns:
        Task information for tracking progress
    """
    try:
        # Validate collection exists
        app_state = get_app_state(request)

        collection_service = app_state.collection_service
        collection = await collection_service.get_collection(collection_id)

        if not collection:
            raise_not_found(f"Collection '{collection_id}' not found")

        # Validate files list
        if not request_data.files:
            raise_bad_request("Files list cannot be empty")

        # Create task
        app_state = get_app_state(request)

        task_service = app_state.task_service
        task = await task_service.create_task(
            task_type="ingest_files",
            collection_id=collection_id,
            input_params={"files": request_data.files}
        )

        logger.info(f"Created file ingestion task {task.task_id} for collection {collection_id}")

        return success_response(data={
            "task_id": task.task_id,
            "status": task.status
        })

    except Exception as e:
        logger.error(f"Failed to start file ingestion: {e}")
        raise_internal_error(f"Failed to start file ingestion: {str(e)}")


@router.post("/collections/{collection_id}/ingest/urls", status_code=status.HTTP_202_ACCEPTED)
async def ingest_urls(
    collection_id: str,
    request_data: IngestUrlsRequest,
    request: Request
):
    """
    Ingest URLs into a collection

    Args:
        collection_id: Target collection ID
        request_data: URL ingestion request data

    Returns:
        Task information for tracking progress
    """
    # Validate collection exists
    app_state = get_app_state(request)

    collection_service = app_state.collection_service
    collection = await collection_service.get_collection(collection_id)

    if not collection:
        raise_not_found(f"Collection '{collection_id}' not found")

    # Validate URLs list
    if not request_data.urls:
        raise_bad_request("URLs list cannot be empty")

    # Create task
    task_service = app_state.task_service
    task = await task_service.create_task(
        task_type="ingest_urls",
        collection_id=collection_id,
        input_params={
            "urls": request_data.urls,
            "max_depth": request_data.max_depth,
            "override": request_data.override
        }
    )

    logger.info(f"Created URL ingestion task {task.task_id} for collection {collection_id}")

    return success_response(data={
        "task_id": task.task_id,
        "status": task.status
    })
