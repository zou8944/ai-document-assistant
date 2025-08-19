"""Chat and ChatMessage repositories."""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.database.chat import Chat, ChatMessage
from repository.base import BaseRepository


class ChatRepository(BaseRepository[Chat]):
    """Repository for Chat operations."""

    def __init__(self, session: Session):
        super().__init__(Chat, session)

    def get_all_ordered(
        self,
        offset: int = 0,
        limit: Optional[int] = None
    ) -> list[Chat]:
        """
        Get all chats ordered by last message time.

        Args:
            offset: Offset for pagination
            limit: Limit for pagination

        Returns:
            list of chats ordered by activity
        """
        query = (
            select(Chat)
            .order_by(Chat.last_message_at.desc().nulls_last(), Chat.updated_at.desc())
            .offset(offset)
        )

        if limit:
            query = query.limit(limit)

        return list(self.session.scalars(query))

    def update_message_count(self, chat_id: str) -> bool:
        """
        Update message count for a chat.

        Args:
            chat_id: Chat ID

        Returns:
            True if updated, False if chat not found
        """
        chat = self.get_by_id(chat_id)
        if not chat:
            return False

        # Count messages
        message_count = self.session.scalar(
            select(func.count(ChatMessage.id)).where(ChatMessage.chat_id == chat_id)
        ) or 0

        # Get last message time
        last_message = self.session.scalar(
            select(ChatMessage.created_at)
            .where(ChatMessage.chat_id == chat_id)
            .order_by(ChatMessage.created_at.desc())
        )

        # Update chat
        chat.message_count = message_count
        chat.last_message_at = last_message

        self.session.commit()
        return True

    def search_by_name(self, search_term: str) -> list[Chat]:
        """
        Search chats by name.

        Args:
            search_term: Search term for chat name

        Returns:
            list of matching chats
        """
        return list(self.session.scalars(
            select(Chat)
            .where(Chat.name.ilike(f"%{search_term}%"))
            .order_by(Chat.last_message_at.desc().nulls_last())
        ))

    def get_by_collection(self, collection_id: str) -> list[Chat]:
        """
        Get chats that use a specific collection.

        Args:
            collection_id: Collection ID

        Returns:
            list of chats using the collection
        """
        # This requires JSON querying which varies by database
        # For SQLite, we'll use simple LIKE matching
        return list(self.session.scalars(
            select(Chat).where(
                Chat.collection_ids.like(f'%"{collection_id}"%')
            )
        ))


class ChatMessageRepository(BaseRepository[ChatMessage]):
    """Repository for ChatMessage operations."""

    def __init__(self, session: Session):
        super().__init__(ChatMessage, session)

    def get_by_chat(
        self,
        chat_id: str,
        offset: int = 0,
        limit: Optional[int] = None
    ) -> list[ChatMessage]:
        """
        Get messages by chat ID.

        Args:
            chat_id: Chat ID
            offset: Offset for pagination
            limit: Limit for pagination

        Returns:
            list of chat messages ordered by creation time
        """
        query = (
            select(ChatMessage)
            .where(ChatMessage.chat_id == chat_id)
            .order_by(ChatMessage.created_at.asc())
            .offset(offset)
        )

        if limit:
            query = query.limit(limit)

        return list(self.session.scalars(query))

    def count_by_chat(self, chat_id: str) -> int:
        """
        Count messages in a chat.

        Args:
            chat_id: Chat ID

        Returns:
            Message count
        """
        return self.session.scalar(
            select(func.count(ChatMessage.id)).where(ChatMessage.chat_id == chat_id)
        ) or 0

    def get_latest_by_chat(self, chat_id: str) -> Optional[ChatMessage]:
        """
        Get the latest message in a chat.

        Args:
            chat_id: Chat ID

        Returns:
            Latest message or None if no messages
        """
        return self.session.scalar(
            select(ChatMessage)
            .where(ChatMessage.chat_id == chat_id)
            .order_by(ChatMessage.created_at.desc())
        )

    def add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        sources: Optional[str] = None,
        metadata: Optional[str] = None
    ) -> ChatMessage:
        """
        Add a message to a chat.

        Args:
            chat_id: Chat ID
            role: Message role (user/assistant)
            content: Message content
            sources: Optional sources JSON
            metadata: Optional metadata JSON

        Returns:
            Created chat message
        """
        message = ChatMessage(
            chat_id=chat_id,
            role=role,
            content=content,
            sources=sources or "[]",
            metadata=metadata or "{}"
        )

        self.session.add(message)
        self.session.commit()
        self.session.refresh(message)

        # Update chat statistics
        chat_repo = ChatRepository(self.session)
        chat_repo.update_message_count(chat_id)

        return message

    def get_conversation_history(
        self,
        chat_id: str,
        max_messages: int = 50
    ) -> list[ChatMessage]:
        """
        Get recent conversation history for a chat.

        Args:
            chat_id: Chat ID
            max_messages: Maximum number of messages to return

        Returns:
            list of recent messages ordered by creation time
        """
        return list(self.session.scalars(
            select(ChatMessage)
            .where(ChatMessage.chat_id == chat_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(max_messages)
        ))[::-1]  # Reverse to get chronological order

    def delete_by_chat(self, chat_id: str) -> int:
        """
        Delete all messages for a chat.

        Args:
            chat_id: Chat ID

        Returns:
            Number of deleted messages
        """
        from sqlalchemy import delete

        stmt = delete(ChatMessage).where(ChatMessage.chat_id == chat_id)
        result = self.session.execute(stmt)
        self.session.commit()

        return result.rowcount or 0
