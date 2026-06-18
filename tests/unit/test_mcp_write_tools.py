"""Unit tests for MCP write tools + audit log."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from src.mcp_server.write_tools import _drain_dlq, _replay_dlq_message, _retry_failed_sync

_OPERATOR_TOKEN = "op-token"
_ADMIN_TOKEN = "admin-token"
_VIEWER_TOKEN = "viewer-token"


@pytest.fixture(autouse=True)
def _patch_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "MCP_STATIC_TOKENS",
        (
            f"{_OPERATOR_TOKEN}:orders.read,metrics.read,outbox.retry,dlq.replay;"
            f"{_ADMIN_TOKEN}:orders.read,metrics.read,outbox.retry,dlq.replay,dlq.admin;"
            f"{_VIEWER_TOKEN}:orders.read,metrics.read"
        ),
    )
    from src.common.config import get_settings
    from src.mcp_server.auth import _token_scopes

    get_settings.cache_clear()
    _token_scopes.cache_clear()


def _make_outbox_row(id: int = 1, status: str = "dlq") -> MagicMock:
    row = MagicMock()
    row.id = id
    row.aggregate_id = "1"
    row.target_adapter = "paris"
    row.status = status
    row.attempts = 5
    row.error_log = "timeout"
    return row


class TestReplayDlqMessage:
    def test_resets_dlq_entry(self) -> None:
        row = _make_outbox_row(id=10, status="dlq")

        with (
            patch("src.mcp_server.write_tools.session_scope") as mock_scope,
            patch("src.mcp_server.audit._write_audit"),
        ):
            session = MagicMock()
            session.get.return_value = row
            mock_scope.return_value.__enter__ = MagicMock(return_value=session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            result = _replay_dlq_message("10", api_token=_OPERATOR_TOKEN)

        data = json.loads(result)
        assert data["replayed"] is True
        assert data["outbox_id"] == 10
        assert row.status == "pending"
        assert row.attempts == 0

    def test_not_found(self) -> None:
        with (
            patch("src.mcp_server.write_tools.session_scope") as mock_scope,
            patch("src.mcp_server.audit._write_audit"),
        ):
            session = MagicMock()
            session.get.return_value = None
            mock_scope.return_value.__enter__ = MagicMock(return_value=session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            result = _replay_dlq_message("999", api_token=_OPERATOR_TOKEN)

        assert "not found" in result

    def test_wrong_status_noop(self) -> None:
        row = _make_outbox_row(id=1, status="done")

        with (
            patch("src.mcp_server.write_tools.session_scope") as mock_scope,
            patch("src.mcp_server.audit._write_audit"),
        ):
            session = MagicMock()
            session.get.return_value = row
            mock_scope.return_value.__enter__ = MagicMock(return_value=session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            result = _replay_dlq_message("1", api_token=_OPERATOR_TOKEN)

        assert "not 'dlq'" in result
        assert row.status == "done"  # unchanged

    def test_invalid_id(self) -> None:
        with patch("src.mcp_server.audit._write_audit"):
            result = _replay_dlq_message("not-a-number", api_token=_OPERATOR_TOKEN)
        assert "Invalid" in result

    def test_requires_dlq_replay_scope(self) -> None:
        with patch("src.mcp_server.audit._write_audit"), pytest.raises(PermissionError):
            _replay_dlq_message("1", api_token=_VIEWER_TOKEN)

    def test_audit_recorded_on_success(self) -> None:
        row = _make_outbox_row(id=5, status="dlq")

        with (
            patch("src.mcp_server.write_tools.session_scope") as mock_scope,
            patch("src.mcp_server.audit._write_audit") as mock_audit,
        ):
            session = MagicMock()
            session.get.return_value = row
            mock_scope.return_value.__enter__ = MagicMock(return_value=session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            _replay_dlq_message("5", api_token=_OPERATOR_TOKEN)

        mock_audit.assert_called_once()
        kwargs = mock_audit.call_args.kwargs
        assert kwargs["tool_name"] == "replay_dlq_message"
        assert kwargs["scope_used"] == "dlq.replay"
        assert kwargs["result_status"] == "ok"

    def test_audit_recorded_as_denied_on_permission_error(self) -> None:
        with (
            patch("src.mcp_server.audit._write_audit") as mock_audit,
            pytest.raises(PermissionError),
        ):
            _replay_dlq_message("1", api_token=_VIEWER_TOKEN)

        mock_audit.assert_called_once()
        assert mock_audit.call_args.kwargs["result_status"] == "denied"


class TestRetryFailedSync:
    def test_resets_existing_dlq_entry(self) -> None:
        order = MagicMock()
        order.internal_id = 1
        order.odoo_order_id = 42
        order.marketplace_order_id = "MP-1"

        dlq_entry = _make_outbox_row(id=3, status="dlq")

        with (
            patch("src.mcp_server.write_tools.session_scope") as mock_scope,
            patch("src.mcp_server.audit._write_audit"),
        ):
            session = MagicMock()
            session.get.return_value = order
            session.scalars.return_value = [dlq_entry]
            mock_scope.return_value.__enter__ = MagicMock(return_value=session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            result = _retry_failed_sync("1", api_token=_OPERATOR_TOKEN)

        data = json.loads(result)
        assert data["retried"] is True
        assert data["entries_reset"] == 1
        assert dlq_entry.status == "pending"
        assert dlq_entry.attempts == 0

    def test_order_not_found(self) -> None:
        with (
            patch("src.mcp_server.write_tools.session_scope") as mock_scope,
            patch("src.mcp_server.audit._write_audit"),
        ):
            session = MagicMock()
            session.get.return_value = None
            mock_scope.return_value.__enter__ = MagicMock(return_value=session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            result = _retry_failed_sync("999", api_token=_OPERATOR_TOKEN)

        assert "not found" in result

    def test_requires_outbox_retry_scope(self) -> None:
        with patch("src.mcp_server.audit._write_audit"), pytest.raises(PermissionError):
            _retry_failed_sync("1", api_token=_VIEWER_TOKEN)


class TestDrainDlq:
    def test_dry_run_lists_without_mutating(self) -> None:
        rows = [_make_outbox_row(1, "dlq"), _make_outbox_row(2, "dlq")]

        with (
            patch("src.mcp_server.write_tools.session_scope") as mock_scope,
            patch("src.mcp_server.audit._write_audit"),
        ):
            session = MagicMock()
            session.scalars.return_value = rows
            mock_scope.return_value.__enter__ = MagicMock(return_value=session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            result = _drain_dlq(dry_run=True, api_token=_ADMIN_TOKEN)

        data = json.loads(result)
        assert data["dry_run"] is True
        assert data["dlq_count"] == 2
        # entries must not be mutated
        assert rows[0].status == "dlq"
        assert rows[1].status == "dlq"

    def test_drain_resets_all_entries(self) -> None:
        rows = [_make_outbox_row(1, "dlq"), _make_outbox_row(2, "dlq")]

        with (
            patch("src.mcp_server.write_tools.session_scope") as mock_scope,
            patch("src.mcp_server.audit._write_audit"),
        ):
            session = MagicMock()
            session.scalars.return_value = rows
            mock_scope.return_value.__enter__ = MagicMock(return_value=session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            result = _drain_dlq(dry_run=False, api_token=_ADMIN_TOKEN)

        data = json.loads(result)
        assert data["dry_run"] is False
        assert data["dlq_count"] == 2
        assert all(r.status == "pending" for r in rows)
        assert all(r.attempts == 0 for r in rows)

    def test_requires_dlq_admin_scope(self) -> None:
        with patch("src.mcp_server.audit._write_audit"), pytest.raises(PermissionError):
            _drain_dlq(dry_run=True, api_token=_OPERATOR_TOKEN)

    def test_operator_cannot_drain(self) -> None:
        with (
            patch("src.mcp_server.audit._write_audit"),
            pytest.raises(PermissionError, match=r"dlq\.admin"),
        ):
            _drain_dlq(dry_run=False, api_token=_OPERATOR_TOKEN)
