"""
FastAPI application main file.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load .env before any config/env reads; no-op if file doesn't exist
load_dotenv(Path(__file__).parent.parent / ".env")

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from api.middleware import UnifiedResponseMiddleware  # noqa: E402
from api.routes import chats, collections, documents, health, ingest, settings, tasks  # noqa: E402
from api.state import AppState, get_app_state_direct, set_app_state  # noqa: E402
from config import get_config  # noqa: E402

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""

    try:
        # Initialize configuration
        config = get_config()

        # Run database migrations
        logger.info("Running database migrations...")
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")

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
        try:
            state = get_app_state_direct(app)
        except AttributeError:
            state = None
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

# Add unified response middleware (inner)
app.add_middleware(UnifiedResponseMiddleware)

# Add CORS middleware last so it wraps everything and always injects CORS headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers with versioned API prefix
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(collections.router, prefix="/api/v1", tags=["collections"])
app.include_router(documents.router, prefix="/api/v1", tags=["documents"])
app.include_router(ingest.router, prefix="/api/v1", tags=["ingest"])
app.include_router(settings.router, prefix="/api/v1", tags=["settings"])
app.include_router(tasks.router, prefix="/api/v1", tags=["tasks"])
app.include_router(chats.router, prefix="/api/v1", tags=["chats"])


