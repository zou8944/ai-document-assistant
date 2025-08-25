"""Document and DocumentChunk repositories."""

from typing import Optional

from sqlalchemy import func, select

from database.connection import session_context
from models.database.document import Document, DocumentChunk
from models.dto import DocumentChunkDTO, DocumentDTO
from repository.base import BaseRepository


class DocumentRepository(BaseRepository[Document, DocumentDTO]):
    """Repository for Document operations."""

    def __init__(self):
        super().__init__(Document, DocumentDTO)

    def get_by_collection(
        self,
        collection_id: str,
        status: Optional[str] = None,
        search: Optional[str] = None,
        offset: int = 0,
        limit: Optional[int] = None
    ) -> list[DocumentDTO]:
        with session_context() as session:
            query = select(Document).where(Document.collection_id == collection_id)

            if status:
                query = query.where(Document.status == status)

            if search:
                query = query.where(Document.name.ilike(f"%{search}%"))

            query = query.order_by(Document.updated_at.desc()).offset(offset)

            if limit:
                query = query.limit(limit)

            return [self.dto_class.from_orm(item) for item in session.scalars(query)]

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

    def find_by_uri(self, collection_id: str, uri: str) -> Optional[DocumentDTO]:
        with session_context() as session:
            entity = session.scalar(
                select(Document).where(
                    Document.collection_id == collection_id,
                    Document.uri == uri
                )
            )
            return self.dto_class.from_orm(entity) if entity else None

    def list_by_uri(self, collection_id: str, uris: list[str]) -> list[DocumentDTO]:
        with session_context() as session:
            sql = select(Document).where(
                Document.collection_id == collection_id,
                Document.uri.in_(uris)
            )
            return [self.dto_class.from_orm(item) for item in session.scalars(sql)]

    def delete_by_id(self, id: str) -> int:
        from sqlalchemy import delete

        with session_context() as session:
            stmt = delete(Document).where(Document.id == id)
            result = session.execute(stmt)
            session.flush()

        return result.rowcount or 0

    def get_by_status(self, status: str) -> list[DocumentDTO]:
        with session_context() as session:
            sql = select(Document).where(Document.status == status)
            return [self.dto_class.from_orm(item) for item in session.scalars(sql)]


class DocumentChunkRepository(BaseRepository[DocumentChunk, DocumentChunkDTO]):
    """Repository for DocumentChunk operations."""

    def __init__(self):
        super().__init__(DocumentChunk, DocumentChunkDTO)

    def get_by_document(self, document_id: str) -> list[DocumentChunkDTO]:
        with session_context() as session:
            sql = select(DocumentChunk).where(DocumentChunk.document_id == document_id)
            return [self.dto_class.from_orm(item) for item in session.scalars(sql)]

    def get_by_collection(self, collection_id: str) -> list[DocumentChunkDTO]:
        with session_context() as session:
            sql = select(DocumentChunk).where(DocumentChunk.collection_id == collection_id)
            return [self.dto_class.from_orm(item) for item in session.scalars(sql)]

    def get_by_vector_id(self, vector_id: str) -> Optional[DocumentChunkDTO]:
        with session_context() as session:
            sql = select(DocumentChunk).where(DocumentChunk.vector_id == vector_id)
            entity = session.scalar(sql)
            return self.dto_class.from_orm(entity) if entity else None

    def get_by_vector_ids(self, vector_ids: list[str]) -> list[DocumentChunkDTO]:
        with session_context() as session:
            sql = select(DocumentChunk).where(DocumentChunk.vector_id.in_(vector_ids))
            return [self.dto_class.from_orm(item) for item in session.scalars(sql)]

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
