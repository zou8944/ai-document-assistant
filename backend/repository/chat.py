"""Chat and ChatMessage repositories."""

from typing import Optional

from sqlalchemy import func, select

from database.connection import session_context
from models.database.chat import Chat, ChatMessage
from models.dto import ChatDTO, ChatMessageDTO
from repository.base import BaseRepository


class ChatRepository(BaseRepository[Chat, ChatDTO]):
    """Repository for Chat operations."""

    def __init__(self):
        super().__init__(Chat, ChatDTO)

    def get_all_ordered(self, offset: int = 0, limit: Optional[int] = None) -> list[ChatDTO]:
        with session_context() as session:
            query = (
                select(Chat)
                .order_by(Chat.last_message_at.desc().nulls_last(), Chat.updated_at.desc())
                .offset(offset)
            )

            if limit:
                query = query.limit(limit)

            entities = list(session.scalars(query))
            return [self.dto_class.from_orm(item) for item in entities]

    def update_message_count(self, chat_id: str) -> bool:
        with session_context() as session:
            chat = session.get(Chat, chat_id)
            if not chat:
                return False

            # Count messages
            message_count = session.scalar(
                select(func.count(ChatMessage.id)).where(ChatMessage.chat_id == chat_id)
            ) or 0

            # Get last message time
            last_message = session.scalar(
                select(ChatMessage.created_at)
                .where(ChatMessage.chat_id == chat_id)
                .order_by(ChatMessage.created_at.desc())
            )

            # Update chat
            chat.message_count = message_count
            chat.last_message_at = last_message
            return True

    def search_by_name(self, search_term: str) -> list[ChatDTO]:
        with session_context() as session:
            sql = select(Chat).where(Chat.name.ilike(f"%{search_term}%")).order_by(Chat.last_message_at.desc().nulls_last())
            entities = list(session.scalars(sql))
            return [self.dto_class.from_orm(item) for item in entities]

    def get_by_collection(self, collection_id: str) -> list[ChatDTO]:
        # This requires JSON querying which varies by database
        # For SQLite, we'll use simple LIKE matching
        with session_context() as session:
            sql = select(Chat).where(Chat.collection_ids.like(f'%"{collection_id}"%'))
            entities = list(session.scalars(sql))
            return [self.dto_class.from_orm(item) for item in entities]


class ChatMessageRepository(BaseRepository[ChatMessage, ChatMessageDTO]):
    """Repository for ChatMessage operations."""

    def __init__(self):
        super().__init__(ChatMessage, ChatMessageDTO)

    def get_by_chat(self, chat_id: str, offset: int = 0, limit: Optional[int] = None) -> list[ChatMessageDTO]:
        with session_context() as session:
            query = (
                select(ChatMessage)
                .where(ChatMessage.chat_id == chat_id)
                .order_by(ChatMessage.created_at.asc())
                .offset(offset)
            )

            if limit:
                query = query.limit(limit)

            entities = list(session.scalars(query))
            return [self.dto_class.from_orm(item) for item in entities]

    def count_by_chat(self, chat_id: str) -> int:
        with session_context() as session:
            return session.scalar(
                select(func.count(ChatMessage.id)).where(ChatMessage.chat_id == chat_id)
            ) or 0

    def get_latest_by_chat(self, chat_id: str) -> Optional[ChatMessageDTO]:
        with session_context() as session:
            entity = session.scalar(
                select(ChatMessage)
                .where(ChatMessage.chat_id == chat_id)
                .order_by(ChatMessage.created_at.desc())
            )
            if entity is None:
                return None
            return self.dto_class.from_orm(entity)

    def add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        sources: Optional[str] = None,
        metadata: Optional[str] = None
    ) -> ChatMessageDTO:
        with session_context() as session:
            message = ChatMessage(
                chat_id=chat_id,
                role=role,
                content=content,
                sources=sources or "[]",
                metadata=metadata or "{}"
            )

            session.add(message)
            session.flush()
            session.refresh(message)

        # Update chat statistics
        chat_repo = ChatRepository()
        chat_repo.update_message_count(chat_id)

        return self.dto_class.from_orm(message)

    def get_conversation_history(
        self,
        chat_id: str,
        max_messages: int = 50
    ) -> list[ChatMessageDTO]:
        with session_context() as session:
            entities = list(session.scalars(
                select(ChatMessage)
                .where(ChatMessage.chat_id == chat_id)
                .order_by(ChatMessage.created_at.desc())
                .limit(max_messages)
            ))[::-1]  # Reverse to get chronological order
            return [self.dto_class.from_orm(item) for item in entities]

    def delete_by_chat(self, chat_id: str) -> int:
        from sqlalchemy import delete
        with session_context() as session:
            stmt = delete(ChatMessage).where(ChatMessage.chat_id == chat_id)
            result = session.execute(stmt)

        return result.rowcount or 0
