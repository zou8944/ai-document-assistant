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


class SettingsResponse(BaseModel):
    """Response model for settings"""
    llm: dict = Field(..., description="LLM settings")
    embedding: dict = Field(..., description="Embedding settings")
    data_location: str = Field(..., description="Data location path")
    paths: dict = Field(..., description="Path settings")
    crawler: dict = Field(..., description="Crawler settings")
    text: dict = Field(..., description="Text processing settings")


class TaskResponse(BaseModel):
    """Response model for task operations"""
    task_id: str = Field(..., description="Task ID")
    type: str = Field(..., description="Task type")
    status: str = Field(..., description="Task status")
    progress: dict = Field(..., description="Progress information")
    stats: dict = Field(..., description="Task statistics")
    collection_id: Optional[str] = Field(None, description="Associated collection ID")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    error: Optional[str] = Field(None, description="Error message if failed")


class IngestResponse(BaseModel):
    """Response model for ingestion operations"""
    task_id: str = Field(..., description="Task ID for tracking progress")
    status: str = Field(..., description="Initial task status")


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


class ChatResponse(BaseModel):
    """Response model for chat information"""
    chat_id: str = Field(..., description="Chat ID")
    name: str = Field(..., description="Chat name")
    collection_ids: list[str] = Field(..., description="Knowledge base collection IDs")
    message_count: int = Field(..., description="Number of messages in chat")
    created_at: str = Field(..., description="Creation timestamp")
    last_message_at: Optional[str] = Field(None, description="Last message timestamp")


class ChatMessageResponse(BaseModel):
    """Response model for chat messages"""
    message_id: str = Field(..., description="Message ID")
    chat_id: str = Field(..., description="Chat ID")
    role: str = Field(..., description="Message role (user/assistant)")
    content: str = Field(..., description="Message content")
    sources: list[dict] = Field(default=[], description="Source references")
    metadata: dict = Field(default={}, description="Additional metadata")
    created_at: str = Field(..., description="Creation timestamp")


class SourceReference(BaseModel):
    """Response model for source references"""
    document_name: str = Field(..., description="Source document name")
    document_id: str = Field(..., description="Document ID")
    chunk_index: int = Field(..., description="Chunk index within document")
    content_preview: str = Field(..., description="Preview of relevant content")
    relevance_score: float = Field(..., description="Relevance score")


class ChatCompletionResponse(BaseModel):
    """Response model for chat completion"""
    message_id: str = Field(..., description="Generated message ID")
    chat_id: str = Field(..., description="Chat ID")
    content: str = Field(..., description="Generated response content")
    sources: list[SourceReference] = Field(default=[], description="Source references")
    metadata: dict = Field(default={}, description="Additional metadata")
    model_info: dict = Field(default={}, description="Model information used")


class EnhancedChatResponse(BaseModel):
    """Response model for enhanced chat with advanced retrieval features"""
    message_id: str = Field(..., description="Generated message ID")
    chat_id: str = Field(..., description="Chat ID")
    content: str = Field(..., description="Generated response content")
    sources: list[SourceReference] = Field(default=[], description="Source references")
    metadata: dict = Field(default={}, description="Additional metadata")

    # Enhanced features
    confidence: float = Field(..., description="Response confidence score")
    intent_analysis: Optional[dict] = Field(None, description="Query intent analysis results")
    retrieval_strategy: str = Field(..., description="Retrieval strategy used")
    cache_hit: bool = Field(default=False, description="Whether response was served from cache")

    # Performance metrics
    retrieval_time_ms: Optional[float] = Field(None, description="Time spent on retrieval (ms)")
    generation_time_ms: Optional[float] = Field(None, description="Time spent on generation (ms)")
    total_time_ms: Optional[float] = Field(None, description="Total processing time (ms)")

    # Retrieval details
    collections_searched: list[str] = Field(default=[], description="Collections that were searched")
    documents_retrieved: int = Field(default=0, description="Number of documents retrieved")
    sources_count: int = Field(default=0, description="Number of source references")


class IntentAnalysisResponse(BaseModel):
    """Response model for query intent analysis"""
    intent: str = Field(..., description="Detected intent type")
    confidence: str = Field(..., description="Confidence level (high/medium/low)")
    confidence_score: float = Field(..., description="Numerical confidence score")
    keyword_scores: dict = Field(..., description="Keyword matching scores by intent")
    description: str = Field(..., description="Human-readable intent description")
    analysis_method: str = Field(..., description="Method used for analysis")


class CacheStatsResponse(BaseModel):
    """Response model for cache statistics"""
    chains_count: int = Field(..., description="Number of retrieval chains")
    total_cache_hits: int = Field(..., description="Total cache hits across all chains")
    total_cache_misses: int = Field(..., description="Total cache misses across all chains")
    hit_rate: float = Field(..., description="Overall cache hit rate")
    per_collection: dict = Field(..., description="Per-collection cache statistics")


class RetrievalStrategiesResponse(BaseModel):
    """Response model for available retrieval strategies"""
    strategies: dict = Field(..., description="Available strategies with descriptions")
    default: str = Field(..., description="Default strategy")
    recommended: str = Field(..., description="Recommended strategy")
