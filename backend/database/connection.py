"""Database connection and session management."""

import os
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from database.base import Base


def _configure_sqlite(dbapi_connection, connection_record):
    """Configure SQLite-specific settings."""
    cursor = dbapi_connection.cursor()
    # Enable WAL mode for better concurrency
    cursor.execute("PRAGMA journal_mode=WAL")
    # Set cache size (64MB)
    cursor.execute("PRAGMA cache_size=16384")
    # Enable foreign key constraints
    cursor.execute("PRAGMA foreign_keys=ON")
    # Set synchronous mode to NORMAL
    cursor.execute("PRAGMA synchronous=NORMAL")
    # Optimize temporary storage
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.close()


# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("DATABASE_DEBUG", "false").lower() == "true",
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

# Configure SQLite optimizations if using SQLite
if "sqlite" in DATABASE_URL:
    event.listen(Engine, "connect", _configure_sqlite)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session() -> Generator[Session, None, None]:
    """
    Get a database session.

    Yields:
        Session: SQLAlchemy database session
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def get_db_session_context() -> Generator[Session, None, None]:
    """
    Get a database session with context management.

    Yields:
        Session: SQLAlchemy database session
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_tables():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)


def drop_tables():
    """Drop all database tables."""
    Base.metadata.drop_all(bind=engine)
