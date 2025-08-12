"""
FastAPI application main file.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import collections, crawler, files, health, query
from config import get_config
from services.collection_service import CollectionService
from services.document_service import DocumentService
from services.query_service import QueryService

logger = logging.getLogger(__name__)

# Global services (will be initialized in lifespan)
document_service: DocumentService
query_service: QueryService
collection_service: CollectionService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global document_service, query_service, collection_service

    try:
        # Initialize configuration
        config = get_config()

        # Initialize services
        logger.info("Initializing services...")
        document_service = DocumentService(config)
        query_service = QueryService(config)
        collection_service = CollectionService(config)

        logger.info("Services initialized successfully")

        # Store services in app state for access in routes
        app.state.document_service = document_service
        app.state.query_service = query_service
        app.state.collection_service = collection_service

        yield

    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise
    finally:
        # Cleanup services
        logger.info("Shutting down services...")

        if document_service:
            document_service.close()
        if query_service:
            query_service.close()
        if collection_service:
            collection_service.close()

        logger.info("Services shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="AI Document Assistant API",
    description="REST API for document processing and RAG-based questioning",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )



app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(files.router, prefix="/api", tags=["files"])
app.include_router(crawler.router, prefix="/api", tags=["crawler"])
app.include_router(query.router, prefix="/api", tags=["query"])
app.include_router(collections.router, prefix="/api", tags=["collections"])


if __name__ == "__main__":
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="AI Document Assistant API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=0, help="Port to bind to (0 for auto)")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes")
    parser.add_argument("--log-level", default="info", help="Log level")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info(f"Starting API server on {args.host}:{args.port}")

    uvicorn.run(
        "api.main:app",
        host=args.host,
        port=args.port,
        workers=args.workers,
        log_level=args.log_level,
        reload=False
    )
