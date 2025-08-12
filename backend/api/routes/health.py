"""
Health check routes.
"""

from fastapi import APIRouter, Request

from models.responses import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """Health check endpoint"""

    # Check if embeddings are available
    embeddings_available = True
    try:
        document_service = request.app.state.document_service
        if not document_service.embeddings:
            embeddings_available = False
    except Exception:
        embeddings_available = False

    # Check if Qdrant is available
    qdrant_available = True
    try:
        query_service = request.app.state.query_service
        # Try a simple operation
        await query_service.qdrant_manager.list_collections()
    except Exception:
        qdrant_available = False

    return HealthResponse(
        status="healthy",
        version="1.0.0",
        embeddings_available=embeddings_available,
        qdrant_available=qdrant_available
    )
