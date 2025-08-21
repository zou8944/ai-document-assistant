"""
Health check routes.
"""

from fastapi import APIRouter, Request

from api.response_utils import success_response
from api.state import get_app_state

router = APIRouter()


class HealthData:
    """Health check response data"""
    def __init__(self, status: str, version: str, embeddings_available: bool, chroma_available: bool):
        self.status = status
        self.version = version
        self.embeddings_available = embeddings_available
        self.chroma_available = chroma_available


@router.get("/health")
async def health_check(request: Request):
    """
    Health check endpoint

    Returns system health status including service availability.
    """

    # Check if embeddings are available
    embeddings_available = True
    try:
        app_state = get_app_state(request)

        document_service = app_state.document_service
        if not document_service.embeddings:
            embeddings_available = False
    except Exception:
        embeddings_available = False

    # Check if Chroma is available
    chroma_available = True
    try:
        app_state = get_app_state(request)

        query_service = app_state.query_service
        # Try a simple operation
        await query_service.chroma_manager.list_collections()
    except Exception:
        chroma_available = False

    health_data = {
        "status": "ok",
        "version": "0.1.0",
        "embeddings_available": embeddings_available,
        "chroma_available": chroma_available
    }

    return success_response(data=health_data)
