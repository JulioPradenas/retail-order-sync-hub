"""HTTP retry helper shared by adapters.

Retries transient transport errors and ``429`` responses (honouring
``Retry-After``) with exponential backoff + jitter via tenacity. This is the
*in-request* retry; durable retry across attempts lives in the outbox worker.
"""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)


class RateLimited(Exception):
    def __init__(self, retry_after: float) -> None:
        super().__init__(f"rate limited (retry after {retry_after}s)")
        self.retry_after = retry_after


def _wait(retry_state: RetryCallState) -> float:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if isinstance(exc, RateLimited):
        return min(exc.retry_after, 10.0)
    return wait_exponential_jitter(initial=0.1, max=5.0)(retry_state)


async def request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_attempts: int,
    **kwargs: Any,
) -> httpx.Response:
    """Issue an HTTP request, retrying transient failures and 429s."""
    retryer: AsyncRetrying = AsyncRetrying(
        retry=retry_if_exception_type((RateLimited, httpx.TransportError)),
        stop=stop_after_attempt(max_attempts),
        wait=_wait,
        reraise=True,
    )

    async def _do() -> httpx.Response:
        resp = await client.request(method, url, **kwargs)
        if resp.status_code == 429:
            raise RateLimited(float(resp.headers.get("Retry-After", "1") or 1))
        return resp

    return await retryer(_do)
