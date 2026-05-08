"""
Application state management with type safety.
"""

import logging
from dataclasses import dataclass

from fastapi import FastAPI, Request

from chat.agent import AgentConfig
from chat.agent.llm.claude import ClaudeToolBackend
from chat.agent_service import AgentChatService
from chat.generation.claude_backend import ClaudeLLMService
from models.config import AppConfig
from repository.chat import ChatMessageRepository, ChatRepository
from repository.collection import CollectionRepository
from repository.document import DocumentRepository
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
    agent_chat_service: AgentChatService | None = None

    @classmethod
    def create_from_config(cls, config: AppConfig) -> "AppState":
        """Create AppState with all services initialized from configuration."""
        try:
            llm_service = LLMService(config)

            chat_repo = ChatRepository()
            chat_message_repo = ChatMessageRepository()
            document_repo = DocumentRepository()
            collection_repo = CollectionRepository()

            # Agent chat service (tool-use based RAG)
            agent_chat_service: AgentChatService | None = None
            try:
                deep_llm = ClaudeLLMService(
                    api_key=config.llm.anthropic_api_key,
                    model=config.llm.anthropic_chat_model,
                    base_url=config.llm.anthropic_base_url or None,
                )

                agent_backend = ClaudeToolBackend(
                    client=deep_llm.client,
                    model=config.llm.deep_model,
                )
                agent_fast_backend = ClaudeToolBackend(
                    client=deep_llm.client,
                    model=config.llm.fast_model,
                )
                agent_config = AgentConfig(
                    max_iterations=15,
                    context_window=200_000,
                    model="standard",
                    transcript_dir="./var/agent_transcripts",
                )
                agent_chat_service = AgentChatService(
                    backend=agent_backend,
                    fast_backend=agent_fast_backend,
                    config=agent_config,
                    chat_repo=chat_repo,
                    chat_message_repo=chat_message_repo,
                    document_repo=document_repo,
                    collection_repo=collection_repo,
                )
                logger.info("Agent chat service initialized successfully")
            except Exception as agent_err:
                logger.warning(
                    f"Failed to initialize agent chat service: {agent_err}"
                )

            chat_service = ChatService()
            document_service = DocumentService(config)
            collection_service = CollectionService(config, llm_service)
            task_service = TaskService(
                config, collection_service, llm_service,
            )

            logger.info("AppState created successfully with new configuration")

            return cls(
                chat_service=chat_service,
                document_service=document_service,
                collection_service=collection_service,
                task_service=task_service,
                agent_chat_service=agent_chat_service,
            )
        except Exception as e:
            logger.error(f"Failed to create AppState: {e}")
            raise

    @classmethod
    def recreate_with_new_config(cls, config: AppConfig) -> "AppState":
        """Recreate AppState with new configuration and update global reference."""
        global _current_app_state

        if _current_app_state:
            try:
                _current_app_state.chat_service.close()
                _current_app_state.document_service.close()
                _current_app_state.collection_service.close()
                _current_app_state.task_service.close()
                logger.info("Closed previous services")
            except Exception as e:
                logger.warning(f"Error closing previous services: {e}")

        new_state = cls.create_from_config(config)
        _current_app_state = new_state

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


_current_app_state: AppState | None = None
_current_app: FastAPI | None = None


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
