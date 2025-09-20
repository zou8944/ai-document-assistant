"""Data Transfer Objects for repository layer.

DTOs serve as the boundary between Repository (ORM) and Service layers,
ensuring Repository returns stateless objects that don't depend on SQLAlchemy sessions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Generic, Protocol, TypeVar

from database.base import Base
from models.database import (
    Chat,
    ChatMessage,
    Collection,
    Document,
    DocumentChunk,
    Settings,
    Task,
    TaskLog,
)

T = TypeVar("T", bound=Base)  # ORM model type
D = TypeVar("D", covariant=True)  # DTO type


class DTOConvertible(Protocol, Generic[T, D]):
    """Protocol for DTOs that can be created from ORM objects."""

    @classmethod
    def from_orm(cls, orm_obj: T) -> D:
        """Convert ORM object to DTO."""
        if not hasattr(cls, "__dataclass_fields__"):
            raise TypeError(f"{cls.__name__} must be a dataclass to use default from_orm")

        kwargs = {}
        for field_name in cls.__dataclass_fields__.keys():  # type: ignore
            if hasattr(orm_obj, field_name):
                kwargs[field_name] = getattr(orm_obj, field_name)

        return cls(**kwargs)  # type: ignore

    def to_orm(self, model_class: type[T]) -> T:
        """Convert DTO to ORM object."""
        if not hasattr(self, "__dataclass_fields__"):
            raise TypeError(f"{type(self).__name__} must be a dataclass to use default to_orm")

        kwargs = {}
        for field_name in self.__dataclass_fields__.keys():  # type: ignore
            value = getattr(self, field_name)
            if value is not None:  # 跳过 None 值
                kwargs[field_name] = value

        return model_class(**kwargs)


@dataclass(frozen=True)
class CollectionDTO(DTOConvertible[Collection, "CollectionDTO"]):
    """Collection data transfer object for repository-service boundary."""

    id: str | None = None
    name: str | None = None
    summary: str | None = None
    description: str | None = None
    document_count: int | None = None
    vector_count: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class DocumentDTO(DTOConvertible[Document, "DocumentDTO"]):
    """Document data transfer object for repository-service boundary."""

    id: str | None = None
    collection_id: str | None = None
    name: str | None = None
    content: str | None = None
    summary: str | None = None
    uri: str | None = None
    size_bytes: int | None = None
    mime_type: str | None = None
    chunk_count: int | None = None
    status: str | None = None
    error_message: str | None = None
    hash_md5: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class DocumentChunkDTO(DTOConvertible[DocumentChunk, "DocumentChunkDTO"]):
    """Document chunk data transfer object for repository-service boundary."""

    id: str | None = None
    document_id: str | None = None
    collection_id: str | None = None
    chunk_index: int | None = None
    content_preview: str | None = None
    start_char: int | None = None
    end_char: int | None = None
    vector_id: str | None = None
    content_hash: str | None = None
    chunk_metadata: str | None = None  # JSON string
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class ChatDTO(DTOConvertible[Chat, "ChatDTO"]):
    """Chat data transfer object for repository-service boundary."""

    id: str | None = None
    name: str | None = None
    collection_ids: str | None = None  # JSON string
    message_count: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_message_at: datetime | None = None


@dataclass(frozen=True)
class ChatMessageDTO(DTOConvertible[ChatMessage, "ChatMessageDTO"]):
    """Chat message data transfer object for repository-service boundary."""

    id: str | None = None
    chat_id: str | None = None
    role: str | None = None
    content: str | None = None
    sources: str | None = None  # JSON string
    message_metadata: str | None = None  # JSON string
    created_at: datetime | None = None


@dataclass(frozen=True)
class TaskDTO(DTOConvertible[Task, "TaskDTO"]):
    """Task data transfer object for repository-service boundary."""

    id: str | None = None
    type: str | None = None
    status: str | None = None
    collection_id: str | None = None
    progress_percentage: int | None = None
    input_params: str | None = None  # JSON string
    stats: str | None = None  # JSON string
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True)
class TaskLogDTO(DTOConvertible[TaskLog, "TaskLogDTO"]):
    """Task log data transfer object for repository-service boundary."""

    id: int | None = None
    task_id: str | None = None
    level: str | None = None
    message: str | None = None
    details: str | None = None  # JSON string
    timestamp: datetime | None = None


@dataclass(frozen=True)
class SettingsDTO(DTOConvertible[Settings, "SettingsDTO"]):
    """Settings data transfer object for repository-service boundary."""

    key: str | None = None
    value: str | None = None
    value_type: str | None = None
    category: str | None = None
    description: str | None = None
    is_sensitive: bool | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


# Convenience type aliases for easier imports
CollectionData = CollectionDTO
DocumentData = DocumentDTO
DocumentChunkData = DocumentChunkDTO
ChatData = ChatDTO
ChatMessageData = ChatMessageDTO
TaskData = TaskDTO
TaskLogData = TaskLogDTO
SettingsData = SettingsDTO
