"""Audit log decorator for MCP write tools (Phase 9).

Every write tool call — whether it succeeds, is denied, or raises — is
recorded in ``mcp_audit_log`` in its own transaction so the record is
written even when the business operation fails.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any, TypeVar

from src.common.db import session_scope
from src.common.models import McpAuditLog

F = TypeVar("F", bound=Callable[..., Any])

# Convention: pass api_token as a kwarg; user_id is the first 16 chars of the token.
_TOKEN_ARG = "api_token"


def _user_id_from_token(token: str) -> str:
    return f"token:{token[:16]}" if token else "token:anonymous"


def audit(scope: str) -> Callable[[F], F]:
    """Wrap a write tool so every call is appended to mcp_audit_log.

    Captures: who called, what params, which scope was used, outcome, latency.
    The audit write runs in a separate session so it always commits,
    even when the business operation fails or the token is denied.
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tool_name = fn.__name__.lstrip("_")
            api_token: str = kwargs.get(_TOKEN_ARG, "") or (
                args[-1] if args and isinstance(args[-1], str) else ""
            )
            user_id = _user_id_from_token(api_token)

            # Params snapshot (exclude token from log)
            log_params = {k: v for k, v in kwargs.items() if k != _TOKEN_ARG}
            if args:
                log_params["_args"] = list(args)

            t0 = time.perf_counter()
            result_status = "ok"
            error_message: str | None = None
            try:
                result = fn(*args, **kwargs)
                return result
            except PermissionError as exc:
                result_status = "denied"
                error_message = str(exc)
                raise
            except Exception as exc:
                result_status = "error"
                error_message = str(exc)
                raise
            finally:
                latency_ms = int((time.perf_counter() - t0) * 1000)
                _write_audit(
                    user_id=user_id,
                    tool_name=tool_name,
                    params_json=log_params,
                    scope_used=scope,
                    result_status=result_status,
                    error_message=error_message,
                    latency_ms=latency_ms,
                )

        return wrapper  # type: ignore[return-value]

    return decorator


def _write_audit(
    *,
    user_id: str,
    tool_name: str,
    params_json: dict[str, Any],
    scope_used: str,
    result_status: str,
    error_message: str | None,
    latency_ms: int,
) -> None:
    try:
        with session_scope() as session:
            session.add(
                McpAuditLog(
                    user_id=user_id,
                    tool_name=tool_name,
                    params_json=params_json,
                    scope_used=scope_used,
                    result_status=result_status,
                    error_message=error_message,
                    latency_ms=latency_ms,
                )
            )
    except Exception:
        pass  # never let audit failure break the caller
