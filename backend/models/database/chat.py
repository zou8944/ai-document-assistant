"""Chat and ChatMessage models for conversation management."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database.base import Base


class Chat(Base):
    """Chat model for conversation sessions."""

    __tablename__ = "chats"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=lambda: f"chat_{uuid.uuid4().hex[:16]}",
        doc="Chat ID"
    )

    # Basic info
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Chat name"
    )
    collection_ids: Mapped[str] = mapped_column(
        Text,
        default="[]",
        server_default="'[]'",
        doc="Associated collection IDs (JSON array)"
    )

    # Statistics
    message_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        doc="Number of messages"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        doc="Creation timestamp"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        doc="Last update timestamp"
    )
    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        doc="Last message timestamp"
    )

    # Relationships
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="chat",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "length(name) >= 1 AND length(name) <= 200",
            name="chk_chat_name_length"
        ),
        Index("idx_chats_updated_at", "updated_at"),
        Index("idx_chats_last_message_at", "last_message_at"),
    )

    def __repr__(self) -> str:
        return f"<Chat(id='{self.id}', name='{self.name}')>"


class ChatMessage(Base):
    """Chat message model for individual messages in conversations."""

    __tablename__ = "chat_messages"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=lambda: f"msg_{uuid.uuid4().hex[:16]}",
        doc="Message ID"
    )

    # Foreign key
    chat_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
        doc="Chat ID"
    )

    # Message content
    role: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        doc="Message role (user, assistant)"
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Message content"
    )

    # Additional data
    sources: Mapped[str] = mapped_column(
        Text,
        default="[]",
        server_default="'[]'",
        doc="Reference sources (JSON array)"
    )
    message_metadata: Mapped[str] = mapped_column(
        Text,
        default="{}",
        server_default="'{}'",
        doc="Additional metadata (JSON)"
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        doc="Creation timestamp"
    )

    # Relationships
    chat: Mapped["Chat"] = relationship(
        "Chat",
        back_populates="messages"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant')",
            name="chk_message_role"
        ),
        CheckConstraint(
            "length(content) > 0",
            name="chk_message_content_length"
        ),
        Index("idx_chat_messages_chat_id", "chat_id"),
        Index("idx_chat_messages_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ChatMessage(id='{self.id}', chat='{self.chat_id}', role='{self.role}')>"
