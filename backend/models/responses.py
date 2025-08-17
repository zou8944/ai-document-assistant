"""
Response models for API endpoints.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class SourceInfo(BaseModel):
    """Information about a document source"""
    source: str = Field(..., description="Source file path or URL")
    content_preview: str = Field(..., description="Preview of the content")
    score: float = Field(..., description="Relevance score")
    start_index: int = Field(default=0, description="Start index in the document")


class ProcessFilesResponse(BaseModel):
    """Response model for file processing"""
    success: bool = Field(..., description="Whether the processing was successful")
    collection_name: str = Field(..., description="Name of the created/updated collection")
    processed_files: int = Field(..., description="Number of files successfully processed")
    total_files: int = Field(..., description="Total number of files attempted")
    total_chunks: int = Field(..., description="Total number of text chunks created")
    indexed_count: int = Field(..., description="Number of chunks successfully indexed")
    message: Optional[str] = Field(None, description="Additional message or error details")


class CrawlWebsiteResponse(BaseModel):
    """Response model for website crawling"""
    success: bool = Field(..., description="Whether the crawling was successful")
    collection_name: str = Field(..., description="Name of the created/updated collection")
    crawled_pages: int = Field(..., description="Number of pages successfully crawled")
    failed_pages: int = Field(default=0, description="Number of pages that failed to crawl")
    total_chunks: int = Field(..., description="Total number of text chunks created")
    indexed_count: int = Field(..., description="Number of chunks successfully indexed")
    stats: Optional[dict[str, Any]] = Field(None, description="Additional crawling statistics")
    message: Optional[str] = Field(None, description="Additional message or error details")


class QueryResponse(BaseModel):
    """Response model for document queries"""
    answer: str = Field(..., description="Generated answer to the question")
    sources: list[SourceInfo] = Field(default=[], description="Source documents used")
    confidence: float = Field(..., description="Confidence score for the answer")
    collection_name: str = Field(..., description="Collection that was queried")
    question: str = Field(..., description="Original question")


class CollectionInfo(BaseModel):
    """Information about a document collection"""
    name: str = Field(..., description="Collection name")
    vector_size: int = Field(..., description="Vector dimensions")
    document_count: int = Field(..., description="Number of documents in collection")
    source_type: str = Field(..., description="Type of source (files, website, etc.)")


class CollectionResponse(BaseModel):
    """Response model for collection operations"""
    id: str = Field(..., description="Collection ID")
    name: str = Field(..., description="Display name")
    description: str = Field(..., description="Description")
    document_count: int = Field(..., description="Number of documents")
    vector_count: int = Field(..., description="Number of vectors")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")


class ListCollectionsResponseV1(BaseModel):
    """Response model for listing collections (v1 API)"""
    collections: list[CollectionResponse] = Field(..., description="List of collections")
    total: int = Field(..., description="Total number of collections")


class DocumentResponse(BaseModel):
    """Response model for document operations"""
    id: str = Field(..., description="Document ID")
    name: str = Field(..., description="File name or page title")
    uri: str = Field(..., description="Document URI")
    size_bytes: int = Field(..., description="File size in bytes")
    mime_type: Optional[str] = Field(None, description="MIME type")
    chunk_count: int = Field(..., description="Number of chunks")
    status: str = Field(..., description="Processing status")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")


class ListDocumentsResponse(BaseModel):
    """Response model for listing documents"""
    documents: list[DocumentResponse] = Field(..., description="List of documents")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Page size")
    total: int = Field(..., description="Total number of documents")


class ListCollectionsResponse(BaseModel):
    """Response model for listing collections"""
    collections: list[CollectionInfo] = Field(default=[], description="List of available collections")


class DeleteCollectionResponse(BaseModel):
    """Response model for deleting a collection"""
    success: bool = Field(..., description="Whether the deletion was successful")
    collection_name: str = Field(..., description="Name of the deleted collection")
    message: Optional[str] = Field(None, description="Additional message or error details")


class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    embeddings_available: bool = Field(..., description="Whether embeddings service is available")
    chroma_available: bool = Field(..., description="Whether Chroma service is available")
