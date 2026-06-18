"""Unit tests for MCP read tools — queries mocked, no real DB."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from src.mcp_server.server import (
    _find_failed_orders,
    _get_dlq_depth,
    _get_order_status,
    _trace_order,
)

_VALID_TOKEN = "dev-token"
_NO_SCOPE_TOKEN = "bad"


@pytest.fixture(autouse=True)
def _patch_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_STATIC_TOKENS", f"{_VALID_TOKEN}:orders.read,metrics.read")
    from src.common.config import get_settings
    from src.mcp_server.auth import _token_scopes

    get_settings.cache_clear()
    _token_scopes.cache_clear()


class TestGetOrderStatus:
    def test_returns_order_json(self) -> None:
        order = {
            "internal_id": 1,
            "odoo_order_id": 42,
            "marketplace": "paris",
            "marketplace_order_id": "MP-1",
            "status": "confirmed",
            "last_sync_at": None,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        with patch("src.mcp_server.server.get_order_by_id", return_value=order):
            result = _get_order_status("1", api_token=_VALID_TOKEN)
        data = json.loads(result)
        assert data["marketplace"] == "paris"
        assert data["status"] == "confirmed"

    def test_not_found(self) -> None:
        with patch("src.mcp_server.server.get_order_by_id", return_value=None):
            result = _get_order_status("999", api_token=_VALID_TOKEN)
        assert "not found" in result

    def test_requires_scope(self) -> None:
        with pytest.raises(PermissionError):
            _get_order_status("1", api_token=_NO_SCOPE_TOKEN)


class TestTraceOrder:
    def test_returns_timeline(self) -> None:
        order = {
            "internal_id": 1,
            "odoo_order_id": None,
            "marketplace": "paris",
            "marketplace_order_id": "MP-1",
            "status": "pending",
            "last_sync_at": None,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        outbox = [
            {
                "id": 10,
                "target_adapter": "paris",
                "status": "dlq",
                "attempts": 5,
                "next_attempt_at": "2026-01-01T01:00:00+00:00",
                "error_log": "timeout",
                "created_at": "2026-01-01T00:01:00+00:00",
                "updated_at": "2026-01-01T00:05:00+00:00",
            }
        ]
        with (
            patch("src.mcp_server.server.get_order_by_id", return_value=order),
            patch("src.mcp_server.server.get_outbox_entries", return_value=outbox),
            patch("src.mcp_server.server.get_webhook_events", return_value=[]),
        ):
            result = _trace_order("1", api_token=_VALID_TOKEN)

        data = json.loads(result)
        assert data["order"]["marketplace"] == "paris"
        assert len(data["dlq_entries"]) == 1
        assert len(data["timeline"]) >= 2

    def test_not_found(self) -> None:
        with patch("src.mcp_server.server.get_order_by_id", return_value=None):
            result = _trace_order("999", api_token=_VALID_TOKEN)
        assert "not found" in result


class TestGetDlqDepth:
    def test_returns_depth(self) -> None:
        with patch("src.mcp_server.server.count_dlq_entries", return_value=3):
            result = _get_dlq_depth(api_token=_VALID_TOKEN)
        data = json.loads(result)
        assert data["dlq_depth"] == 3
        assert "checked_at" in data

    def test_requires_metrics_scope(self) -> None:
        with pytest.raises(PermissionError):
            _get_dlq_depth(api_token=_NO_SCOPE_TOKEN)


class TestFindFailedOrders:
    def test_returns_orders(self) -> None:
        orders = [
            {
                "internal_id": 5,
                "marketplace": "mercadolibre",
                "marketplace_order_id": "ML-5",
                "status": "pending",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        ]
        with patch("src.mcp_server.server.find_failed_orders", return_value=orders):
            result = _find_failed_orders(since="24h", api_token=_VALID_TOKEN)
        data = json.loads(result)
        assert data["count"] == 1
        assert data["orders"][0]["marketplace"] == "mercadolibre"

    def test_invalid_since_format(self) -> None:
        result = _find_failed_orders(since="bad", api_token=_VALID_TOKEN)
        assert "Invalid" in result

    def test_invalid_since_unit(self) -> None:
        result = _find_failed_orders(since="7w", api_token=_VALID_TOKEN)
        assert "Invalid unit" in result

    def test_filters_by_marketplace(self) -> None:
        with patch("src.mcp_server.server.find_failed_orders", return_value=[]) as mock:
            _find_failed_orders(since="1h", marketplace="paris", api_token=_VALID_TOKEN)
        mock.assert_called_once()
        assert mock.call_args[0][1] == "paris"

    def test_requires_scope(self) -> None:
        with pytest.raises(PermissionError):
            _find_failed_orders(since="1h", api_token=_NO_SCOPE_TOKEN)
