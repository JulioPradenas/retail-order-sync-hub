"""Unit tests for db.py — engine + session_scope."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from src.common.config import Settings
from src.common.db import get_session_factory, make_engine, session_scope


def test_make_engine_passes_dsn_to_create_engine() -> None:
    settings = Settings()
    with patch("src.common.db.create_engine") as mock_ce:
        mock_ce.return_value = MagicMock()
        make_engine(settings)
    mock_ce.assert_called_once_with(settings.app_db_dsn, pool_pre_ping=True, future=True)


def test_session_scope_commits_on_success() -> None:
    session = MagicMock()
    factory = MagicMock(return_value=session)
    with patch("src.common.db.get_session_factory", return_value=factory), session_scope() as s:
        assert s is session
    session.commit.assert_called_once()
    session.close.assert_called_once()
    session.rollback.assert_not_called()


def test_session_scope_rolls_back_on_exception() -> None:
    session = MagicMock()
    factory = MagicMock(return_value=session)
    with (
        patch("src.common.db.get_session_factory", return_value=factory),
        pytest.raises(ValueError, match="oops"),
        session_scope(),
    ):
        raise ValueError("oops")
    session.rollback.assert_called_once()
    session.close.assert_called_once()


def test_get_session_factory_is_singleton() -> None:
    import src.common.db as db_module

    original = db_module._session_factory
    try:
        db_module._session_factory = None
        with patch("src.common.db.make_engine") as mock_engine:
            mock_engine.return_value = MagicMock()
            factory1 = get_session_factory()
            factory2 = get_session_factory()
        assert factory1 is factory2
        mock_engine.assert_called_once()
    finally:
        db_module._session_factory = original
