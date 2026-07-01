"""Chat and ChatMessage repositories."""

from typing import Optional

from sqlalchemy import func, select

from database.connection import session_context
from database.models.chat import Chat, ChatMessage
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
                .order_by(Chat.sort_order.asc())
                .offset(offset)
            )

            if limit:
                query = query.limit(limit)

            entities = list(session.scalars(query))
            return [self.dto_class.from_orm(item) for item in entities]

    def next_sort_order(self) -> int:
        """Return the next sort_order value (max + 1, or 0 for empty table)."""
        with session_context() as session:
            max_order = session.scalar(select(func.max(Chat.sort_order)))
            if max_order is None:
                return 0
            return max_order + 1

    def reorder(self, ordered_ids: list[str]) -> int:
        """Rewrite sort_order for the given chat ids based on their position.

        Raises ValueError if any id is missing in the database.
        """
        with session_context() as session:
            chats = list(
                session.scalars(select(Chat).where(Chat.id.in_(ordered_ids)))
            )
            chats_map = {c.id: c for c in chats}
            missing = set(ordered_ids) - chats_map.keys()
            if missing:
                raise ValueError(f"Chats not found: {sorted(missing)}")
            for pos, chat_id in enumerate(ordered_ids):
                chats_map[chat_id].sort_order = pos
            return len(ordered_ids)

    def count_all(self) -> int:
        """Return total number of chats."""
        with session_context() as session:
            return session.scalar(select(func.count(Chat.id))) or 0

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

    def get_by_bound_collection(self, collection_id: str) -> Optional[ChatDTO]:
        """Get collection-bound chat by collection ID."""
        with session_context() as session:
            entity = session.scalar(
                select(Chat).where(Chat.bound_collection_id == collection_id)
            )
            if entity is None:
                return None
            return self.dto_class.from_orm(entity)


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
                message_metadata=metadata or "{}"
            )

            session.add(message)
            session.flush()
            session.refresh(message)

            message_dto = self.dto_class.from_orm(message)

        # Update chat statistics
        chat_repo = ChatRepository()
        chat_repo.update_message_count(chat_id)

        return message_dto

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

    def find_preceding_user_message(self, chat_id: str, assistant_message_id: str) -> Optional[ChatMessageDTO]:
        """Find the user message immediately before the given assistant message."""
        with session_context() as session:
            # Get the assistant message to find its timestamp
            assistant = session.get(ChatMessage, assistant_message_id)
            if not assistant or assistant.chat_id != chat_id or assistant.role != "assistant":
                return None

            # Find the latest user message before this assistant message
            entity = session.scalar(
                select(ChatMessage)
                .where(ChatMessage.chat_id == chat_id)
                .where(ChatMessage.role == "user")
                .where(ChatMessage.created_at < assistant.created_at)
                .order_by(ChatMessage.created_at.desc())
                .limit(1)
            )
            if entity is None:
                return None
            return self.dto_class.from_orm(entity)

    def delete_by_chat(self, chat_id: str) -> int:
        from sqlalchemy import delete
        with session_context() as session:
            stmt = delete(ChatMessage).where(ChatMessage.chat_id == chat_id)
            result = session.execute(stmt)

            return result.rowcount or 0
