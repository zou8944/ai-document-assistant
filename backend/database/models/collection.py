"""Collection model for knowledge base collections."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database.base import Base

if TYPE_CHECKING:
    from .document import Document
    from .task import Task


class Collection(Base):
    """Knowledge base collection model."""

    __tablename__ = "collections"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
        doc="Collection ID (slug)"
    )

    # Basic info
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Display name"
    )
    description: Mapped[str] = mapped_column(
        Text,
        default="",
        server_default="",
        doc="Description"
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Collection summary"
    )

    # Statistics (cached values)
    document_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        doc="Number of documents"
    )
    vector_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        doc="Number of vectors"
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

    # Relationships
    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="collection",
        cascade="all, delete-orphan"
    )
    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="collection"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "length(name) >= 1 AND length(name) <= 200",
            name="chk_collection_name_length"
        ),
        Index("idx_collections_name", "name"),
        Index("idx_collections_updated_at", "updated_at"),
    )

    def __repr__(self) -> str:
        return f"<Collection(id='{self.id}', name='{self.name}')>"
