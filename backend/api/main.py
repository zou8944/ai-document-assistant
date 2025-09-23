"""
FastAPI application main file.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.middleware import UnifiedResponseMiddleware
from api.routes import chats, collections, documents, health, ingest, settings, tasks
from api.state import AppState, get_app_state_direct, set_app_state
from config import get_config
from database.connection import create_tables

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""

    try:
        # Initialize configuration
        config = get_config()

        # Initialize database
        logger.info("Initializing database...")
        create_tables()

        # Initialize services
        logger.info("Initializing services...")

        logger.info("Services initialized successfully")

        state = AppState.create_from_config(config)
        set_app_state(app, state)

        # Start task workers
        logger.info("Starting task workers...")
        await state.task_service.start_workers()

        yield

    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise
    finally:
        # Cleanup services
        logger.info("Shutting down services...")
        state = get_app_state_direct(app)
        if state:
            await state.task_service.stop_workers()
            state.chat_service.close()
            state.document_service.close()
            state.collection_service.close()

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

# Add unified response middleware
app.add_middleware(UnifiedResponseMiddleware)


# Include routers with versioned API prefix
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(collections.router, prefix="/api/v1", tags=["collections"])
app.include_router(documents.router, prefix="/api/v1", tags=["documents"])
app.include_router(ingest.router, prefix="/api/v1", tags=["ingest"])
app.include_router(settings.router, prefix="/api/v1", tags=["settings"])
app.include_router(tasks.router, prefix="/api/v1", tags=["tasks"])
app.include_router(chats.router, prefix="/api/v1", tags=["chats"])


if __name__ == "__main__":
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="AI Document Assistant API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8888, help="Port to bind to (0 for auto)")
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
