"""Database connection and session management."""

import os
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

_host = os.environ["POSTGRES_HOST"]
_port = os.environ.get("POSTGRES_PORT", "5432")
_user = os.environ["POSTGRES_USER"]
_password = os.environ["POSTGRES_PASSWORD"]
_db = os.environ["POSTGRES_DB"]
DATABASE_URL = f"postgresql://{_user}:{_password}@{_host}:{_port}/{_db}"

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


_current_session: ContextVar[Optional[Session]] = ContextVar[Optional[Session]]("_current_session", default=None)


@contextmanager
def session_context() -> Generator[Session, None, None]:
    # 如果有 session 就直接返回
    session = _current_session.get()
    if session:
        yield session
        return

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
        _ = exc_val, exc_tb  # Unused parameters
        if exc_type:
            self.session.rollback()
        else:
            self.session.commit()
        self.session.expunge_all()
        self.session.close()
        _current_session.set(None)
