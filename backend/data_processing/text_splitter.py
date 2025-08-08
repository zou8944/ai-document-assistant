"""
Text processing and chunking module using LangChain's RecursiveCharacterTextSplitter.
Following 2024 best practices for document preprocessing and metadata preservation.
"""

import logging
from typing import Any, Optional
from uuid import uuid4

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class DocumentChunk(BaseModel):
    """Structured document chunk with metadata"""
    id: str
    content: str
    source: str
    start_index: int
    metadata: dict[str, Any] = {}


class DocumentProcessor:
    """
    Document text processing and chunking using LangChain's RecursiveCharacterTextSplitter.
    Optimized for RAG applications with proper metadata preservation.
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        """
        Initialize document processor with standard 2024 configuration.

        Args:
            chunk_size: Size of each chunk (default 1000 - 2024 recommendation)
            chunk_overlap: Overlap between chunks (default 200 - standard overlap)
        """
        # CRITICAL: LangChain RecursiveCharacterTextSplitter standard config
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            add_start_index=True,  # Track source location
            separators=["\n\n", "\n", " ", ""],  # Default separators
            keep_separator=False
        )

        logger.info(f"Initialized DocumentProcessor with chunk_size={chunk_size}, overlap={chunk_overlap}")

    def process_text(self, text: str, source: str = "unknown",
                    additional_metadata: Optional[dict[str, Any]] = None) -> list[DocumentChunk]:
        """
        Process raw text into structured chunks with metadata.

        Args:
            text: Raw text content to process
            source: Source identifier (file path, URL, etc.)
            additional_metadata: Optional metadata to include with each chunk

        Returns:
            list of DocumentChunk objects with preserved metadata
        """
        if not text.strip():
            logger.warning(f"Empty text provided for source: {source}")
            return []

        try:
            # Create LangChain Document
            doc = Document(
                page_content=text,
                metadata={
                    "source": source,
                    **(additional_metadata or {})
                }
            )

            # Split the document
            splits = self.text_splitter.split_documents([doc])

            # Convert to our DocumentChunk format
            chunks = []
            for split in splits:
                chunk = DocumentChunk(
                    id=str(uuid4()),
                    content=split.page_content,
                    source=source,
                    start_index=split.metadata.get("start_index", 0),
                    metadata=split.metadata
                )
                chunks.append(chunk)

            logger.info(f"Processed text from '{source}' into {len(chunks)} chunks")
            return chunks

        except Exception as e:
            logger.error(f"Failed to process text from '{source}': {e}")
            return []

    def process_documents(self, documents: list[Document]) -> list[DocumentChunk]:
        """
        Process multiple LangChain Documents into chunks.

        Args:
            documents: list of LangChain Document objects

        Returns:
            list of DocumentChunk objects
        """
        all_chunks = []

        try:
            # Split all documents at once for efficiency
            splits = self.text_splitter.split_documents(documents)

            # Convert to our format
            for split in splits:
                chunk = DocumentChunk(
                    id=str(uuid4()),
                    content=split.page_content,
                    source=split.metadata.get("source", "unknown"),
                    start_index=split.metadata.get("start_index", 0),
                    metadata=split.metadata
                )
                all_chunks.append(chunk)

            logger.info(f"Processed {len(documents)} documents into {len(all_chunks)} chunks")
            return all_chunks

        except Exception as e:
            logger.error(f"Failed to process documents: {e}")
            return []

    def process_file_content(self, file_path: str, content: str,
                           file_type: str = "unknown") -> list[DocumentChunk]:
        """
        Process content from a file with appropriate metadata.

        Args:
            file_path: Path to the source file
            content: File content as string
            file_type: Type of file (pdf, txt, docx, etc.)

        Returns:
            list of DocumentChunk objects
        """
        metadata = {
            "file_path": file_path,
            "file_type": file_type,
            "processing_timestamp": "2024"  # Could use datetime.now().isoformat()
        }

        return self.process_text(
            text=content,
            source=file_path,
            additional_metadata=metadata
        )

    def process_web_content(self, url: str, content: str,
                          page_title: str = "") -> list[DocumentChunk]:
        """
        Process content from web crawling with appropriate metadata.

        Args:
            url: Source URL
            content: Web page content as markdown/text
            page_title: Title of the web page

        Returns:
            list of DocumentChunk objects
        """
        metadata = {
            "url": url,
            "page_title": page_title,
            "content_type": "web_page",
            "processing_timestamp": "2024"  # Could use datetime.now().isoformat()
        }

        return self.process_text(
            text=content,
            source=url,
            additional_metadata=metadata
        )

    def get_chunk_stats(self, chunks: list[DocumentChunk]) -> dict[str, Any]:
        """
        Get statistics about processed chunks.

        Args:
            chunks: list of document chunks

        Returns:
            Dictionary with chunk statistics
        """
        if not chunks:
            return {"total_chunks": 0, "total_characters": 0, "sources": []}

        total_chars = sum(len(chunk.content) for chunk in chunks)
        sources = list(set(chunk.source for chunk in chunks))
        avg_chunk_size = total_chars / len(chunks) if chunks else 0

        return {
            "total_chunks": len(chunks),
            "total_characters": total_chars,
            "average_chunk_size": round(avg_chunk_size, 2),
            "unique_sources": len(sources),
            "sources": sources[:10]  # Limit to first 10 sources for readability
        }


# Convenience function for creating processor instance
def create_document_processor(chunk_size: int = 1000, chunk_overlap: int = 200) -> DocumentProcessor:
    """Create and return a DocumentProcessor instance with standard configuration"""
    return DocumentProcessor(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
