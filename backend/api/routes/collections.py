"""
Collection management routes.
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from models.requests import DeleteCollectionRequest
from models.responses import DeleteCollectionResponse, ListCollectionsResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/collections", response_model=ListCollectionsResponse)
async def list_collections(request: Request):
    """List all available collections"""
    try:
        collection_service = request.app.state.collection_service

        collections = await collection_service.list_collections()

        return ListCollectionsResponse(collections=collections)

    except Exception as e:
        logger.error(f"Failed to list collections: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/collections", response_model=DeleteCollectionResponse)
async def delete_collection(
    request_data: DeleteCollectionRequest,
    request: Request
):
    """Delete a collection"""
    try:
        collection_service = request.app.state.collection_service

        success = await collection_service.delete_collection(request_data.collection_name)

        if success:
            return DeleteCollectionResponse(
                success=True,
                collection_name=request_data.collection_name,
                message=f"Collection '{request_data.collection_name}' deleted successfully"
            )
        else:
            return DeleteCollectionResponse(
                success=False,
                collection_name=request_data.collection_name,
                message=f"Failed to delete collection '{request_data.collection_name}'"
            )

    except Exception as e:
        logger.error(f"Failed to delete collection: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/collections/{collection_name}")
async def get_collection_info(collection_name: str, request: Request):
    """Get information about a specific collection"""
    try:
        collection_service = request.app.state.collection_service

        info = await collection_service.get_collection_info(collection_name)

        if not info:
            raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")

        return info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get collection info: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
