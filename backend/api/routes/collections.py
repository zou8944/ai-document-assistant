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

    success = await collection_service.delete_collection(collection_id)

    if not success:
        raise HTTPNotFoundException(f"Collection '{collection_id}' not found")

    return {}
