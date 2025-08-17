"""
Collection management service.
"""

import logging
from typing import Optional

from database.connection import get_db_session_context
from models.database.collection import Collection
from models.responses import CollectionInfo, CollectionResponse
from repository.collection import CollectionRepository

logger = logging.getLogger(__name__)


class CollectionService:
    """Service for managing document collections"""

    def __init__(self, config=None):
        """Initialize collection service"""
        from config import get_config
        from vector_store.chroma_client import create_chroma_manager

        self.config = config or get_config()
        self.chroma_manager = create_chroma_manager(self.config)

        logger.info("CollectionService initialized successfully")

    def _to_response(self, collection: Collection) -> CollectionResponse:
        """Convert Collection model to response model"""
        return CollectionResponse(
            id=collection.id,
            name=collection.name,
            description=collection.description,
            document_count=collection.document_count,
            vector_count=collection.vector_count,
            created_at=collection.created_at.isoformat(),
            updated_at=collection.updated_at.isoformat()
        )

    async def create_collection(self, collection_id: str, name: str, description: str = "") -> Optional[CollectionResponse]:
        """Create a new collection"""
        try:
            with get_db_session_context() as session:
                repo = CollectionRepository(session)

                # Check if collection already exists
                existing = repo.get_by_id(collection_id)
                if existing:
                    logger.warning(f"Collection with id '{collection_id}' already exists")
                    return None

                # Create new collection
                collection = Collection(
                    id=collection_id,
                    name=name,
                    description=description
                )

                created_collection = repo.create_by_model(collection)

                # Create ChromaDB collection
                await self.chroma_manager.ensure_collection(collection_id)

                logger.info(f"Created collection '{collection_id}' with name '{name}'")
                return self._to_response(created_collection)

        except Exception as e:
            logger.error(f"Failed to create collection '{collection_id}': {e}")
            return None

    async def list_collections(self, search: Optional[str] = None) -> list[CollectionResponse]:
        """List all collections with optional search"""
        try:
            with get_db_session_context() as session:
                repo = CollectionRepository(session)
                collections = repo.get_all_ordered(search=search)

                # Update stats for each collection
                for collection in collections:
                    repo.update_stats(collection.id)

                return [self._to_response(c) for c in collections]

        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []

    async def get_collection(self, collection_id: str) -> Optional[CollectionResponse]:
        """Get collection by ID with updated stats"""
        try:
            with get_db_session_context() as session:
                repo = CollectionRepository(session)
                collection = repo.get_with_stats(collection_id)

                if not collection:
                    return None

                return self._to_response(collection)

        except Exception as e:
            logger.error(f"Failed to get collection '{collection_id}': {e}")
            return None

    async def update_collection(self, collection_id: str, name: Optional[str] = None, description: Optional[str] = None) -> Optional[CollectionResponse]:
        """Update collection"""
        try:
            with get_db_session_context() as session:
                repo = CollectionRepository(session)
                collection = repo.get_by_id(collection_id)

                if not collection:
                    return None

                # Update fields
                if name is not None:
                    collection.name = name
                if description is not None:
                    collection.description = description

                updated_collection = repo.update(collection)
                logger.info(f"Updated collection '{collection_id}'")

                assert updated_collection is not None
                return self._to_response(updated_collection)

        except Exception as e:
            logger.error(f"Failed to update collection '{collection_id}': {e}")
            return None

    async def delete_collection(self, collection_id: str) -> bool:
        """Delete a collection"""
        try:
            with get_db_session_context() as session:
                repo = CollectionRepository(session)
                collection = repo.get_by_id(collection_id)

                if not collection:
                    return False

                # Delete from ChromaDB first
                chroma_success = await self.chroma_manager.delete_collection(collection_id)
                if not chroma_success:
                    logger.warning(f"Failed to delete ChromaDB collection '{collection_id}', but continuing with database deletion")

                # Delete from database (cascade will handle related records)
                success = repo.delete(collection_id)

                if success:
                    logger.info(f"Deleted collection '{collection_id}'")

                return success

        except Exception as e:
            logger.error(f"Failed to delete collection '{collection_id}': {e}")
            return False

    # Legacy methods for backward compatibility
    async def get_collection_info(self, collection_name: str) -> Optional[CollectionInfo]:
        """Get information about a specific collection (legacy method)"""
        collection = await self.get_collection(collection_name)
        if not collection:
            return None

        return CollectionInfo(
            name=collection.name,
            vector_size=0,  # Not tracked in new system
            document_count=collection.document_count,
            source_type='unknown'  # Not tracked in new system
        )

    def register_collection(self, collection_name: str, source_type: str):
        """Register a collection with its source type for tracking (legacy method)"""
        logger.info(f"Legacy register_collection called for '{collection_name}' (ignored in new system)")

    def close(self):
        """Close connections and cleanup resources"""
        try:
            if hasattr(self, 'chroma_manager'):
                self.chroma_manager.close()
            logger.info("CollectionService resources closed")
        except Exception as e:
            logger.error(f"Error closing CollectionService: {e}")
