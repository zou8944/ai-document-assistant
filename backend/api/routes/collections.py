"""
Collection management routes.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Request, status
from fastapi.responses import FileResponse

from api.state import get_app_state
from exception import HTTPBadRequestException, HTTPConflictException, HTTPNotFoundException
from models.config import AppConfig
from models.requests import (
    CreateCollectionRequest,
    UpdateCollectionRequest,
)
from models.responses import ListCollectionsResponseV1, SitemapResponse

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


@router.get("/collections/{collection_id}/sitemap")
async def get_collection_sitemap(collection_id: str, request: Request):
    """Get the AI-generated sitemap for a collection"""
    collection_service = get_app_state(request).collection_service

    sitemap_json = await collection_service.get_sitemap(collection_id)
    if sitemap_json is None:
        raise HTTPNotFoundException(f"Collection '{collection_id}' not found")

    return SitemapResponse(sitemap_json=sitemap_json)


@router.get("/collections/{collection_id}/static/{path:path}")
async def serve_static_file(collection_id: str, path: str, request: Request):
    """Serve static assets from the crawl cache directory"""
    app_state = get_app_state(request)

    # Verify collection exists
    collection = await app_state.collection_service.get_collection(collection_id)
    if not collection:
        raise HTTPNotFoundException(f"Collection '{collection_id}' not found")

    # Find domain_key from any document in this collection that has a source_path (crawled doc)
    from repository.document import DocumentRepository
    doc_repo = DocumentRepository()
    docs = doc_repo.get_by_collection(collection_id)

    domain_key = None
    for doc in docs:
        if doc.source_path and doc.uri:
            from urllib.parse import urlparse
            domain_key = urlparse(doc.uri).netloc.lower().replace(":", "_")
            break

    if not domain_key:
        raise HTTPNotFoundException("No crawled documents found in this collection")

    cache_root = AppConfig.get_crawl_cache_dir()
    file_path = cache_root / domain_key / path

    if not file_path.exists() or not file_path.is_file():
        raise HTTPNotFoundException(f"Static file not found: {path}")

    return FileResponse(str(file_path))
