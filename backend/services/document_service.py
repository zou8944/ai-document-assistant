"""
Document processing service for handling files and web content.
"""

import logging
import mimetypes
import re
from pathlib import Path
from typing import Any, Optional

from fastapi import Response
from langchain_openai import OpenAIEmbeddings

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

    def __init__(
        self,
        success: bool,
        collection_name: str,
        processed_count: int,
        total_count: int,
        total_chunks: int,
        indexed_count: int,
        message: Optional[str] = None,
    ):
        self.success = success
        self.collection_name = collection_name
        self.processed_count = processed_count
        self.total_count = total_count
        self.total_chunks = total_chunks
        self.indexed_count = indexed_count
        self.message = message


class CrawlResult:
    """Result object for crawling operations"""

    def __init__(
        self,
        success: bool,
        collection_name: str,
        crawled_pages: int,
        failed_pages: int,
        total_chunks: int,
        indexed_count: int,
        stats: Optional[dict[str, Any]] = None,
        message: Optional[str] = None,
    ):
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

    def __init__(self, config):
        """Initialize document service with configuration"""
        self.config = config

        # Initialize components
        self.file_processor = create_file_processor(self.config)
        self.document_processor = create_document_processor()
        self.web_crawler = create_simple_web_crawler(self.config)
        self.chroma_manager = create_chroma_manager()

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
            name_translated=document.name_translated,
            uri=document.uri or "",
            size_bytes=document.size_bytes or 0,
            mime_type=document.mime_type or "",
            chunk_count=document.chunk_count or 0,
            status=document.status or "",
            source_path=document.source_path,
            category=document.category,
            keywords=document.keywords,
            total_tokens=document.total_tokens or 0,
            created_at=document.created_at.isoformat() if document.created_at else "",
            updated_at=document.updated_at.isoformat() if document.updated_at else "",
        )

    async def list_documents(
        self,
        collection_id: str,
        page: int = 1,
        page_size: int = 50,
        search: Optional[str] = None,
        status: Optional[str] = None,
    ) -> ListDocumentsResponse:
        """List documents in a collection with pagination and filters"""
        offset = (page - 1) * page_size

        # Get documents (hide not_found pages by default)
        documents = self.doc_repo.get_by_collection(
            collection_id=collection_id,
            status=status,
            exclude_statuses=["not_found"] if not status else None,
            search=search,
            offset=offset,
            limit=page_size,
        )

        # Get total count (hide not_found pages by default)
        total = self.doc_repo.count_by_collection(
            collection_id=collection_id,
            status=status,
            exclude_statuses=["not_found"] if not status else None,
            search=search,
        )

        return ListDocumentsResponse(
            documents=[self._to_response(doc) for doc in documents],
            page=page,
            page_size=page_size,
            total=total,
        )

    async def get_document(
        self, collection_id: str, document_id: str
    ) -> Optional[DocumentResponse]:
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
        suffix = mimetypes.guess_extension(document.mime_type or "text/plain")
        if suffix:
            filename += suffix

        # wrap the document content as FileResponse
        return Response(
            content=document.content.encode("utf-8") if document.content else b"",
            media_type=document.mime_type or "text/plain",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @staticmethod
    def _source_path_to_page_rel_path(source_path: str) -> str:
        """Map URL source_path to local HTML path under pages/."""
        clean = source_path.split("?", 1)[0].split("#", 1)[0].strip().lstrip("/")
        if not clean:
            return "pages/index.html"

        suffix = Path(clean).suffix.lower()
        if suffix in {".html", ".htm"}:
            return f"pages/{clean}"
        return f"pages/{clean}.html"

    def _compute_preview_base_href(self, document: DocumentDTO, collection_id: str) -> str | None:
        """Compute the <base> href for previewing a crawled page in the browser."""
        if not document.source_path:
            return None

        page_rel_path = self._source_path_to_page_rel_path(document.source_path)
        page_dir = str(Path(page_rel_path).parent)
        if page_dir == ".":
            page_dir = ""

        base = f"/api/v1/collections/{collection_id}/static/"
        if page_dir:
            base += page_dir + "/"
        return base

    @staticmethod
    def _inject_base_tag(html: str, base_href: str) -> str:
        """Inject or replace a <base> tag in the HTML."""
        base_tag = f'<base href="{base_href}">'

        # If a <base> tag already exists, replace its href attribute
        if re.search(r"<base\b", html, re.IGNORECASE):
            return re.sub(
                r"<base\b[^>]*>",
                base_tag,
                html,
                count=1,
                flags=re.IGNORECASE,
            )

        # Try to insert after <head> tag
        head_match = re.search(r"<head\b[^>]*>", html, re.IGNORECASE)
        if head_match:
            insert_pos = head_match.end()
            return html[:insert_pos] + "\n" + base_tag + html[insert_pos:]

        # Try to insert after <html> tag (wrap with <head>)
        html_match = re.search(r"<html\b[^>]*>", html, re.IGNORECASE)
        if html_match:
            insert_pos = html_match.end()
            return html[:insert_pos] + "\n<head>\n" + base_tag + "\n</head>" + html[insert_pos:]

        # Fallback: prepend to the beginning
        return base_tag + "\n" + html

    async def preview_document(self, collection_id: str, document_id: str) -> Optional[Response]:
        """Return rewritten HTML content for offline preview (crawled pages only)"""
        document = self.doc_repo.get_by_id(document_id)

        if not document or document.collection_id != collection_id:
            return None

        if not document.clean_html:
            return None

        base_href = self._compute_preview_base_href(document, collection_id)
        if base_href:
            html = self._inject_base_tag(document.clean_html, base_href)
        else:
            html = document.clean_html

        return Response(
            content=html.encode("utf-8"),
            media_type="text/html",
        )

    async def get_document_content(
        self, collection_id: str, document_id: str
    ) -> Optional[str]:
        """Get the markdown content of a specific document"""
        document = self.doc_repo.get_by_id(document_id)

        if not document or document.collection_id != collection_id:
            return None

        return document.content or None

    def close(self):
        self.chroma_manager.close()
        logger.info("DocumentService resources closed")
