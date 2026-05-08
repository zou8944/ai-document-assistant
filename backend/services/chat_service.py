"""
Chat service for managing conversations (CRUD only).
AI response generation has been moved to AgentChatService.
"""

import json
import logging
from typing import Optional

from models.dto import ChatDTO, ChatMessageDTO
from models.responses import ChatMessageResponse, ChatResponse
from repository.chat import ChatMessageRepository, ChatRepository

logger = logging.getLogger(__name__)


class ChatService:
    """Service for managing chat conversations (CRUD only)."""

    def __init__(self, config=None, llm_service=None):
        """Initialize chat service."""
        self.config = config
        self.chat_repo = ChatRepository()
        self.chat_message_repo = ChatMessageRepository()
        logger.info("ChatService initialized successfully")

    def _to_chat_response(self, chat: ChatDTO) -> ChatResponse:
        """Convert Chat model to response model"""
        assert chat.id
        assert chat.name
        return ChatResponse(
            chat_id=chat.id,
            name=chat.name,
            collection_ids=json.loads(chat.collection_ids) if chat.collection_ids else [],
            bound_collection_id=chat.bound_collection_id,
            message_count=chat.message_count or 0,
            created_at=chat.created_at.isoformat() if chat.created_at else "",
            updated_at=chat.updated_at.isoformat() if chat.updated_at else "",
            last_message_at=chat.last_message_at.isoformat() if chat.last_message_at else None
        )

    def _to_message_response(self, message: ChatMessageDTO) -> ChatMessageResponse:
        """Convert ChatMessage model to response model"""
        try:
            sources = json.loads(message.sources) if message.sources else []
        except json.JSONDecodeError:
            sources = []

        try:
            metadata = json.loads(message.message_metadata) if message.message_metadata else {}
        except json.JSONDecodeError:
            metadata = {}

        return ChatMessageResponse(
            message_id=message.id or "",
            chat_id=message.chat_id or "",
            role=message.role or "",
            content=message.content or "",
            sources=sources,
            metadata=metadata,
            created_at=message.created_at.isoformat() if message.created_at else ""
        )

    async def create_chat(self, name: str, collection_ids: list[str], bound_collection_id: Optional[str] = None) -> ChatResponse:
        """Create a new chat"""
        created_chat = self.chat_repo.create_by_model(ChatDTO(
            name=name,
            collection_ids=json.dumps(collection_ids),
            message_count=0,
            bound_collection_id=bound_collection_id
        ))
        logger.info(f"Created chat {created_chat.id} with name '{name}'")

        return self._to_chat_response(created_chat)

    async def get_chat(self, chat_id: str) -> Optional[ChatResponse]:
        """Get chat by ID"""
        chat = self.chat_repo.get_by_id(chat_id)

        if not chat:
            return None

        return self._to_chat_response(chat)

    async def list_chats(self, offset: int = 0, limit: int = 50) -> list[ChatResponse]:
        """List chats with pagination"""
        chats = self.chat_repo.get_all_ordered(offset=offset, limit=limit)

        return [self._to_chat_response(chat) for chat in chats]

    async def update_chat(
        self,
        chat_id: str,
        name: Optional[str] = None,
        collection_ids: Optional[list[str]] = None
    ) -> Optional[ChatResponse]:
        """Update chat information"""
        updated_model = self.chat_repo.update_by_model(ChatDTO(
            id=chat_id,
            name=name,
            collection_ids=json.dumps(collection_ids) if collection_ids else None
        ))
        if not updated_model:
            return None

        return self._to_chat_response(updated_model)

    async def delete_chat(self, chat_id: str) -> bool:
        """Delete chat and all its messages"""
        self.chat_message_repo.delete_by_chat(chat_id)
        return self.chat_repo.delete(chat_id)

    async def get_chat_messages(
        self,
        chat_id: str,
        offset: int = 0,
        limit: int = 50
    ) -> list[ChatMessageResponse]:
        """Get messages for a chat"""
        messages = self.chat_message_repo.get_by_chat(chat_id, offset=offset, limit=limit)
        return [self._to_message_response(message) for message in messages]

    async def count_chat_messages(self, chat_id: str) -> int:
        """Count total chat messages"""
        return self.chat_message_repo.count_by_chat(chat_id)

    def close(self):
        logger.info("ChatService resources closed")
