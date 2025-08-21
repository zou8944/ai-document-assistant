"""
Application state management with type safety.
"""

from dataclasses import dataclass

from fastapi import FastAPI, Request

from services.chat_service import ChatService
from services.collection_service import CollectionService
from services.document_service import DocumentService
from services.enhanced_chat_service import EnhancedChatService
from services.query_service import QueryService
from services.settings_service import SettingsService
from services.task_service import TaskService


@dataclass
class AppState:
    # Core services - all required after initialization
    chat_service: ChatService
    enhanced_chat_service: EnhancedChatService
    document_service: DocumentService
    query_service: QueryService
    collection_service: CollectionService
    settings_service: SettingsService
    task_service: TaskService


def set_app_state(app: FastAPI, state: AppState):
    app.state.app_state = state


def get_app_state(request: Request) -> AppState:
    return request.app.state.app_state
