"""
Collection management service.
"""

import logging
from typing import Optional

from database.connection import transaction
from models.dto import CollectionDTO
from models.responses import CollectionResponse
from repository.collection import CollectionRepository
from repository.document import DocumentChunkRepository, DocumentRepository
from services import LLMService

logger = logging.getLogger(__name__)


class CollectionService:
    """Service for managing document collections"""

    def __init__(self, config, llm_service: LLMService):
        """Initialize collection service"""
        from config import get_config
        from vector_store.chroma_client import create_chroma_manager

        self.config = config or get_config()
        self.chroma_manager = create_chroma_manager(self.config)

        self.collection_repo = CollectionRepository()
        self.doc_repo = DocumentRepository()
        self.doc_chunk_repo = DocumentChunkRepository()

        # LLM service
        self.llm_service = llm_service

        logger.info("CollectionService initialized successfully")

    def _to_response(self, collection: CollectionDTO) -> CollectionResponse:
        """Convert Collection model to response model"""
        return CollectionResponse(
            id=collection.id or "",
            name=collection.name or "",
            description=collection.description or "",
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
        """Delete a collection"""
        # delete collection, document, document_chunk; delete chroma collection
        async with transaction():
            self.collection_repo.delete(collection_id)
            self.doc_repo.delete_by_collection(collection_id)
            self.doc_chunk_repo.delete_by_collection(collection_id)
            await self.chroma_manager.delete_collection(collection_id)

        logger.info(f"Deleted collection '{collection_id}'")

    async def refresh_collection_summary(self, collection_id: str):
        docs = self.doc_repo.get_by_collection(collection_id)
        doc_summaries = [doc.summary for doc in docs if doc.summary]
        if not doc_summaries:
            return
        collection_summary = self.llm_service.summarize_collection(doc_summaries)
        self.collection_repo.update(collection_id, summary=collection_summary)

    def close(self):
        """Close connections and cleanup resources"""
        self.chroma_manager.close()
        self.llm_service.close()
        logger.info("CollectionService resources closed")
