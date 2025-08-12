"""
Models for streaming responses.
"""

from typing import Optional, Union

from pydantic import BaseModel, Field

from models.responses import SourceInfo


class StreamChunk(BaseModel):
    """Base class for all streaming chunks"""
    type: str = Field(..., description="Type of the chunk")


class ProgressChunk(StreamChunk):
    """Progress update chunk"""
    type: str = Field(default="progress", description="Chunk type")
    message: str = Field(..., description="Progress message")
    current: Optional[int] = Field(None, description="Current progress value")
    total: Optional[int] = Field(None, description="Total progress value")


class ContentChunk(StreamChunk):
    """Content chunk containing partial answer"""
    type: str = Field(default="content", description="Chunk type")
    content: str = Field(..., description="Partial content")


class SourcesChunk(StreamChunk):
    """Sources chunk containing document sources"""
    type: str = Field(default="sources", description="Chunk type")
    sources: list[SourceInfo] = Field(..., description="Source documents")


class ErrorChunk(StreamChunk):
    """Error chunk for streaming errors"""
    type: str = Field(default="error", description="Chunk type")
    error: str = Field(..., description="Error message")


class DoneChunk(StreamChunk):
    """Done chunk indicating end of stream"""
    type: str = Field(default="done", description="Chunk type")
    confidence: Optional[float] = Field(None, description="Final confidence score")


# Union type for all possible chunks
AnyStreamChunk = Union[ProgressChunk, ContentChunk, SourcesChunk, ErrorChunk, DoneChunk]
