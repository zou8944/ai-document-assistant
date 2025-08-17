"""Database module for AI Document Assistant backend."""

from .base import Base
from .connection import SessionLocal, create_tables, drop_tables, engine, get_db_session
from .initialization import ensure_database_initialized, initialize_database

__all__ = [
    "get_db_session",
    "engine",
    "SessionLocal",
    "Base",
    "create_tables",
    "drop_tables",
    "initialize_database",
    "ensure_database_initialized"
]
