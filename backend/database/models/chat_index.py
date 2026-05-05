"""Chat indexing models for keyword-based retrieval."""

from sqlalchemy import Column, Index, Integer, String, Text

from database.base import Base


class KeywordOccurrence(Base):
    """Keyword inverted index for document search."""

    __tablename__ = "keyword_occurrences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String(200), nullable=False, index=True)
    document_id = Column(String(100), nullable=False, index=True)
    document_name = Column(String(200))
    context_snippet = Column(Text)
    position = Column(Integer)

    __table_args__ = (
        Index("idx_keyword_occ_doc", "document_id"),
        Index("idx_keyword_occ_kw_doc", "keyword", "document_id"),
    )
