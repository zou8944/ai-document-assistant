"""
Collection management service.
"""

import logging
import shutil
from pathlib import Path
from typing import Any, Optional

from database.connection import transaction
from models.dto import CollectionDTO
from models.responses import CollectionResponse
from repository.collection import CollectionRepository
from repository.document import DocumentChunkRepository, DocumentRepository
from repository.task import TaskRepository
from services.llm_service import LLMService

logger = logging.getLogger(__name__)


class CollectionService:
    """Service for managing document collections"""

    def __init__(self, config, llm_service: LLMService):
        """Initialize collection service"""
        from vector_store.chroma_client import create_chroma_manager

        self.config = config
        self.chroma_manager = create_chroma_manager()

        self.collection_repo = CollectionRepository()
        self.doc_repo = DocumentRepository()
        self.doc_chunk_repo = DocumentChunkRepository()
        self.task_repo = TaskRepository()

        # LLM service
        self.llm_service = llm_service

        logger.info("CollectionService initialized successfully")

    def _to_response(self, collection: CollectionDTO) -> CollectionResponse:
        """Convert Collection model to response model"""
        return CollectionResponse(
            id=collection.id or "",
            name=collection.name or "",
            description=collection.description or "",
            source_language=collection.source_language,
            document_count=collection.document_count or 0,
            vector_count=collection.vector_count or 0,
            created_at=collection.created_at.isoformat() if collection.created_at else "",
            updated_at=collection.updated_at.isoformat() if collection.updated_at else ""
        )

    async def create_collection(self, collection_id: str, name: str, description: str = "") -> Optional[CollectionResponse]:
        """Create a new collection"""

        # Check if collection already exists
        existing = self.collection_repo.get_by_id(collection_id)
        if existing:
            logger.warning(f"Collection with id '{collection_id}' already exists")
            return None

        # Create new collection
        collection = CollectionDTO(
            id=collection_id,
            name=name,
            description=description
        )

        created_collection = self.collection_repo.create_by_model(collection)

        # Create ChromaDB collection
        await self.chroma_manager.ensure_collection(collection_id)

        logger.info(f"Created collection '{collection_id}' with name '{name}'")
        return self._to_response(created_collection)

    async def list_collections(self, search: Optional[str] = None) -> list[CollectionResponse]:
        """List all collections with optional search"""
        collections = self.collection_repo.get_all_ordered(search=search)

        # Update stats for each collection
        for collection in collections:
            assert collection.id
            self.collection_repo.update_stats(collection.id)

        return [self._to_response(c) for c in collections]

    async def get_collection(self, collection_id: str) -> Optional[CollectionResponse]:
        """Get collection by ID with updated stats"""
        collection = self.collection_repo.get_by_id(collection_id)

        if not collection:
            return None

        return self._to_response(collection)

    async def update_collection(self, collection_id: str, name: Optional[str] = None, description: Optional[str] = None) -> Optional[CollectionResponse]:
        """Update collection"""
        updated_collection = self.collection_repo.update_by_model(CollectionDTO(
            id=collection_id,
            name=name,
            description=description
        ))
        logger.info(f"Updated collection '{collection_id}'")

        assert updated_collection is not None
        return self._to_response(updated_collection)

    async def delete_collection(self, collection_id: str):
        """Delete a collection and all associated data including crawl cache."""
        # Get domain info before deleting docs (for crawl cache cleanup)
        docs = self.doc_repo.get_by_collection(collection_id)
        domains = set()
        for doc in docs:
            if doc.uri and doc.uri.startswith("http"):
                from urllib.parse import urlparse
                domains.add(urlparse(doc.uri).netloc.lower().replace(":", "_"))

        # Delete all database records in transaction
        async with transaction():
            self.task_repo.delete_by_collection(collection_id)
            self.doc_repo.delete_by_collection(collection_id)
            self.doc_chunk_repo.delete_by_collection(collection_id)
            self.collection_repo.delete(collection_id)
            await self.chroma_manager.delete_collection(collection_id)

        # Delete crawl cache
        cache_root = Path(self.config.get_crawl_cache_dir())
        for domain in domains:
            domain_dir = cache_root / domain
            if domain_dir.exists():
                shutil.rmtree(domain_dir)
                logger.info(f"Deleted crawl cache: {domain_dir}")

        logger.info(f"Deleted collection '{collection_id}'")

    async def clear_collection(self, collection_id: str):
        """Clear all data in a collection but keep the collection itself."""
        collection = self.collection_repo.get_by_id(collection_id)
        if not collection:
            raise ValueError(f"Collection '{collection_id}' not found")

        # Cancel any processing tasks before clearing
        tasks = self.task_repo.get_by_collection(collection_id)
        for task in tasks:
            if task.status == "processing":
                self.task_repo.update_status(task.id, "stopped")

        # Get domain info before deleting docs (for crawl cache cleanup)
        docs = self.doc_repo.get_by_collection(collection_id)
        domains = set()
        for doc in docs:
            if doc.uri and doc.uri.startswith("http"):
                from urllib.parse import urlparse
                domains.add(urlparse(doc.uri).netloc.lower().replace(":", "_"))

        # Delete all vectors from ChromaDB
        chroma_collection = await self.chroma_manager.get_collection(collection_id)
        if chroma_collection:
            try:
                chroma_collection.delete()
            except Exception as e:
                logger.warning(f"Failed to clear vectors for collection {collection_id}: {e}")

        # Delete all database records and update collection
        async with transaction():
            self.doc_repo.delete_by_collection(collection_id)
            self.doc_chunk_repo.delete_by_collection(collection_id)
            self.task_repo.delete_by_collection(collection_id)
            self.collection_repo.update(
                collection_id,
                readme_content=None,
                categories_json=None,
                readme_content_zh=None,
                categories_json_zh=None,
                source_language=None,
                document_count=0,
                vector_count=0,
            )

        # Delete crawl cache
        cache_root = Path(self.config.get_crawl_cache_dir())
        for domain in domains:
            domain_dir = cache_root / domain
            if domain_dir.exists():
                shutil.rmtree(domain_dir)
                logger.info(f"Deleted crawl cache: {domain_dir}")

        logger.info(f"Cleared collection '{collection_id}'")

    async def get_readme(self, collection_id: str) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
        """Get the AI-generated README content and categories for a collection.

        Returns: (readme_content, categories_json, readme_content_zh, categories_json_zh, source_language)
        """
        collection = self.collection_repo.get_by_id(collection_id)
        if not collection:
            return None, None, None, None, None
        return (
            collection.readme_content,
            collection.categories_json,
            collection.readme_content_zh,
            collection.categories_json_zh,
            collection.source_language,
        )

    async def update_readme(
        self,
        collection_id: str,
        readme_content: str,
        categories_json: str,
        readme_content_zh: str = "",
        categories_json_zh: str = "",
        source_language: str = ""
    ) -> None:
        """Store AI-generated README and categories on the collection."""
        update_data: dict[str, Any] = {
            "readme_content": readme_content,
            "categories_json": categories_json
        }
        if readme_content_zh:
            update_data["readme_content_zh"] = readme_content_zh
        if categories_json_zh:
            update_data["categories_json_zh"] = categories_json_zh
        if source_language:
            update_data["source_language"] = source_language
        self.collection_repo.update(collection_id, **update_data)

    async def refresh_collection_summary(self, collection_id: str):
        docs = self.doc_repo.get_by_collection(collection_id, exclude_statuses=["not_found"])
        doc_summaries = [doc.summary for doc in docs if doc.summary]
        if not doc_summaries:
            return
        collection_summary = await self.llm_service.summarize_collection(doc_summaries)
        self.collection_repo.update(collection_id, summary=collection_summary)

    def close(self):
        """Close connections and cleanup resources"""
        self.chroma_manager.close()
        self.llm_service.close()
        logger.info("CollectionService resources closed")
