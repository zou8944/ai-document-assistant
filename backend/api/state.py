"""
Application state management with type safety.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import FastAPI, Request

from models.config import AppConfig
from chat.service import ChatService as NewChatService
from chat.context.assembler import ContextAssembler
from chat.retrieval.document_index import DocumentIndex
from chat.retrieval.chunk_index import ChunkIndex
from chat.retrieval.keyword_index import KeywordIndex
from chat.retrieval.orchestrator import RetrievalOrchestrator
from chat.generation.claude_backend import ClaudeLLMService
from chat.generation.openai_backend import OpenAILLMService
from services.chat_service import ChatService
from services.collection_service import CollectionService
from services.document_service import DocumentService
from services.llm_service import LLMService
from services.task_service import TaskService
from repository.chat import ChatRepository, ChatMessageRepository

logger = logging.getLogger(__name__)


@dataclass
class AppState:
    # Core services - all required after initialization
    chat_service: ChatService
    document_service: DocumentService
    collection_service: CollectionService
    task_service: TaskService
    new_chat_service: Optional[NewChatService] = None

    @classmethod
    def create_from_config(cls, config: AppConfig) -> "AppState":
        """Create AppState with all services initialized from configuration."""
        try:
            llm_service = LLMService(config)

            # Create new chat module components
            from vector_store.chroma_client import create_chroma_manager

            document_index = DocumentIndex()
            chunk_index = ChunkIndex(
                chroma_client=create_chroma_manager(),
                embedding_model=llm_service.embeddings,
            )
            keyword_index = KeywordIndex()
            orchestrator = RetrievalOrchestrator(
                document_index=document_index,
                chunk_index=chunk_index,
                keyword_index=keyword_index,
            )
            assembler = ContextAssembler()

            # Multi-model configuration - wrapped in try/except so failure
            # of new chat service does not prevent app from starting
            new_chat_service: Optional[NewChatService] = None
            try:
                router_llm = OpenAILLMService(
                    api_key=config.llm.api_key,
                    model=config.llm.router_model,
                    base_url=config.llm.base_url,
                )
                fast_llm = OpenAILLMService(
                    api_key=config.llm.api_key,
                    model=config.llm.fast_model,
                    base_url=config.llm.base_url,
                )
                standard_llm = OpenAILLMService(
                    api_key=config.llm.api_key,
                    model=config.llm.standard_model,
                    base_url=config.llm.base_url,
                )
                deep_llm = ClaudeLLMService(
                    api_key=config.llm.anthropic_api_key,
                    model=config.llm.anthropic_chat_model,
                    base_url=config.llm.anthropic_base_url or None,
                )

                chat_repo = ChatRepository()
                chat_message_repo = ChatMessageRepository()

                new_chat_service = NewChatService(
                    router_llm=router_llm,
                    fast_llm=fast_llm,
                    standard_llm=standard_llm,
                    deep_llm=deep_llm,
                    orchestrator=orchestrator,
                    assembler=assembler,
                    chat_repo=chat_repo,
                    chat_message_repo=chat_message_repo,
                )
                logger.info("New chat service initialized successfully")
            except Exception as e:
                logger.warning(
                    f"Failed to initialize new chat service (will fall back to legacy): {e}"
                )

            # Legacy services for backward compatibility
            chat_service = ChatService(config, llm_service)
            document_service = DocumentService(config)
            collection_service = CollectionService(config, llm_service)
            task_service = TaskService(
                config, collection_service, llm_service,
                document_index=document_index,
                keyword_index=keyword_index,
            )

            logger.info("AppState created successfully with new configuration")

            return cls(
                chat_service=chat_service,
                document_service=document_service,
                collection_service=collection_service,
                task_service=task_service,
                new_chat_service=new_chat_service,
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
            if self.new_chat_service:
                try:
                    self.new_chat_service.close()
                except Exception as e:
                    logger.warning(f"Error closing new chat service: {e}")
            self.chat_service.close()
            self.document_service.close()
            self.collection_service.close()
            self.task_service.close()
            logger.info("All services closed successfully")
        except Exception as e:
            logger.error(f"Error closing services: {e}")


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
