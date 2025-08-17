"""Document and DocumentChunk repositories."""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.database.document import Document, DocumentChunk

from .base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    """Repository for Document operations."""

    def __init__(self, session: Session):
        super().__init__(Document, session)

    def get_by_collection(
        self,
        collection_id: str,
        status: Optional[str] = None,
        search: Optional[str] = None,
        offset: int = 0,
        limit: Optional[int] = None
    ) -> list[Document]:
        """
        Get documents by collection with filters.

        Args:
            collection_id: Collection ID
            status: Optional status filter
            search: Optional name search
            offset: Offset for pagination
            limit: Limit for pagination

        Returns:
            list of documents
        """
        query = select(Document).where(Document.collection_id == collection_id)

        if status:
            query = query.where(Document.status == status)

        if search:
            query = query.where(Document.name.ilike(f"%{search}%"))

        query = query.order_by(Document.updated_at.desc()).offset(offset)

        if limit:
            query = query.limit(limit)

        return list(self.session.scalars(query))

    def count_by_collection(
        self,
        collection_id: str,
        status: Optional[str] = None
    ) -> int:
        """
        Count documents in collection.

        Args:
            collection_id: Collection ID
            status: Optional status filter

        Returns:
            Document count
        """
        query = select(func.count(Document.id)).where(
            Document.collection_id == collection_id
        )

        if status:
            query = query.where(Document.status == status)

        return self.session.scalar(query) or 0

    def find_by_uri(self, collection_id: str, uri: str) -> Optional[Document]:
        """
        Find document by collection and URI.

        Args:
            collection_id: Collection ID
            uri: Document URI

        Returns:
            Document or None if not found
        """
        return self.session.scalar(
            select(Document).where(
                Document.collection_id == collection_id,
                Document.uri == uri
            )
        )

    def find_by_hash(self, collection_id: str, hash_md5: str) -> Optional[Document]:
        """
        Find document by collection and MD5 hash.

        Args:
            collection_id: Collection ID
            hash_md5: MD5 hash

        Returns:
            Document or None if not found
        """
        return self.session.scalar(
            select(Document).where(
                Document.collection_id == collection_id,
                Document.hash_md5 == hash_md5
            )
        )

    def get_by_status(self, status: str) -> list[Document]:
        """
        Get documents by status.

        Args:
            status: Document status

        Returns:
            list of documents with given status
        """
        return list(self.session.scalars(
            select(Document).where(Document.status == status)
        ))


class DocumentChunkRepository(BaseRepository[DocumentChunk]):
    """Repository for DocumentChunk operations."""

    def __init__(self, session: Session):
        super().__init__(DocumentChunk, session)

    def get_by_document(self, document_id: str) -> list[DocumentChunk]:
        """
        Get chunks by document ID.

        Args:
            document_id: Document ID

        Returns:
            list of document chunks ordered by index
        """
        return list(self.session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        ))

    def get_by_collection(self, collection_id: str) -> list[DocumentChunk]:
        """
        Get chunks by collection ID.

        Args:
            collection_id: Collection ID

        Returns:
            list of document chunks
        """
        return list(self.session.scalars(
            select(DocumentChunk).where(DocumentChunk.collection_id == collection_id)
        ))

    def get_by_vector_id(self, vector_id: str) -> Optional[DocumentChunk]:
        """
        Get chunk by vector ID.

        Args:
            vector_id: Vector ID in ChromaDB

        Returns:
            Document chunk or None if not found
        """
        return self.session.scalar(
            select(DocumentChunk).where(DocumentChunk.vector_id == vector_id)
        )

    def get_by_vector_ids(self, vector_ids: list[str]) -> list[DocumentChunk]:
        """
        Get chunks by multiple vector IDs.

        Args:
            vector_ids: list of vector IDs

        Returns:
            list of document chunks
        """
        return list(self.session.scalars(
            select(DocumentChunk).where(DocumentChunk.vector_id.in_(vector_ids))
        ))

    def count_by_document(self, document_id: str) -> int:
        """
        Count chunks by document ID.

        Args:
            document_id: Document ID

        Returns:
            Chunk count
        """
        return self.session.scalar(
            select(func.count(DocumentChunk.id)).where(
                DocumentChunk.document_id == document_id
            )
        ) or 0

    def count_by_collection(self, collection_id: str) -> int:
        """
        Count chunks by collection ID.

        Args:
            collection_id: Collection ID

        Returns:
            Chunk count
        """
        return self.session.scalar(
            select(func.count(DocumentChunk.id)).where(
                DocumentChunk.collection_id == collection_id
            )
        ) or 0

    def delete_by_document(self, document_id: str) -> int:
        """
        Delete all chunks for a document.

        Args:
            document_id: Document ID

        Returns:
            Number of deleted chunks
        """
        from sqlalchemy import delete

        stmt = delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        result = self.session.execute(stmt)
        self.session.commit()

        return result.rowcount or 0
