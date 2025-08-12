"""
Collection management service.
"""

import logging
from typing import Optional

from models.responses import CollectionInfo

logger = logging.getLogger(__name__)


class CollectionService:
    """Service for managing document collections"""

    def __init__(self, config=None):
        """Initialize collection service"""
        from config import get_config
        from vector_store.chroma_client import create_chroma_manager

        self.config = config or get_config()
        self.chroma_manager = create_chroma_manager(self.config)

        # Track active collections and their source types
        self.active_collections: dict[str, str] = {}

        logger.info("CollectionService initialized successfully")

    async def list_collections(self) -> list[CollectionInfo]:
        """list all available collections with their information"""
        try:
            collections_info = []

            # Get all collections from ChromaDB
            all_collections = self.chroma_manager.client.list_collections()

            for collection in all_collections:
                collection_name = collection.name
                info = await self.chroma_manager.get_collection_info(collection_name)
                if info:
                    # Determine source type (default to 'unknown' if not tracked)
                    source_type = self.active_collections.get(collection_name, 'unknown')

                    collection_info = CollectionInfo(
                        name=collection_name,
                        vector_size=info.get('vector_size', 0),
                        document_count=info.get('document_count', 0),
                        source_type=source_type
                    )
                    collections_info.append(collection_info)

            return collections_info

        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []

    async def get_collection_info(self, collection_name: str) -> Optional[CollectionInfo]:
        """Get information about a specific collection"""
        try:
            info = await self.chroma_manager.get_collection_info(collection_name)
            if not info:
                return None

            source_type = self.active_collections.get(collection_name, 'unknown')

            return CollectionInfo(
                name=collection_name,
                vector_size=info.get('vector_size', 0),
                document_count=info.get('document_count', 0),
                source_type=source_type
            )

        except Exception as e:
            logger.error(f"Failed to get collection info for '{collection_name}': {e}")
            return None

    async def delete_collection(self, collection_name: str) -> bool:
        """Delete a collection"""
        try:
            success = await self.chroma_manager.delete_collection(collection_name)
            if success:
                # Remove from active collections tracking
                self.active_collections.pop(collection_name, None)
                logger.info(f"Deleted collection '{collection_name}'")
            return success

        except Exception as e:
            logger.error(f"Failed to delete collection '{collection_name}': {e}")
            return False

    def register_collection(self, collection_name: str, source_type: str):
        """Register a collection with its source type for tracking"""
        self.active_collections[collection_name] = source_type
        logger.info(f"Registered collection '{collection_name}' with source type '{source_type}'")

    def close(self):
        """Close connections and cleanup resources"""
        try:
            if hasattr(self, 'chroma_manager'):
                self.chroma_manager.close()
            logger.info("CollectionService resources closed")
        except Exception as e:
            logger.error(f"Error closing CollectionService: {e}")
