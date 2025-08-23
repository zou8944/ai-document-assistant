"""
Document processing service for handling files and web content.
"""

import logging
import os
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlparse

from fastapi import HTTPException
from fastapi.responses import FileResponse
from langchain_openai import OpenAIEmbeddings

from config import get_config
from crawler import create_simple_web_crawler
from data_processing.file_processor import create_file_processor
from data_processing.text_splitter import create_document_processor
from database.connection import get_db_session_context
from models.database.document import Document
from models.responses import DocumentResponse, ListDocumentsResponse
from repository.document import DocumentChunkRepository, DocumentRepository
from vector_store.chroma_client import create_chroma_manager

logger = logging.getLogger(__name__)


class ProcessResult:
    """Result object for processing operations"""

    def __init__(self, success: bool, collection_name: str, processed_count: int,
                 total_count: int, total_chunks: int, indexed_count: int,
                 message: Optional[str] = None):
        self.success = success
        self.collection_name = collection_name
        self.processed_count = processed_count
        self.total_count = total_count
        self.total_chunks = total_chunks
        self.indexed_count = indexed_count
        self.message = message


class CrawlResult:
    """Result object for crawling operations"""

    def __init__(self, success: bool, collection_name: str, crawled_pages: int,
                 failed_pages: int, total_chunks: int, indexed_count: int,
                 stats: Optional[dict[str, Any]] = None, message: Optional[str] = None):
        self.success = success
        self.collection_name = collection_name
        self.crawled_pages = crawled_pages
        self.failed_pages = failed_pages
        self.total_chunks = total_chunks
        self.indexed_count = indexed_count
        self.stats = stats or {}
        self.message = message


class DocumentService:
    """
    Service for processing documents and web content.
    Pure business logic without communication protocol concerns.
    """

    def __init__(self, config=None):
        """Initialize document service with configuration"""
        self.config = config or get_config()

        # Initialize components
        self.file_processor = create_file_processor(self.config)
        self.document_processor = create_document_processor(self.config)
        self.web_crawler = create_simple_web_crawler(self.config)
        self.chroma_manager = create_chroma_manager(self.config)

        # Initialize embeddings
        embeddings_kwargs = self.config.get_openai_embeddings_kwargs()
        self.embeddings = OpenAIEmbeddings(**embeddings_kwargs)

        # Detect embedding dimension
        self.embedding_dimension = self._detect_embedding_dimension()
        logger.info(f"Detected embedding dimension: {self.embedding_dimension}")

        # Batch processing settings
        self.max_embedding_batch_size = getattr(self.config, "embedding_batch_size", 64)

        logger.info("DocumentService initialized successfully")

    def _to_response(self, document: Document) -> DocumentResponse:
        """Convert Document model to response model"""
        return DocumentResponse(
            id=document.id,
            name=document.name,
            uri=document.uri,
            size_bytes=document.size_bytes,
            mime_type=document.mime_type,
            chunk_count=document.chunk_count,
            status=document.status,
            created_at=document.created_at.isoformat(),
            updated_at=document.updated_at.isoformat()
        )

    async def list_documents(
        self,
        collection_id: str,
        page: int = 1,
        page_size: int = 50,
        search: Optional[str] = None,
        status: Optional[str] = None
    ) -> ListDocumentsResponse:
        """List documents in a collection with pagination and filters"""
        with get_db_session_context() as session:
            repo = DocumentRepository(session)

            # Calculate offset
            offset = (page - 1) * page_size

            # Get documents
            documents = repo.get_by_collection(
                collection_id=collection_id,
                status=status,
                search=search,
                offset=offset,
                limit=page_size
            )

            # Get total count
            total = repo.count_by_collection(collection_id=collection_id, status=status)

            return ListDocumentsResponse(
                documents=[self._to_response(doc) for doc in documents],
                page=page,
                page_size=page_size,
                total=total
            )

    async def get_document(self, collection_id: str, document_id: str) -> Optional[DocumentResponse]:
        """Get a specific document"""
        with get_db_session_context() as session:
            repo = DocumentRepository(session)
            document = repo.get_by_id(document_id)

            if not document or document.collection_id != collection_id:
                return None

            return self._to_response(document)

    async def delete_document(self, collection_id: str, document_id: str) -> bool:
        """Delete a document and its associated chunks/vectors"""
        with get_db_session_context() as session:
            doc_repo = DocumentRepository(session)
            chunk_repo = DocumentChunkRepository(session)

            document = doc_repo.get_by_id(document_id)
            if not document or document.collection_id != collection_id:
                return False

            # Get all chunks to get vector IDs
            chunks = chunk_repo.get_by_document(document_id)
            vector_ids = [chunk.vector_id for chunk in chunks]

            # Delete vectors from ChromaDB
            if vector_ids:
                await self.chroma_manager.delete_collection(collection_id)
                logger.info(f"Deleted {len(vector_ids)} vectors from ChromaDB")

            # Delete document from database (cascade will handle chunks)
            success = doc_repo.delete(document_id)

            if success:
                logger.info(f"Deleted document '{document_id}' and {len(vector_ids)} chunks")

            return success

    async def download_document(self, collection_id: str, document_id: str) -> Optional[FileResponse]:
        """Download a document file (only for file:// URIs)"""
        with get_db_session_context() as session:
            repo = DocumentRepository(session)
            document = repo.get_by_id(document_id)

            if not document or document.collection_id != collection_id:
                return None

            # Check if it's a file URI
            parsed_uri = urlparse(document.uri)
            if parsed_uri.scheme != 'file':
                raise HTTPException(
                    status_code=400,
                    detail="Document is not a local file and cannot be downloaded"
                )

            # Get file path
            file_path = parsed_uri.path
            if not os.path.exists(file_path):
                raise HTTPException(
                    status_code=404,
                    detail="File not found on disk"
                )

            # Return file response
            return FileResponse(
                path=file_path,
                filename=document.name,
                media_type=document.mime_type or 'application/octet-stream'
            )

    def _detect_embedding_dimension(self) -> int:
        """Detect the actual embedding dimension from the model"""
        vec = self.embeddings.embed_query("ping")
        dim = len(vec)
        if dim <= 0:
            raise ValueError("Empty embedding vector returned")
        return dim

    async def _embed_texts_in_batches(self, texts: list[str],
                                    progress_callback: Optional[Callable] = None) -> list[list[float]]:
        """Generate embeddings in batches to avoid API limits"""
        if not self.embeddings:
            raise Exception("Embeddings not available. Please check OpenAI API configuration.")

        if not texts:
            return []

        max_batch = self.max_embedding_batch_size
        total = len(texts)
        embeddings: list[list[float]] = []

        for start in range(0, total, max_batch):
            end = min(start + max_batch, total)
            batch = texts[start:end]

            batch_embeddings = await self.embeddings.aembed_documents(batch)
            embeddings.extend(batch_embeddings)

            if progress_callback:
                progress_callback(f"Embedding batch {end}/{total}", end, total)

        return embeddings

    async def _ensure_collection_with_dimension(self, collection_name: str) -> Optional[str]:
        """
        Ensure collection exists with correct dimensions.
        Returns error message if there's a dimension mismatch.
        """
        info = await self.chroma_manager.get_collection_info(collection_name)
        if info and info.get("vector_size") and info["vector_size"] != self.embedding_dimension:
            raise ValueError(f"Collection '{collection_name}' exists with vector size {info['vector_size']} "
                           f"but current model outputs {self.embedding_dimension} dimensions. "
                           f"Please delete the collection or use a different name.")

        # Create or ensure collection exists
        await self.chroma_manager.ensure_collection(
            collection_name,
            vector_size=self.embedding_dimension
        )
        return None

    async def process_files(self, file_paths: list[str], collection_name: str = "documents",
                          progress_callback: Optional[Callable] = None) -> ProcessResult:
        """
        Process local files and index them in vector store.

        Args:
            file_paths: list of file or folder paths
            collection_name: Target collection name
            progress_callback: Optional callback for progress updates (message, current, total)

        Returns:
            ProcessResult with processing statistics
        """
        logger.info(f"Processing {len(file_paths)} file paths for collection '{collection_name}'")

        if progress_callback:
            progress_callback("Checking collection...", 0, len(file_paths))

        # Ensure collection exists with correct dimensions
        await self._ensure_collection_with_dimension(collection_name)

        all_chunks = []
        processed_files = 0
        total_files = 0

        # Process each path
        for file_path in file_paths:
            path_obj = Path(file_path)

            if path_obj.is_file():
                # Single file processing
                total_files += 1
                result = self.file_processor.process_file(str(path_obj))

                if result.success:
                    chunks = self.document_processor.process_file_content(
                        file_path=str(path_obj),
                        content=result.content,
                        file_type=result.file_type
                    )
                    all_chunks.extend(chunks)
                    processed_files += 1

                    if progress_callback:
                        progress_callback(f"Processed: {path_obj.name}",
                                        processed_files, total_files)
                else:
                    logger.warning(f"Failed to process file {file_path}: {result.error}")

            elif path_obj.is_dir():
                # Folder processing
                folder_results = list(self.file_processor.process_folder(str(path_obj)))
                total_files += len(folder_results)

                for result in folder_results:
                    if result.success:
                        chunks = self.document_processor.process_file_content(
                            file_path=result.file_path,
                            content=result.content,
                            file_type=result.file_type
                        )
                        all_chunks.extend(chunks)
                        processed_files += 1

                        if progress_callback:
                            progress_callback(f"Processed: {Path(result.file_path).name}",
                                            processed_files, total_files)

        if not all_chunks:
            return ProcessResult(
                success=False, collection_name=collection_name,
                processed_count=processed_files, total_count=total_files,
                total_chunks=0, indexed_count=0,
                message="No content extracted from provided files"
            )

        # Generate embeddings
        if progress_callback:
            progress_callback("Generating embeddings...", processed_files, total_files)

        texts = [chunk.content for chunk in all_chunks]
        embeddings = await self._embed_texts_in_batches(texts, progress_callback)

        # Index in vector store
        if progress_callback:
            progress_callback("Indexing documents...", processed_files, total_files)

        index_result = await self.chroma_manager.index_documents(
            collection_name=collection_name,
            chunks=all_chunks,
            embeddings=embeddings
        )

        if index_result["status"] == "success":
            return ProcessResult(
                success=True, collection_name=collection_name,
                processed_count=processed_files, total_count=total_files,
                total_chunks=len(all_chunks),
                indexed_count=index_result["indexed_count"]
            )
        else:
            return ProcessResult(
                success=False, collection_name=collection_name,
                processed_count=processed_files, total_count=total_files,
                total_chunks=len(all_chunks), indexed_count=0,
                message=f"Indexing failed: {index_result['message']}"
            )

    async def crawl_website(self, url: str, collection_name: str = "website",
                          progress_callback: Optional[Callable] = None) -> CrawlResult:
        """
        Crawl website and index content in vector store.

        Args:
            url: Starting URL to crawl
            collection_name: Target collection name
            progress_callback: Optional callback for progress updates (message, current, total)

        Returns:
            CrawlResult with crawling statistics
        """
        logger.info(f"Starting website crawl for: {url}")

        if progress_callback:
            progress_callback("Checking collection...", 0, 1)

        # Ensure collection exists with correct dimensions
        await self._ensure_collection_with_dimension(collection_name)

        # Progress callback for crawling
        def crawl_progress_callback(current_url: str, current: int, total: int):
            if progress_callback:
                progress_callback(f"Crawling: {current_url}", current, max(total, current))

        # Crawl the website
        crawl_results = self.web_crawler.crawl_recursive(url, crawl_progress_callback)
        successful_results = [r for r in crawl_results if r.success]

        if not successful_results:
            return CrawlResult(
                success=False, collection_name=collection_name,
                crawled_pages=0, failed_pages=len(crawl_results),
                total_chunks=0, indexed_count=0,
                message="No pages were successfully crawled"
            )

        # Process crawled content
        if progress_callback:
            progress_callback("Processing crawled content...",
                            len(successful_results), len(successful_results))

        all_chunks = []
        for result in successful_results:
            chunks = self.document_processor.process_web_content(
                url=result.url,
                content=result.content,
                page_title=result.title
            )
            all_chunks.extend(chunks)

        if not all_chunks:
            return CrawlResult(
                success=False, collection_name=collection_name,
                crawled_pages=len(successful_results),
                failed_pages=len(crawl_results) - len(successful_results),
                total_chunks=0, indexed_count=0,
                message="No content extracted from crawled pages"
            )

        # Generate embeddings
        if progress_callback:
            progress_callback("Generating embeddings...",
                            len(successful_results), len(successful_results))

        texts = [chunk.content for chunk in all_chunks]
        embeddings = await self._embed_texts_in_batches(texts, progress_callback)

        # Index in vector store
        if progress_callback:
            progress_callback("Indexing documents...",
                            len(successful_results), len(successful_results))

        index_result = await self.chroma_manager.index_documents(
            collection_name=collection_name,
            chunks=all_chunks,
            embeddings=embeddings
        )

        if index_result["status"] == "success":
            stats = self.web_crawler.get_crawl_stats(crawl_results)

            return CrawlResult(
                success=True, collection_name=collection_name,
                crawled_pages=len(successful_results),
                failed_pages=len(crawl_results) - len(successful_results),
                total_chunks=len(all_chunks),
                indexed_count=index_result["indexed_count"],
                stats=stats
            )
        else:
            return CrawlResult(
                success=False, collection_name=collection_name,
                crawled_pages=len(successful_results),
                failed_pages=len(crawl_results) - len(successful_results),
                total_chunks=len(all_chunks), indexed_count=0,
                message=f"Indexing failed: {index_result['message']}"
            )

    def close(self):
        self.chroma_manager.close()
        logger.info("DocumentService resources closed")
