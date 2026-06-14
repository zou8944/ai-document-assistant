"""
Collection management routes.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Request, status

from api.state import get_app_state
from exception import HTTPBadRequestException, HTTPConflictException, HTTPNotFoundException
from models.requests import (
    CreateCollectionRequest,
    RecategorizeRequest,
    UpdateCollectionRequest,
)
from models.responses import ListCollectionsResponseV1, ReadmeResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/collections", status_code=status.HTTP_201_CREATED)
async def create_collection(
    request_data: CreateCollectionRequest,
    request: Request
):
    """
    Create a new collection

    Args:
        request_data: Collection creation data
    """
    app_state = get_app_state(request)

    collection_service = app_state.collection_service

    collection = await collection_service.create_collection(
        collection_id=request_data.id,
        name=request_data.name,
        description=request_data.description
    )

    if not collection:
        raise HTTPConflictException(f"Collection with id '{request_data.id}' already exists")

    return collection


@router.get("/collections")
async def list_collections(request: Request, search: Optional[str] = None):
    """
    List all available collections

    Args:
        search: Optional search keyword to filter collections
    """
    app_state = get_app_state(request)

    collection_service = app_state.collection_service

    collections = await collection_service.list_collections(search=search)

    response_data = ListCollectionsResponseV1(
        collections=collections,
        total=len(collections)
    )

    return response_data


@router.get("/collections/{collection_id}")
async def get_collection(collection_id: str, request: Request):
    """Get information about a specific collection"""
    app_state = get_app_state(request)

    collection_service = app_state.collection_service

    collection = await collection_service.get_collection(collection_id)

    if not collection:
        raise HTTPNotFoundException(f"Collection '{collection_id}' not found")

    return collection


@router.patch("/collections/{collection_id}")
async def update_collection(
    collection_id: str,
    request_data: UpdateCollectionRequest,
    request: Request
):
    """Update a collection"""
    app_state = get_app_state(request)

    collection_service = app_state.collection_service

    # Validate at least one field is provided
    if request_data.name is None and request_data.description is None:
        raise HTTPBadRequestException("At least one field (name or description) must be provided")

    collection = await collection_service.update_collection(
        collection_id=collection_id,
        name=request_data.name,
        description=request_data.description
    )

    if not collection:
        raise HTTPNotFoundException(f"Collection '{collection_id}' not found")

    return collection


@router.delete("/collections/{collection_id}")
async def delete_collection(collection_id: str, request: Request):
    """Delete a collection"""
    app_state = get_app_state(request)

    collection_service = app_state.collection_service

    await collection_service.delete_collection(collection_id)

    return {}


@router.post("/collections/{collection_id}/clear")
async def clear_collection_data(collection_id: str, request: Request):
    """Clear all data in a collection but keep the collection itself"""
    app_state = get_app_state(request)
    collection_service = app_state.collection_service

    collection = await collection_service.get_collection(collection_id)
    if not collection:
        raise HTTPNotFoundException(f"Collection '{collection_id}' not found")

    await collection_service.clear_collection(collection_id)
    return {}


@router.get("/collections/{collection_id}/readme")
async def get_collection_readme(collection_id: str, request: Request):
    """Get the AI-generated README and categories for a collection"""
    collection_service = get_app_state(request).collection_service

    readme_content, categories_json, readme_content_zh, categories_json_zh, source_language = await collection_service.get_readme(collection_id)
    if readme_content is None:
        raise HTTPNotFoundException(f"Collection '{collection_id}' not found")

    return ReadmeResponse(
        readme_content=readme_content,
        categories_json=categories_json,
        readme_content_zh=readme_content_zh,
        categories_json_zh=categories_json_zh,
        source_language=source_language,
    )


@router.post("/collections/{collection_id}/reindex", status_code=status.HTTP_202_ACCEPTED)
async def reindex_collection(collection_id: str, request: Request):
    """Trigger re-indexing of all documents in a collection with current chunking parameters."""
    app_state = get_app_state(request)
    task_service = app_state.task_service

    # Verify collection exists and has documents
    collection = await app_state.collection_service.get_collection(collection_id)
    if not collection:
        raise HTTPNotFoundException(f"Collection '{collection_id}' not found")
    if collection.document_count == 0:
        raise HTTPBadRequestException(f"Collection '{collection_id}' has no documents to re-index")

    task = await task_service.create_task(
        task_type="reindex_collection",
        collection_id=collection_id,
        input_params={},
    )

    logger.info(f"Created reindex task {task.task_id} for collection {collection_id}")

    return {"task_id": task.task_id, "status": task.status}


@router.post("/collections/{collection_id}/regenerate-readme", status_code=status.HTTP_202_ACCEPTED)
async def regenerate_readme(collection_id: str, request: Request):
    """Re-categorize all documents and regenerate README without re-crawling."""
    app_state = get_app_state(request)
    task_service = app_state.task_service

    # Verify collection exists and has documents
    collection = await app_state.collection_service.get_collection(collection_id)
    if not collection:
        raise HTTPNotFoundException(f"Collection '{collection_id}' not found")
    if collection.document_count == 0:
        raise HTTPBadRequestException(f"Collection '{collection_id}' has no documents")

    task = await task_service.create_task(
        task_type="regenerate_readme",
        collection_id=collection_id,
        input_params={"title": "重新生成 README"},
    )

    logger.info(f"Created regenerate_readme task {task.task_id} for collection {collection_id}")

    return {"task_id": task.task_id, "status": task.status}


@router.post("/collections/{collection_id}/recategorize", status_code=status.HTTP_202_ACCEPTED)
async def recategorize_collection(
    collection_id: str,
    request_data: RecategorizeRequest,
    request: Request,
):
    """Re-categorize all documents in a collection without re-crawling."""
    app_state = get_app_state(request)
    task_service = app_state.task_service

    # Verify collection exists and has documents
    collection = await app_state.collection_service.get_collection(collection_id)
    if not collection:
        raise HTTPNotFoundException(f"Collection '{collection_id}' not found")
    if collection.document_count == 0:
        raise HTTPBadRequestException(f"Collection '{collection_id}' has no documents")

    task = await task_service.create_task(
        task_type="recategorize",
        collection_id=collection_id,
        input_params={
            "categorize_mode": request_data.categorize_mode,
            "title": "重新分类文档",
        },
    )

    logger.info(f"Created recategorize task {task.task_id} for collection {collection_id}")

    return {"task_id": task.task_id, "status": task.status}
