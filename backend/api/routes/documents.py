"""
Document management routes.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query, Request

from api.response_utils import (
    raise_not_found,
    success_response,
)
from api.state import get_app_state

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/collections/{collection_id}/documents")
async def list_documents(
    collection_id: str,
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Page size"),
    search: Optional[str] = Query(None, description="Search term for document names"),
    status: Optional[str] = Query(None, description="Filter by document status")
):
    """
    List documents in a collection with pagination and filters

    Args:
        collection_id: Collection ID
        page: Page number (starts from 1)
        page_size: Number of documents per page
        search: Optional search term for document names
        status: Optional status filter (pending, processing, indexed, failed)
    """
    document_service = get_app_state(request).document_service

    result = await document_service.list_documents(
        collection_id=collection_id,
        page=page,
        page_size=page_size,
        search=search,
        status=status
    )

    return success_response(data=result)


@router.get("/collections/{collection_id}/documents/{document_id}")
async def get_document(
    collection_id: str,
    document_id: str,
    request: Request
):
    """Get a specific document"""
    document_service = get_app_state(request).document_service

    document = await document_service.get_document(collection_id, document_id)

    if not document:
        raise_not_found(f"Document '{document_id}' not found in collection '{collection_id}'")

    return success_response(data=document)


@router.delete("/collections/{collection_id}/documents/{document_id}")
async def delete_document(
    collection_id: str,
    document_id: str,
    request: Request
):
    """Delete a document and its associated chunks/vectors"""
    document_service = get_app_state(request).document_service

    success = await document_service.delete_document(collection_id, document_id)

    if not success:
        raise_not_found(f"Document '{document_id}' not found in collection '{collection_id}'")

    return success_response(data={"document_id": document_id, "deleted": True})


@router.get("/collections/{collection_id}/documents/{document_id}/download")
async def download_document(
    collection_id: str,
    document_id: str,
    request: Request
):
    """
    Download a document file (only for local files)
    """
    document_service = get_app_state(request).document_service

    file_response = await document_service.download_document(collection_id, document_id)

    if not file_response:
        raise_not_found(f"Document '{document_id}' not found in collection '{collection_id}'")

    return file_response
