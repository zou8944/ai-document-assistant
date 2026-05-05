#!/usr/bin/env python
"""
One-time migration script: re-index existing documents for the new chat module.

Populates:
- documents.total_tokens
- keyword_occurrences table

Usage:
    cd backend && POSTGRES_HOST=... POSTGRES_PORT=... POSTGRES_DB=... \
        POSTGRES_USER=... POSTGRES_PASSWORD=... \
        uv run python scripts/reindex_existing_documents.py
"""

import logging
import os
import sys

# Ensure backend is on PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from chat.retrieval.document_index import DocumentIndex
from chat.retrieval.keyword_index import KeywordIndex
from database.connection import session_context

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def get_indexed_documents():
    """Fetch all indexed documents with their content."""
    with session_context() as session:
        result = session.execute(text("""
            SELECT id, name, content
            FROM documents
            WHERE status = 'indexed'
        """))
        return [(row[0], row[1], row[2]) for row in result]


def reindex_document(doc_id: str, name: str, content: str) -> None:
    """Re-index a single document for the new chat module."""
    doc_index = DocumentIndex()
    kw_index = KeywordIndex()

    total_tokens = len(content) // 4

    doc_index.index_document(
        document_id=doc_id,
        keywords=[],
        total_tokens=total_tokens,
    )

    kw_index.index_document(
        document_id=doc_id,
        title=name,
        summary="",
        content=content,
        document_name=name,
    )


def main() -> None:
    docs = get_indexed_documents()
    logger.info(f"Found {len(docs)} indexed documents to re-index")

    success = 0
    failed = 0

    for doc_id, name, content in docs:
        try:
            reindex_document(doc_id, name, content)
            success += 1
            logger.info(f"Re-indexed: {name} ({doc_id})")
        except Exception as e:
            failed += 1
            logger.error(f"Failed to re-index {name} ({doc_id}): {e}")

    logger.info(f"Done. Success: {success}, Failed: {failed}")


if __name__ == "__main__":
    main()
