"""Document and DocumentChunk repositories."""

from typing import Optional

from sqlalchemy import func, select

from database.connection import session_context
from models.database.document import Document, DocumentChunk
from repository.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    """Repository for Document operations."""

    def __init__(self):
        super().__init__(Document)

    def get_by_collection(
        self,
        collection_id: str,
        status: Optional[str] = None,
        search: Optional[str] = None,
        offset: int = 0,
        limit: Optional[int] = None
    ) -> list[Document]:
        with session_context() as session:
            query = select(Document).where(Document.collection_id == collection_id)

            if status:
                query = query.where(Document.status == status)

            if search:
                query = query.where(Document.name.ilike(f"%{search}%"))

            query = query.order_by(Document.updated_at.desc()).offset(offset)

            if limit:
                query = query.limit(limit)

            return list(session.scalars(query))

    def count_by_collection(
        self,
        collection_id: str,
        status: Optional[str] = None
    ) -> int:
        with session_context() as session:
            query = select(func.count(Document.id)).where(
                Document.collection_id == collection_id
            )

            if status:
                query = query.where(Document.status == status)

            return session.scalar(query) or 0

    def find_by_uri(self, collection_id: str, uri: str) -> Optional[Document]:
        with session_context() as session:
            return session.scalar(
                select(Document).where(
                    Document.collection_id == collection_id,
                    Document.uri == uri
                )
            )

    def find_by_hash(self, collection_id: str, hash_md5: str) -> Optional[Document]:
        with session_context() as session:
            return session.scalar(
                select(Document).where(
                    Document.collection_id == collection_id,
                    Document.hash_md5 == hash_md5
                )
            )

    def get_by_status(self, status: str) -> list[Document]:
        with session_context() as session:
            return list(session.scalars(
                select(Document).where(Document.status == status)
            ))


class DocumentChunkRepository(BaseRepository[DocumentChunk]):
    """Repository for DocumentChunk operations."""

    def __init__(self):
        super().__init__(DocumentChunk)

    def get_by_document(self, document_id: str) -> list[DocumentChunk]:
        with session_context() as session:
            return list(session.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == document_id)
                .order_by(DocumentChunk.chunk_index)
            ))

    def get_by_collection(self, collection_id: str) -> list[DocumentChunk]:
        with session_context() as session:
            return list(session.scalars(
                select(DocumentChunk).where(DocumentChunk.collection_id == collection_id)
            ))

    def get_by_vector_id(self, vector_id: str) -> Optional[DocumentChunk]:
        with session_context() as session:
            return session.scalar(
                select(DocumentChunk).where(DocumentChunk.vector_id == vector_id)
            )

    def get_by_vector_ids(self, vector_ids: list[str]) -> list[DocumentChunk]:
        with session_context() as session:
            return list(session.scalars(
                select(DocumentChunk).where(DocumentChunk.vector_id.in_(vector_ids))
            ))

    def count_by_document(self, document_id: str) -> int:
        with session_context() as session:
            return session.scalar(
                select(func.count(DocumentChunk.id)).where(
                    DocumentChunk.document_id == document_id
                )
            ) or 0

    def count_by_collection(self, collection_id: str) -> int:
        with session_context() as session:
            return session.scalar(
                select(func.count(DocumentChunk.id)).where(
                    DocumentChunk.collection_id == collection_id
                )
            ) or 0

    def delete_by_document(self, document_id: str) -> int:
        from sqlalchemy import delete

        with session_context() as session:
            stmt = delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
            result = session.execute(stmt)
            session.flush()

        return result.rowcount or 0
