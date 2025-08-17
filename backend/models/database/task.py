"""Task and TaskLog models for async operations."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database.base import Base

if TYPE_CHECKING:
    from .collection import Collection


class Task(Base):
    """Task model for async operations like file ingestion."""

    __tablename__ = "tasks"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=lambda: f"task_{uuid.uuid4().hex[:16]}",
        doc="Task ID"
    )

    # Task type and status
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Task type (ingest_files, ingest_urls)"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        server_default="'pending'",
        doc="Task status"
    )

    # Associated collection
    collection_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        ForeignKey("collections.id", ondelete="SET NULL"),
        doc="Associated collection ID"
    )

    # Progress tracking
    progress_percentage: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        doc="Progress percentage (0-100)"
    )

    # Input parameters and statistics (JSON)
    input_params: Mapped[str] = mapped_column(
        Text,
        default="{}",
        server_default="'{}'",
        doc="Task input parameters (JSON)"
    )
    stats: Mapped[str] = mapped_column(
        Text,
        default="{}",
        server_default="'{}'",
        doc="Task statistics (JSON)"
    )

    # Error handling
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        doc="Error message if task failed"
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
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        doc="Task start timestamp"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        doc="Task completion timestamp"
    )

    # Relationships
    collection: Mapped[Optional["Collection"]] = relationship(
        "Collection",
        back_populates="tasks"
    )
    logs: Mapped[list["TaskLog"]] = relationship(
        "TaskLog",
        back_populates="task",
        cascade="all, delete-orphan"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "type IN ('ingest_files', 'ingest_urls')",
            name="chk_task_type"
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'success', 'failed')",
            name="chk_task_status"
        ),
        CheckConstraint(
            "progress_percentage BETWEEN 0 AND 100",
            name="chk_task_progress"
        ),
        Index("idx_tasks_status", "status"),
        Index("idx_tasks_collection_id", "collection_id"),
        Index("idx_tasks_created_at", "created_at"),
        Index("idx_tasks_type_status", "type", "status"),
    )

    def __repr__(self) -> str:
        return f"<Task(id='{self.id}', type='{self.type}', status='{self.status}')>"


class TaskLog(Base):
    """Task log model for detailed task execution logs."""

    __tablename__ = "task_logs"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        doc="Log entry ID"
    )

    # Foreign key
    task_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        doc="Task ID"
    )

    # Log info
    level: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        doc="Log level (debug, info, warning, error)"
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Log message"
    )
    details: Mapped[str] = mapped_column(
        Text,
        default="{}",
        server_default="'{}'",
        doc="Detailed information (JSON)"
    )

    # Timestamp
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        doc="Log timestamp"
    )

    # Relationships
    task: Mapped["Task"] = relationship(
        "Task",
        back_populates="logs"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "level IN ('debug', 'info', 'warning', 'error')",
            name="chk_log_level"
        ),
        Index("idx_task_logs_task_id", "task_id"),
        Index("idx_task_logs_timestamp", "timestamp"),
        Index("idx_task_logs_level", "level"),
    )

    def __repr__(self) -> str:
        return f"<TaskLog(id={self.id}, task='{self.task_id}', level='{self.level}')>"
