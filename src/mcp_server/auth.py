"""MCP IAM scaffold (Phase 8 — V1 static tokens).

Static token map is loaded from ``MCP_STATIC_TOKENS`` env var (format:
``"token1:scope_a,scope_b;token2:scope_c"``).

Phase 9 will add JWT validation and Secret Manager integration.
"""

from __future__ import annotations

from functools import lru_cache

from src.common.config import get_settings


@lru_cache(maxsize=1)
def _token_scopes() -> dict[str, frozenset[str]]:
    """Parse static token map from settings (cached per process)."""
    raw = get_settings().mcp_static_tokens.strip()
    result: dict[str, frozenset[str]] = {}
    for pair in raw.split(";"):
        pair = pair.strip()
        if not pair:
            continue
        token, _, scopes_str = pair.partition(":")
        result[token.strip()] = frozenset(s.strip() for s in scopes_str.split(",") if s.strip())
    return result


def validate_token(token: str) -> frozenset[str]:
    """Return the scopes granted to ``token``, or empty set if unknown."""
    return _token_scopes().get(token, frozenset())


def require_scope(token: str, scope: str) -> None:
    """Raise ``PermissionError`` if ``token`` does not carry ``scope``."""
    granted = validate_token(token)
    if scope not in granted:
        raise PermissionError(
            f"Token does not have required scope '{scope}'. "
            f"Granted scopes: {sorted(granted) or 'none'}."
        )


# Role presets — convenience for generating static token values.
ROLES: dict[str, frozenset[str]] = {
    "viewer": frozenset({"orders.read", "metrics.read"}),
    "operator": frozenset({"orders.read", "metrics.read", "outbox.retry", "dlq.replay"}),
    "admin": frozenset({"orders.read", "metrics.read", "outbox.retry", "dlq.replay", "dlq.admin"}),
}
