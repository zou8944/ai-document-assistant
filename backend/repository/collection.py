"""Collection repository for knowledge base collections."""

from typing import Optional

from sqlalchemy import func, select

from database.connection import session_context
from models.database.collection import Collection
from models.dto import CollectionDTO
from repository.base import BaseRepository


class CollectionRepository(BaseRepository[Collection, CollectionDTO]):
    """Repository for Collection operations."""

    def __init__(self):
        super().__init__(Collection, CollectionDTO)

    def search_by_name(self, search_term: str) -> list[CollectionDTO]:
        with session_context() as session:
            query = select(Collection).where(
                Collection.name.ilike(f"%{search_term}%")
            ).order_by(Collection.updated_at.desc())

            entities = list(session.scalars(query))
            return [self.dto_class.from_orm(item) for item in entities]

    def get_with_stats(self, collection_id: str) -> Optional[CollectionDTO]:
        with session_context() as session:
            collection = session.get(self.model, collection_id)
            if collection is None:
                return None

            # Update document count from actual documents
            from models.database.document import Document
            doc_count = session.scalar(
                select(func.count(Document.id)).where(
                    Document.collection_id == collection_id
                )
            ) or 0

            # Update chunk count from actual chunks
            from models.database.document import DocumentChunk
            vector_count = session.scalar(
                select(func.count(DocumentChunk.id)).where(
                    DocumentChunk.collection_id == collection_id
                )
            ) or 0

            # Update collection stats if they differ
            if collection.document_count != doc_count or collection.vector_count != vector_count:
                collection.document_count = doc_count
                collection.vector_count = vector_count
                session.flush()
                session.refresh(collection)

            return self.dto_class.from_orm(collection)

    def update_stats(self, collection_id: str) -> bool:
        with session_context() as session:
            collection = session.get(self.model, collection_id)
            if not collection:
                return False

            # Count documents
            from models.database.document import Document
            doc_count = session.scalar(
                select(func.count(Document.id)).where(
                    Document.collection_id == collection_id
                )
            ) or 0

            # Count chunks/vectors
            from models.database.document import DocumentChunk
            vector_count = session.scalar(
                select(func.count(DocumentChunk.id)).where(
                    DocumentChunk.collection_id == collection_id
                )
            ) or 0

            # Update collection
            collection.document_count = doc_count
            collection.vector_count = vector_count
            session.flush()

        return True

    def get_all_ordered(
        self, search: Optional[str] = None, offset: int = 0, limit: Optional[int] = None
    ) -> list[CollectionDTO]:
        with session_context() as session:
            query = select(Collection)

            if search:
                query = query.where(Collection.name.ilike(f"%{search}%"))

            query = query.order_by(Collection.updated_at.desc()).offset(offset)

            if limit:
                query = query.limit(limit)

            return [self.dto_class.from_orm(item) for item in session.scalars(query)]
