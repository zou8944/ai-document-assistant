"""
Request models for API endpoints.
"""

from typing import Optional

from pydantic import BaseModel, Field


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


class IngestUrlsRequest(BaseModel):
    """Request model for URL ingestion"""
    urls: list[str] = Field(..., description="List of URLs to crawl")
    exclude_urls: list[str] = Field(..., description="List of URLs to exclude")
    max_depth: int = Field(default=0, description="Maximum recursive crawling depth. if zero, no recursion")
    recursive_prefix: str = Field(default="", description="Recursive prefix for crawling")
    override: bool = Field(default=True, description="Whether to override existing URLs")


class CreateChatRequest(BaseModel):
    """Request model for creating a chat"""
    name: str = Field(..., description="Chat name", min_length=1, max_length=200)
    collection_ids: list[str] = Field(..., description="Knowledge base collection IDs")


class UpdateChatRequest(BaseModel):
    """Request model for updating a chat"""
    name: Optional[str] = Field(None, description="Chat name", min_length=1, max_length=200)
    collection_ids: Optional[list[str]] = Field(None, description="Knowledge base collection IDs")


class ChatMessageRequest(BaseModel):
    """Request model for sending a chat message"""
    message: str = Field(..., description="User message", min_length=1)
    document_ids: Optional[list[str]] = Field(None, description="List of document IDs to use as context")
