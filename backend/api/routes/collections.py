"""
Collection management routes.
"""

import logging

from fastapi import APIRouter, Request

from api.response_utils import (
    raise_internal_error,
    raise_not_found,
    success_response,
)
from models.requests import DeleteCollectionRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/collections")
async def list_collections(request: Request, search: str = None):
    """
    List all available collections

    Args:
        search: Optional search keyword to filter collections
    """
    try:
        collection_service = request.app.state.collection_service

        collections = await collection_service.list_collections()

        # Apply search filter if provided
        if search:
            search_lower = search.lower()
            collections = [
                c for c in collections
                if search_lower in c.name.lower() or search_lower in (c.description or "").lower()
            ]

        response_data = {
            "collections": collections,
            "total": len(collections)
        }

        return success_response(data=response_data)

    except Exception as e:
        logger.error(f"Failed to list collections: {e}")
        raise_internal_error(f"Failed to list collections: {str(e)}")


@router.delete("/collections")
async def delete_collection(
    request_data: DeleteCollectionRequest,
    request: Request
):
    """Delete a collection"""
    try:
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

    except Exception as e:
        logger.error(f"Failed to delete collection: {e}")
        raise_internal_error(f"Failed to delete collection: {str(e)}")


@router.get("/collections/{collection_name}")
async def get_collection_info(collection_name: str, request: Request):
    """Get information about a specific collection"""
    try:
        collection_service = request.app.state.collection_service

        info = await collection_service.get_collection_info(collection_name)

        if not info:
            raise_not_found(f"Collection '{collection_name}' not found")

        return success_response(data=info)

    except Exception as e:
        logger.error(f"Failed to get collection info: {e}")
        raise_internal_error(f"Failed to get collection info: {str(e)}")
