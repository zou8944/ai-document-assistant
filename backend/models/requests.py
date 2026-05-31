"""
Request models for API endpoints.
"""

from typing import Optional

from pydantic import BaseModel, Field, model_validator


class ProcessFilesRequest(BaseModel):
    """Request model for processing files"""
    file_paths: list[str] = Field(..., description="List of file or folder paths to process")
    collection_name: str = Field(default="documents", description="Target collection name")


class CrawlWebsiteRequest(BaseModel):
    """Request model for crawling websites"""
    url: str = Field(..., description="Starting URL to crawl")
    collection_name: str = Field(default="website", description="Target collection name")
    max_pages: Optional[int] = Field(default=100, description="Maximum number of pages to crawl")


class QueryRequest(BaseModel):
    """Request model for querying documents"""
    question: str = Field(..., description="Question to ask about the documents")
    collection_name: str = Field(default="documents", description="Collection to query")
    include_sources: bool = Field(default=True, description="Whether to include source citations")


class DeleteCollectionRequest(BaseModel):
    """Request model for deleting a collection"""
    collection_name: str = Field(..., description="Name of the collection to delete")


class CreateCollectionRequest(BaseModel):
    """Request model for creating a collection"""
    id: str = Field(..., description="Collection ID (slug)", min_length=1, max_length=100)
    name: str = Field(..., description="Display name", min_length=1, max_length=200)
    description: str = Field(default="", description="Description")


class UpdateCollectionRequest(BaseModel):
    """Request model for updating a collection"""
    name: Optional[str] = Field(None, description="Display name", min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="Description")


class UpdateSettingsRequest(BaseModel):
    """Request model for updating settings"""
    llm: Optional[dict] = Field(None, description="LLM settings")
    embedding: Optional[dict] = Field(None, description="Embedding settings")
    data_location: Optional[str] = Field(None, description="Data location path")
    paths: Optional[dict] = Field(None, description="Path settings")
    crawler: Optional[dict] = Field(None, description="Crawler settings")
    text: Optional[dict] = Field(None, description="Text processing settings")


class IngestFilesRequest(BaseModel):
    """Request model for file ingestion"""
    files: list[str] = Field(..., description="List of file or folder paths to process")


class UrlConfig(BaseModel):
    """Configuration for a set of URLs with a shared recursive prefix."""
    seed_urls: list[str] = Field(..., min_length=1, description="List of seed URLs")
    recursive_prefix: str = Field(default="", description="Recursive prefix for crawling")


class IngestUrlsRequest(BaseModel):
    """Request model for URL ingestion. Supports both old format (urls + recursive_prefix)
    and new multi-prefix format (url_configs)."""
    # Old format (backward compatible)
    urls: Optional[list[str]] = Field(None, description="List of URLs to crawl")
    recursive_prefix: Optional[str] = Field(None, description="Recursive prefix for crawling")
    # New format
    url_configs: Optional[list[UrlConfig]] = Field(None, description="Multiple URL configs with independent prefixes")

    @model_validator(mode="after")
    def _normalize(self):
        if self.url_configs:
            return self
        if self.urls:
            self.url_configs = [UrlConfig(seed_urls=self.urls, recursive_prefix=self.recursive_prefix or "")]
            return self
        raise ValueError("必须提供 urls 或 url_configs")


class CreateChatRequest(BaseModel):
    """Request model for creating a chat"""
    name: str = Field(..., description="Chat name", min_length=1, max_length=200)
    collection_ids: list[str] = Field(..., description="Knowledge base collection IDs")
    bound_collection_id: Optional[str] = Field(None, description="Bound collection ID for collection-bound chats")


class UpdateChatRequest(BaseModel):
    """Request model for updating a chat"""
    name: Optional[str] = Field(None, description="Chat name", min_length=1, max_length=200)
    collection_ids: Optional[list[str]] = Field(None, description="Knowledge base collection IDs")
    # Note: bound_collection_id is not included because binding is immutable after creation


class ReorderChatsRequest(BaseModel):
    """Request model for reordering chats (full-list mode)."""
    chat_ids: list[str] = Field(..., description="Chat IDs in their new display order")


class ChatMessageRequest(BaseModel):
    """Request model for sending a chat message"""
    message: str = Field(..., description="User message", min_length=1)
    document_ids: Optional[list[str]] = Field(None, description="List of document IDs to use as context")
