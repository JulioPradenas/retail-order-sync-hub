"""Paris marketplace adapter (talks to paris-mock)."""

from __future__ import annotations

import httpx

from src.adapters._http import request_with_retry
from src.adapters.base import AdapterError, OrderDTO, PushResult
from src.common.config import Settings, get_settings


class ParisAdapter:
    name = "paris"

    def __init__(
        self,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._http = http_client

    def _client(self) -> httpx.AsyncClient:
        if self._http is not None:
            return self._http
        return httpx.AsyncClient(
            base_url=self._settings.paris_base_url,
            headers={"X-API-Key": self._settings.paris_api_key},
            timeout=10.0,
        )

    async def _request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        client = self._client()
        try:
            resp = await request_with_retry(
                client, method, path, max_attempts=self._settings.adapter_max_attempts, **kwargs
            )
        finally:
            if self._http is None:
                await client.aclose()
        if resp.status_code >= 400:
            raise AdapterError(
                f"paris {method} {path} -> {resp.status_code}",
                permanent=400 <= resp.status_code < 500,
            )
        return resp

    async def push_order(self, order: OrderDTO) -> PushResult:
        payload = {
            "buyer": order.buyer,
            "items": [{"sku": i.sku, "qty": i.qty} for i in order.items],
            "external_ref": order.external_ref,
        }
        resp = await self._request("POST", "/orders", json=payload)
        data = resp.json()
        return PushResult(marketplace_order_id=data["id"], status=data["status"])

    async def update_stock(self, sku: str, qty: int) -> None:
        # paris-mock has no stock endpoint; no-op kept for protocol conformance.
        return None

    async def get_order_status(self, marketplace_order_id: str) -> str:
        resp = await self._request("GET", f"/orders/{marketplace_order_id}")
        status: str = resp.json()["status"]
        return status
