"""Collection repository for knowledge base collections."""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.database.collection import Collection
from repository.base import BaseRepository


class CollectionRepository(BaseRepository[Collection]):
    """Repository for Collection operations."""

    def __init__(self, session: Session):
        super().__init__(Collection, session)

    def search_by_name(self, search_term: str) -> list[Collection]:
        """
        Search collections by name.

        Args:
            search_term: Search term for collection name

        Returns:
            list of matching collections
        """
        query = select(Collection).where(
            Collection.name.ilike(f"%{search_term}%")
        ).order_by(Collection.updated_at.desc())

        return list(self.session.scalars(query))

    def get_with_stats(self, collection_id: str) -> Optional[Collection]:
        """
        Get collection with updated statistics.

        Args:
            collection_id: Collection ID

        Returns:
            Collection with updated stats or None
        """
        collection = self.get_by_id(collection_id)
        if collection:
            # Update document count from actual documents
            from models.database.document import Document
            doc_count = self.session.scalar(
                select(func.count(Document.id)).where(
                    Document.collection_id == collection_id
                )
            ) or 0

            # Update chunk count from actual chunks
            from models.database.document import DocumentChunk
            vector_count = self.session.scalar(
                select(func.count(DocumentChunk.id)).where(
                    DocumentChunk.collection_id == collection_id
                )
            ) or 0

            # Update collection stats if they differ
            if collection.document_count != doc_count or collection.vector_count != vector_count:
                collection.document_count = doc_count
                collection.vector_count = vector_count
                self.session.commit()
                self.session.refresh(collection)

        return collection

    def update_stats(self, collection_id: str) -> bool:
        """
        Update collection statistics.

        Args:
            collection_id: Collection ID

        Returns:
            True if updated, False if collection not found
        """
        collection = self.get_by_id(collection_id)
        if not collection:
            return False

        # Count documents
        from models.database.document import Document
        doc_count = self.session.scalar(
            select(func.count(Document.id)).where(
                Document.collection_id == collection_id
            )
        ) or 0

        # Count chunks/vectors
        from models.database.document import DocumentChunk
        vector_count = self.session.scalar(
            select(func.count(DocumentChunk.id)).where(
                DocumentChunk.collection_id == collection_id
            )
        ) or 0

        # Update collection
        collection.document_count = doc_count
        collection.vector_count = vector_count
        self.session.commit()

        return True

    def get_all_ordered(
        self,
        search: Optional[str] = None,
        offset: int = 0,
        limit: Optional[int] = None
    ) -> list[Collection]:
        """
        Get all collections ordered by update time with optional search.

        Args:
            search: Optional search term
            offset: Offset for pagination
            limit: Limit for pagination

        Returns:
            list of collections
        """
        query = select(Collection)

        if search:
            query = query.where(Collection.name.ilike(f"%{search}%"))

        query = query.order_by(Collection.updated_at.desc()).offset(offset)

        if limit:
            query = query.limit(limit)

        return list(self.session.scalars(query))
