"""Database module for AI Document Assistant backend."""

from database.base import Base
from database.connection import (
    SessionLocal,
    create_tables,
    drop_tables,
    engine,
    get_db_session,
)

# Note: initialization functions are available but not imported here to avoid circular imports
# Import them directly from database.initialization when needed

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
