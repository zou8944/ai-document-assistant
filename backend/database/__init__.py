"""Database module for AI Document Assistant backend."""

from database.base import Base
from database.connection import (
    SessionLocal,
    create_tables,
    drop_tables,
    engine,
    session_context,
    transaction,
)

__all__ = [
    "engine",
    "SessionLocal",
    "Base",
    "create_tables",
    "drop_tables",
    "session_context",
    "transaction",
]
