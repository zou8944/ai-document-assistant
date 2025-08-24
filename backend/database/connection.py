"""Database connection and session management."""

import os
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Optional

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


_current_session: ContextVar[Optional[Session]] = ContextVar[Optional[Session]]("_current_session", default=None)


@contextmanager
def session_context() -> Generator[Session, None, None]:
    # 如果有 session 就直接返回
    session = _current_session.get()
    if session:
        yield session

    # 没有 session 则创建新的，同时存储上下文，并在后面全部执行完成后关闭 session
    session = SessionLocal()
    _current_session.set(session)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        _current_session.set(None)
        session.close()

class transaction:
    """事务上下文管理器，用于启动一个长事务"""
    def __init__(self):
        session = _current_session.get()
        if session:
            self.session = session
        else:
            self.session = SessionLocal()
            _current_session.set(self.session)

    async def __aenter__(self):
        _current_session.set(self.session)
        self.session.begin()
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.session.rollback()
        else:
            self.session.commit()
        self.session.expunge_all()
        self.session.close()
        _current_session.set(None)


def create_tables():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)


def drop_tables():
    """Drop all database tables."""
    Base.metadata.drop_all(bind=engine)
