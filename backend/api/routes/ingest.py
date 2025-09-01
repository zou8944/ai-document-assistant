"""
Data ingestion routes for files and URLs.
"""

import logging

from fastapi import APIRouter, Request, status

from api.state import get_app_state
from exception import HTTPBadRequestException, HTTPNotFoundException
from models.requests import IngestFilesRequest, IngestUrlsRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/collections/{collection_id}/ingest/files", status_code=status.HTTP_202_ACCEPTED)
async def ingest_files(
    collection_id: str,
    request_data: IngestFilesRequest,
    request: Request
):
    """
    Ingest local files into a collection
    """
    # Validate collection exists
    collection_service = get_app_state(request).collection_service
    task_service = get_app_state(request).task_service

    collection = await collection_service.get_collection(collection_id)
    if not collection:
        raise HTTPNotFoundException(f"Collection '{collection_id}' not found")

    # Validate files list
    if not request_data.files:
        raise HTTPBadRequestException("Files list cannot be empty")

    # Create task
    task = await task_service.create_task(
        task_type="ingest_files",
        collection_id=collection_id,
        input_params={"files": request_data.files}
    )

    logger.info(f"Created file ingestion task {task.task_id} for collection {collection_id}")

    return {
        "task_id": task.task_id,
        "status": task.status
    }


@router.post("/collections/{collection_id}/ingest/urls", status_code=status.HTTP_202_ACCEPTED)
async def ingest_urls(
    collection_id: str,
    request_data: IngestUrlsRequest,
    request: Request
):
    """
    Ingest URLs into a collection
    """
    # Validate collection exists
    collection_service = get_app_state(request).collection_service
    task_service = get_app_state(request).task_service

    collection = await collection_service.get_collection(collection_id)
    if not collection:
        raise HTTPNotFoundException(f"Collection '{collection_id}' not found")

    # Validate URLs list
    if not request_data.urls:
        raise HTTPBadRequestException("URLs list cannot be empty")

    # Create task
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

    return {
        "task_id": task.task_id,
        "status": task.status
    }
