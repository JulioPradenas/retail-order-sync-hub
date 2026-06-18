"""Self-contained SQLite storage for paris-mock.

Kept entirely separate from ``app_db`` — the mock owns its data so it never
pollutes the system under test.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, create_engine, func
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class ParisBase(DeclarativeBase):
    """Declarative base for the mock's own tables."""


class ParisOrder(ParisBase):
    __tablename__ = "paris_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    buyer: Mapped[str] = mapped_column(String(255))
    external_ref: Mapped[str | None] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(30), default="created")
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ParisWebhook(ParisBase):
    __tablename__ = "paris_webhooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(500), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def make_engine(db_path: str) -> Engine:
    """Create the SQLite engine (use ``:memory:`` for tests)."""
    url = (
        "sqlite+pysqlite:///:memory:" if db_path == ":memory:" else f"sqlite+pysqlite:///{db_path}"
    )
    engine = create_engine(url, future=True)
    ParisBase.metadata.create_all(engine)
    return engine


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def scoped(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
