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
