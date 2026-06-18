"""Unit tests for DbWebhookStore — session mocked."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.webhook_receiver.store import DbWebhookStore


def _ctx(session: MagicMock) -> MagicMock:
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=session)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def test_new_event_inserts_log_and_returns_is_new_true() -> None:
    session = MagicMock()
    session.execute.return_value.first.return_value = ("ev-1",)  # RETURNING row present
    session.add.return_value = None
    session.flush.return_value = None

    # row.id is set after flush — simulate it
    def _add_side_effect(row: MagicMock) -> None:
        row.id = 10

    session.add.side_effect = _add_side_effect

    with patch("src.webhook_receiver.store.session_scope", return_value=_ctx(session)):
        result = DbWebhookStore().record(
            source="paris",
            event_id="ev-1",
            raw_body={"status": "delivered"},
            headers={"X-Sig": "abc"},
        )

    assert result.is_new is True
    assert "webhook_log:10" in result.raw_ref
    session.add.assert_called_once()
    session.flush.assert_called_once()


def test_duplicate_event_skips_log_and_returns_is_new_false() -> None:
    session = MagicMock()
    session.execute.return_value.first.return_value = None  # ON CONFLICT → no RETURNING row

    with patch("src.webhook_receiver.store.session_scope", return_value=_ctx(session)):
        result = DbWebhookStore().record(
            source="paris",
            event_id="ev-dup",
            raw_body={"status": "delivered"},
            headers={},
        )

    assert result.is_new is False
    assert "ev-dup" in result.raw_ref
    session.add.assert_not_called()
