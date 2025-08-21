"""
Collection management routes.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Request, status

from api.response_utils import (
    raise_bad_request,
    raise_conflict,
    raise_not_found,
    success_response,
)
from models.requests import (
    CreateCollectionRequest,
    DeleteCollectionRequest,
    UpdateCollectionRequest,
)
from models.responses import ListCollectionsResponseV1

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
    collection_service = request.app.state.collection_service

    collection = await collection_service.create_collection(
        collection_id=request_data.id,
        name=request_data.name,
        description=request_data.description
    )

    if not collection:
        raise_conflict(f"Collection with id '{request_data.id}' already exists")

    return success_response(data=collection)


@router.get("/collections")
async def list_collections(request: Request, search: Optional[str] = None):
    """
    List all available collections

    Args:
        search: Optional search keyword to filter collections
    """
    collection_service = request.app.state.collection_service

    collections = await collection_service.list_collections(search=search)

    response_data = ListCollectionsResponseV1(
        collections=collections,
        total=len(collections)
    )

    return success_response(data=response_data)


@router.get("/collections/{collection_id}")
async def get_collection(collection_id: str, request: Request):
    """Get information about a specific collection"""
    collection_service = request.app.state.collection_service

    collection = await collection_service.get_collection(collection_id)

    if not collection:
        raise_not_found(f"Collection '{collection_id}' not found")

    return success_response(data=collection)


@router.patch("/collections/{collection_id}")
async def update_collection(
    collection_id: str,
    request_data: UpdateCollectionRequest,
    request: Request
):
    """Update a collection"""
    collection_service = request.app.state.collection_service

    # Validate at least one field is provided
    if request_data.name is None and request_data.description is None:
        raise_bad_request("At least one field (name or description) must be provided")

    collection = await collection_service.update_collection(
        collection_id=collection_id,
        name=request_data.name,
        description=request_data.description
    )

    if not collection:
        raise_not_found(f"Collection '{collection_id}' not found")

    return success_response(data=collection)


@router.delete("/collections/{collection_id}")
async def delete_collection(collection_id: str, request: Request):
    """Delete a collection"""
    collection_service = request.app.state.collection_service

    success = await collection_service.delete_collection(collection_id)

    if not success:
        raise_not_found(f"Collection '{collection_id}' not found")

    return success_response(data={})


# Legacy endpoints for backward compatibility
@router.delete("/collections")
async def delete_collection_legacy(
    request_data: DeleteCollectionRequest,
    request: Request
):
    """Delete a collection (legacy endpoint)"""
    collection_service = request.app.state.collection_service

    success = await collection_service.delete_collection(request_data.collection_name)

    if success:
        response_data = {
            "collection_name": request_data.collection_name,
            "deleted": True
        }
        return success_response(
            data=response_data,
            message=f"Collection '{request_data.collection_name}' deleted successfully"
        )
    else:
        raise_not_found(f"Collection '{request_data.collection_name}' not found")
