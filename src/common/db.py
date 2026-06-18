"""Database engine, session factory and declarative base for ``app_db``."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.common.config import Settings, get_settings


class Base(DeclarativeBase):
    """Declarative base for all operational models."""


def make_engine(settings: Settings | None = None):  # type: ignore[no-untyped-def]
    """Create a SQLAlchemy engine for the operational Postgres."""
    settings = settings or get_settings()
    return create_engine(settings.app_db_dsn, pool_pre_ping=True, future=True)


_session_factory: sessionmaker[Session] | None = None


def get_session_factory() -> sessionmaker[Session]:
    """Return a lazily-built, process-wide session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=make_engine(), expire_on_commit=False)
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
