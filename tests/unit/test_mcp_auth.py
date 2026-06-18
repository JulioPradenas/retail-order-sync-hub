"""Unit tests for MCP auth scaffold."""

from __future__ import annotations

import pytest
from src.mcp_server.auth import require_scope, validate_token


@pytest.fixture(autouse=True)
def _clear_caches() -> None:
    from src.common.config import get_settings
    from src.mcp_server.auth import _token_scopes

    get_settings.cache_clear()
    _token_scopes.cache_clear()


class TestValidateToken:
    def test_known_token_returns_scopes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MCP_STATIC_TOKENS", "tok1:orders.read,metrics.read")
        from src.mcp_server.auth import _token_scopes

        _token_scopes.cache_clear()
        scopes = validate_token("tok1")
        assert "orders.read" in scopes
        assert "metrics.read" in scopes

    def test_unknown_token_returns_empty(self) -> None:
        scopes = validate_token("bad-token")
        assert scopes == frozenset()

    def test_multiple_tokens_parsed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MCP_STATIC_TOKENS", "admin:orders.read,dlq.admin;viewer:orders.read")
        from src.mcp_server.auth import _token_scopes

        _token_scopes.cache_clear()
        assert "dlq.admin" in validate_token("admin")
        assert "dlq.admin" not in validate_token("viewer")
        assert "orders.read" in validate_token("viewer")


class TestRequireScope:
    def test_passes_when_scope_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MCP_STATIC_TOKENS", "good:orders.read")
        from src.mcp_server.auth import _token_scopes

        _token_scopes.cache_clear()
        require_scope("good", "orders.read")  # must not raise

    def test_raises_when_scope_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MCP_STATIC_TOKENS", "limited:metrics.read")
        from src.mcp_server.auth import _token_scopes

        _token_scopes.cache_clear()
        with pytest.raises(PermissionError, match=r"orders\.read"):
            require_scope("limited", "orders.read")

    def test_raises_for_empty_token(self) -> None:
        with pytest.raises(PermissionError):
            require_scope("", "orders.read")

    def test_raises_for_unknown_token(self) -> None:
        with pytest.raises(PermissionError):
            require_scope("does-not-exist", "orders.read")
