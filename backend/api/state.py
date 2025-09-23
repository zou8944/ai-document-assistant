"""
Application state management with type safety.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import FastAPI, Request

from models.config import AppConfig
from services.chat_service import ChatService
from services.collection_service import CollectionService
from services.document_service import DocumentService
from services.llm_service import LLMService
from services.task_service import TaskService

logger = logging.getLogger(__name__)


@dataclass
class AppState:
    # Core services - all required after initialization
    chat_service: ChatService
    document_service: DocumentService
    collection_service: CollectionService
    task_service: TaskService

    @classmethod
    def create_from_config(cls, config: AppConfig) -> "AppState":
        """Create AppState with all services initialized from configuration."""
        try:
            # Initialize services with new configuration
            llm_service = LLMService(config)
            chat_service = ChatService(config, llm_service)
            document_service = DocumentService(config)
            collection_service = CollectionService(config, llm_service)
            task_service = TaskService(config, collection_service, llm_service)

            logger.info("AppState created successfully with new configuration")

            return cls(
                chat_service=chat_service,
                document_service=document_service,
                collection_service=collection_service,
                task_service=task_service,
            )
        except Exception as e:
            logger.error(f"Failed to create AppState: {e}")
            raise

    @classmethod
    def recreate_with_new_config(cls, config: AppConfig) -> "AppState":
        """Recreate AppState with new configuration and update global reference."""
        global _current_app_state

        # Close existing services if any
        if _current_app_state:
            try:
                _current_app_state.chat_service.close()
                _current_app_state.document_service.close()
                _current_app_state.collection_service.close()
                _current_app_state.task_service.close()
                logger.info("Closed previous services")
            except Exception as e:
                logger.warning(f"Error closing previous services: {e}")

        # Create new state
        new_state = cls.create_from_config(config)
        _current_app_state = new_state

        # Update FastAPI app state if available
        if _current_app:
            _current_app.state.app_state = new_state
            logger.info("Updated FastAPI app state with new configuration")

        return new_state

    def close(self):
        """Close all services and cleanup resources."""
        try:
            self.chat_service.close()
            self.document_service.close()
            self.collection_service.close()
            self.task_service.close()
            logger.info("All services closed successfully")
        except Exception as e:
            logger.error(f"Error closing services: {e}")


# Global references for state management
_current_app_state: Optional[AppState] = None
_current_app: Optional[FastAPI] = None


def set_app_state(app: FastAPI, state: AppState):
    """Set the application state for the FastAPI app."""
    global _current_app_state, _current_app
    app.state.app_state = state
    _current_app_state = state
    _current_app = app


def get_app_state(request: Request) -> AppState:
    """Get the application state from the request."""
    return request.app.state.app_state

def get_app_state_direct(app: FastAPI) -> AppState:
    return app.state.app_state
