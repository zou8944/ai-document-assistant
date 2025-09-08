"""
Document processing service for handling files and web content.
"""

import logging
import mimetypes
from typing import Any, Optional

from fastapi import Response
from langchain_openai import OpenAIEmbeddings

from config import get_config
from crawler import create_simple_web_crawler
from data_processing.file_processor import create_file_processor
from data_processing.text_splitter import create_document_processor
from models.dto import DocumentDTO
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

        # Initialize repositories
        self.doc_repo = DocumentRepository()
        self.doc_chunk_repo = DocumentChunkRepository()

        # Initialize embeddings
        embeddings_kwargs = self.config.get_openai_embeddings_kwargs()
        self.embeddings = OpenAIEmbeddings(**embeddings_kwargs)

        # Batch processing settings
        self.max_embedding_batch_size = getattr(self.config, "embedding_batch_size", 64)

        mimetypes.add_type("text/markdown", ".md")

        logger.info("DocumentService initialized successfully")

    def _to_response(self, document: DocumentDTO) -> DocumentResponse:
        """Convert Document model to response model"""
        return DocumentResponse(
            id=document.id or "",
            name=document.name or "",
            uri=document.uri or "",
            size_bytes=document.size_bytes or 0,
            mime_type=document.mime_type or "",
            chunk_count=document.chunk_count or 0,
            status=document.status or "",
            created_at=document.created_at.isoformat() if document.created_at else "",
            updated_at=document.updated_at.isoformat() if document.updated_at else ""
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
        offset = (page - 1) * page_size

        # Get documents
        documents = self.doc_repo.get_by_collection(
            collection_id=collection_id,
            status=status,
            search=search,
            offset=offset,
            limit=page_size
        )

        # Get total count
        total = self.doc_repo.count_by_collection(
            collection_id=collection_id,
            status=status,
            search=search
        )

        return ListDocumentsResponse(
            documents=[self._to_response(doc) for doc in documents],
            page=page,
            page_size=page_size,
            total=total
        )

    async def get_document(self, collection_id: str, document_id: str) -> Optional[DocumentResponse]:
        """Get a specific document"""
        document = self.doc_repo.get_by_id(document_id)

        if not document or document.collection_id != collection_id:
            return None

        return self._to_response(document)

    async def delete_document(self, collection_id: str, document_id: str) -> bool:
        """Delete a document and its associated chunks/vectors"""
        collection = await self.chroma_manager.get_collection(collection_id)
        assert collection

        document = self.doc_repo.get_by_id(document_id)
        if not document or document.collection_id != collection_id:
            return False

        assert document.id
        self.doc_chunk_repo.delete_by_document(document.id)
        self.doc_repo.delete_by_id(document.id)
        collection.delete(where={"document_id": document.id})

        return True

    async def download_document(self, collection_id: str, document_id: str) -> Optional[Response]:
        """Download a document file (only for file:// URIs)"""
        document = self.doc_repo.get_by_id(document_id)

        if not document or document.collection_id != collection_id:
            return None

        # 需要检查 filename 是否有后缀，如果没有，根据 mime_type 添加
        filename = document.name or ""
        suffix = mimetypes.guess_extension(document.mime_type or 'text/plain')
        if suffix:
            filename += suffix

        # wrap the document content as FileResponse
        return Response(
            content=document.content.encode('utf-8') if document.content else b'',
            media_type=document.mime_type or 'text/plain',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )

    def close(self):
        self.chroma_manager.close()
        logger.info("DocumentService resources closed")
