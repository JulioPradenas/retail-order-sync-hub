import httpx
import pytest
from src.adapters.base import AdapterError, OrderDTO, OrderItemDTO
from src.adapters.paris import ParisAdapter
from src.common.config import Settings

_ORDER = OrderDTO(
    odoo_order_id=1, buyer="Comex", items=[OrderItemDTO(sku="A", qty=2)], external_ref="odoo-1"
)


def _adapter(handler) -> ParisAdapter:  # type: ignore[no-untyped-def]
    settings = Settings(
        paris_api_key="k", adapter_max_attempts=4, paris_base_url="http://paris.test"
    )
    client = httpx.AsyncClient(
        base_url=settings.paris_base_url,
        headers={"X-API-Key": "k"},
        transport=httpx.MockTransport(handler),
    )
    return ParisAdapter(settings=settings, http_client=client)


async def test_push_order_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-API-Key"] == "k"
        return httpx.Response(201, json={"id": "p1", "status": "created"})

    result = await _adapter(handler).push_order(_ORDER)
    assert result.marketplace_order_id == "p1"
    assert result.status == "created"


async def test_push_order_retries_on_429_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={})
        return httpx.Response(201, json={"id": "p2", "status": "created"})

    result = await _adapter(handler).push_order(_ORDER)
    assert result.marketplace_order_id == "p2"
    assert calls["n"] == 2  # one retry after the 429


async def test_push_order_permanent_4xx_raises_typed_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"detail": "bad"})

    with pytest.raises(AdapterError) as exc_info:
        await _adapter(handler).push_order(_ORDER)
    assert exc_info.value.permanent is True
