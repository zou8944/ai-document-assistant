"""Document and DocumentChunk models."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database.base import Base

if TYPE_CHECKING:
    from .collection import Collection


class Document(Base):
    """Document model for uploaded files and crawled pages."""

    __tablename__ = "documents"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=lambda: uuid.uuid4().hex,
        doc="Document UUID"
    )

    # Foreign key
    collection_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
        doc="Collection ID"
    )

    # Basic info
    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="File name or page title"
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Document summary"
    )
    uri: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="file:// or https:// URI"
    )
    size_bytes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        doc="File size in bytes"
    )
    mime_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        doc="MIME type"
    )

    # Processing status
    chunk_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        doc="Number of chunks"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        server_default="'pending'",
        doc="Processing status"
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        doc="Error message if processing failed"
    )

    # Content
    content: Mapped[str] = mapped_column(
        Text,
        default="",
        server_default="",
        doc="Document content"
    )

    # Content hash for deduplication
    hash_md5: Mapped[Optional[str]] = mapped_column(
        String(32),
        doc="MD5 hash for deduplication"
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
    collection: Mapped["Collection"] = relationship(
        "Collection",
        back_populates="documents"
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'indexed', 'failed')",
            name="chk_document_status"
        ),
        CheckConstraint(
            "uri LIKE 'file://%' OR uri LIKE 'http://%' OR uri LIKE 'https://%'",
            name="chk_document_uri_format"
        ),
        CheckConstraint(
            "size_bytes >= 0",
            name="chk_document_size"
        ),
        UniqueConstraint(
            "collection_id", "uri",
            name="uq_document_collection_uri"
        ),
        Index("idx_documents_collection_id", "collection_id"),
        Index("idx_documents_status", "status"),
        Index("idx_documents_hash", "hash_md5"),
        Index("idx_documents_updated_at", "updated_at"),
    )

    def __repr__(self) -> str:
        return f"<Document(id='{self.id}', name='{self.name}', status='{self.status}')>"


class DocumentChunk(Base):
    """Document chunk model for fine-grained vector management."""

    __tablename__ = "document_chunks"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=lambda: f"chunk_{uuid.uuid4().hex[:16]}",
        doc="Chunk ID"
    )

    # Foreign keys
    document_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        doc="Document ID"
    )
    collection_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
        doc="Collection ID (redundant for quick queries)"
    )

    # Chunk info
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Chunk index in document (0-based)"
    )
    content_preview: Mapped[Optional[str]] = mapped_column(
        Text,
        doc="Content preview (first 200 chars)"
    )
    start_char: Mapped[Optional[int]] = mapped_column(
        Integer,
        doc="Start character position in document"
    )
    end_char: Mapped[Optional[int]] = mapped_column(
        Integer,
        doc="End character position in document"
    )

    # Vector mapping
    vector_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        doc="Vector ID in ChromaDB"
    )
    content_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        doc="Content hash for caching"
    )

    # Metadata (using chunk_metadata to avoid SQLAlchemy reserved name)
    chunk_metadata: Mapped[Optional[str]] = mapped_column(
        Text,
        default="{}",
        server_default="'{}'",
        doc="Additional metadata (JSON)"
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
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="chunks"
    )
    collection: Mapped["Collection"] = relationship(
        "Collection"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "chunk_index >= 0",
            name="chk_chunk_index"
        ),
        CheckConstraint(
            "start_char >= 0 AND (end_char IS NULL OR end_char > start_char)",
            name="chk_chunk_char_positions"
        ),
        UniqueConstraint(
            "document_id", "chunk_index",
            name="uq_chunk_doc_index"
        ),
        Index("idx_chunks_document_id", "document_id"),
        Index("idx_chunks_collection_id", "collection_id"),
        Index("idx_chunks_vector_id", "vector_id"),
    )

    def __repr__(self) -> str:
        return f"<DocumentChunk(id='{self.id}', doc='{self.document_id}', index={self.chunk_index})>"
