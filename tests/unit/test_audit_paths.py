"""Tests for audit decorator error paths and _write_audit exception handling."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from src.mcp_server.audit import _write_audit, audit


def _make_ctx(session: MagicMock) -> MagicMock:
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=session)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


class TestAuditDecoratorErrorPath:
    def test_generic_exception_sets_status_error(self) -> None:
        @audit("orders.read")
        def _boom(api_token: str = "") -> str:
            raise ValueError("unexpected failure")

        with (
            patch("src.mcp_server.audit._write_audit") as mock_write,
            pytest.raises(ValueError, match="unexpected failure"),
        ):
            _boom(api_token="tok")

        mock_write.assert_called_once()
        assert mock_write.call_args.kwargs["result_status"] == "error"
        assert "unexpected failure" in mock_write.call_args.kwargs["error_message"]

    def test_permission_error_sets_status_denied(self) -> None:
        @audit("orders.read")
        def _denied(api_token: str = "") -> str:
            raise PermissionError("no scope")

        with (
            patch("src.mcp_server.audit._write_audit") as mock_write,
            pytest.raises(PermissionError),
        ):
            _denied(api_token="tok")

        assert mock_write.call_args.kwargs["result_status"] == "denied"

    def test_success_sets_status_ok(self) -> None:
        @audit("orders.read")
        def _ok(api_token: str = "") -> str:
            return "result"

        with patch("src.mcp_server.audit._write_audit") as mock_write:
            result = _ok(api_token="tok")

        assert result == "result"
        assert mock_write.call_args.kwargs["result_status"] == "ok"

    def test_user_id_extracted_from_token(self) -> None:
        @audit("orders.read")
        def _fn(api_token: str = "") -> str:
            return "ok"

        with patch("src.mcp_server.audit._write_audit") as mock_write:
            _fn(api_token="my-long-token-abc")

        assert mock_write.call_args.kwargs["user_id"] == "token:my-long-token-ab"

    def test_empty_token_yields_anonymous_user_id(self) -> None:
        @audit("orders.read")
        def _fn(api_token: str = "") -> str:
            return "ok"

        with patch("src.mcp_server.audit._write_audit") as mock_write:
            _fn(api_token="")

        assert mock_write.call_args.kwargs["user_id"] == "token:anonymous"


class TestWriteAuditExceptionSwallowed:
    def test_session_scope_raises_does_not_propagate(self) -> None:
        with patch("src.mcp_server.audit.session_scope") as mock_scope:
            mock_scope.side_effect = RuntimeError("db down")
            # Must not raise — exceptions in audit writes are swallowed
            _write_audit(
                user_id="token:test",
                tool_name="test_tool",
                params_json={},
                scope_used="orders.read",
                result_status="ok",
                error_message=None,
                latency_ms=5,
            )

    def test_session_add_raises_does_not_propagate(self) -> None:
        session = MagicMock()
        session.add.side_effect = RuntimeError("insert failed")
        with patch("src.mcp_server.audit.session_scope", return_value=_make_ctx(session)):
            _write_audit(
                user_id="token:test",
                tool_name="test_tool",
                params_json={},
                scope_used="orders.read",
                result_status="ok",
                error_message=None,
                latency_ms=5,
            )
