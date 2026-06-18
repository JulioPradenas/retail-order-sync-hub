"""Unit tests for MCP query helpers — DB mocked via session_scope patch."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from src.mcp_server.queries import (
    count_dlq_entries,
    find_failed_orders,
    get_order_by_id,
    get_outbox_entries,
    get_webhook_events,
)

_NOW = datetime.now(UTC)


def _ctx(session: MagicMock) -> MagicMock:
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=session)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _order_row(**kwargs: object) -> MagicMock:
    row = MagicMock()
    row.internal_id = kwargs.get("internal_id", 1)
    row.odoo_order_id = kwargs.get("odoo_order_id", 42)
    row.marketplace = kwargs.get("marketplace", "paris")
    row.marketplace_order_id = kwargs.get("marketplace_order_id", "MP-1")
    row.status = kwargs.get("status", "confirmed")
    row.last_sync_at = kwargs.get("last_sync_at")
    row.created_at = _NOW
    row.updated_at = _NOW
    return row


class TestGetOrderById:
    def test_digit_id_calls_session_get(self) -> None:
        session = MagicMock()
        session.get.return_value = _order_row()
        with patch("src.mcp_server.queries.session_scope", return_value=_ctx(session)):
            result = get_order_by_id("1")
        assert result is not None
        assert result["marketplace"] == "paris"
        session.get.assert_called_once()

    def test_string_id_calls_scalar(self) -> None:
        session = MagicMock()
        session.scalar.return_value = _order_row(marketplace_order_id="MP-99")
        with patch("src.mcp_server.queries.session_scope", return_value=_ctx(session)):
            result = get_order_by_id("MP-99")
        assert result is not None
        assert result["marketplace_order_id"] == "MP-99"

    def test_not_found_returns_none(self) -> None:
        session = MagicMock()
        session.get.return_value = None
        with patch("src.mcp_server.queries.session_scope", return_value=_ctx(session)):
            assert get_order_by_id("999") is None

    def test_last_sync_at_present(self) -> None:
        session = MagicMock()
        session.get.return_value = _order_row(last_sync_at=_NOW)
        with patch("src.mcp_server.queries.session_scope", return_value=_ctx(session)):
            result = get_order_by_id("1")
        assert result is not None
        assert result["last_sync_at"] is not None


class TestGetOutboxEntries:
    def test_returns_list(self) -> None:
        row = MagicMock()
        row.id = 10
        row.target_adapter = "paris"
        row.status = "dlq"
        row.attempts = 5
        row.next_attempt_at = _NOW
        row.error_log = "timeout"
        row.created_at = _NOW
        row.updated_at = _NOW

        session = MagicMock()
        session.scalars.return_value = [row]
        with patch("src.mcp_server.queries.session_scope", return_value=_ctx(session)):
            result = get_outbox_entries("1")
        assert len(result) == 1
        assert result[0]["id"] == 10
        assert result[0]["status"] == "dlq"

    def test_empty_aggregate(self) -> None:
        session = MagicMock()
        session.scalars.return_value = []
        with patch("src.mcp_server.queries.session_scope", return_value=_ctx(session)):
            assert get_outbox_entries("99") == []


class TestGetWebhookEvents:
    def test_with_event_id(self) -> None:
        row = MagicMock()
        row.id = 1
        row.event_id = "ev-1"
        row.source = "paris"
        row.received_at = _NOW

        session = MagicMock()
        session.scalars.return_value = [row]
        with patch("src.mcp_server.queries.session_scope", return_value=_ctx(session)):
            result = get_webhook_events(event_id="ev-1")
        assert result[0]["event_id"] == "ev-1"

    def test_with_source_filter(self) -> None:
        session = MagicMock()
        session.scalars.return_value = []
        with patch("src.mcp_server.queries.session_scope", return_value=_ctx(session)):
            result = get_webhook_events(source="paris")
        assert result == []

    def test_no_filter(self) -> None:
        session = MagicMock()
        session.scalars.return_value = []
        with patch("src.mcp_server.queries.session_scope", return_value=_ctx(session)):
            assert get_webhook_events() == []


class TestCountDlqEntries:
    def test_returns_count(self) -> None:
        session = MagicMock()
        session.scalar.return_value = 7
        with patch("src.mcp_server.queries.session_scope", return_value=_ctx(session)):
            assert count_dlq_entries() == 7

    def test_none_becomes_zero(self) -> None:
        session = MagicMock()
        session.scalar.return_value = None
        with patch("src.mcp_server.queries.session_scope", return_value=_ctx(session)):
            assert count_dlq_entries() == 0


class TestFindFailedOrders:
    def test_without_marketplace(self) -> None:
        row = _order_row(marketplace="paris", marketplace_order_id="MP-1", status="pending")
        session = MagicMock()
        session.scalars.return_value = [row]
        with patch("src.mcp_server.queries.session_scope", return_value=_ctx(session)):
            result = find_failed_orders(_NOW)
        assert len(result) == 1
        assert result[0]["marketplace"] == "paris"

    def test_with_marketplace_filter(self) -> None:
        session = MagicMock()
        session.scalars.return_value = []
        with patch("src.mcp_server.queries.session_scope", return_value=_ctx(session)):
            result = find_failed_orders(_NOW, marketplace="mercadolibre")
        assert result == []
