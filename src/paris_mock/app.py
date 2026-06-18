"""paris-mock — a controllable stand-in for the Paris marketplace.

FastAPI service with API-key auth, its own SQLite store and an admin endpoint
to fire signed webhooks on demand (used by integration and chaos tests).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Annotated, Any

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from src.common.config import Settings, get_settings
from src.common.signing import SIGNATURE_HEADER, sign_payload
from src.paris_mock.storage import ParisOrder, ParisWebhook, make_engine, scoped, session_factory


class OrderItemIn(BaseModel):
    sku: str
    qty: int = Field(gt=0)


class OrderCreateIn(BaseModel):
    buyer: str
    items: list[OrderItemIn] = Field(min_length=1)
    external_ref: str | None = None


class OrderOut(BaseModel):
    id: str
    buyer: str
    status: str
    external_ref: str | None
    items: list[dict[str, Any]]
    created_at: datetime


class WebhookRegisterIn(BaseModel):
    url: str


class EmitWebhookIn(BaseModel):
    status: str = "delivered"


def _to_out(order: ParisOrder) -> OrderOut:
    return OrderOut(
        id=order.id,
        buyer=order.buyer,
        status=order.status,
        external_ref=order.external_ref,
        items=order.items,
        created_at=order.created_at,
    )


def create_app(settings: Settings | None = None, db_path: str | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = make_engine(db_path or settings.paris_mock_db_path)
    factory = session_factory(engine)
    app = FastAPI(title="paris-mock", version="0.1.0")

    def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
        if x_api_key != settings.paris_api_key:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or missing X-API-Key")

    auth = Depends(require_api_key)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
    def create_order(payload: OrderCreateIn, _: None = auth) -> OrderOut:
        with scoped(factory) as session:
            if payload.external_ref:
                existing = session.scalar(
                    select(ParisOrder).where(ParisOrder.external_ref == payload.external_ref)
                )
                if existing is not None:
                    return _to_out(existing)
            order = ParisOrder(
                id=uuid.uuid4().hex,
                buyer=payload.buyer,
                external_ref=payload.external_ref,
                status="created",
                items=[item.model_dump() for item in payload.items],
            )
            session.add(order)
            session.flush()
            return _to_out(order)

    @app.get("/orders/{order_id}", response_model=OrderOut)
    def get_order(order_id: str, _: None = auth) -> OrderOut:
        with scoped(factory) as session:
            order = session.get(ParisOrder, order_id)
            if order is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "order not found")
            return _to_out(order)

    @app.post("/webhooks/register", status_code=status.HTTP_201_CREATED)
    def register_webhook(payload: WebhookRegisterIn, _: None = auth) -> dict[str, str]:
        with scoped(factory) as session:
            existing = session.scalar(select(ParisWebhook).where(ParisWebhook.url == payload.url))
            if existing is None:
                session.add(ParisWebhook(url=payload.url))
            return {"registered": payload.url}

    @app.post("/admin/orders/{order_id}/emit-webhook")
    async def emit_webhook(order_id: str, payload: EmitWebhookIn, _: None = auth) -> dict[str, Any]:
        with scoped(factory) as session:
            order = session.get(ParisOrder, order_id)
            if order is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "order not found")
            order.status = payload.status
            event = {
                "event_id": uuid.uuid4().hex,
                "source": "paris",
                "order_id": order.id,
                "external_ref": order.external_ref,
                "status": payload.status,
            }
            urls = list(session.scalars(select(ParisWebhook.url)))

        body = _json_bytes(event)
        signature = sign_payload(settings.paris_api_secret, body)
        deliveries = await _deliver(urls, body, signature)
        return {"event": event, "deliveries": deliveries}

    return app


def _json_bytes(event: dict[str, Any]) -> bytes:
    return json.dumps(event, separators=(",", ":"), sort_keys=True).encode()


async def _deliver(urls: list[str], body: bytes, signature: str) -> list[dict[str, Any]]:
    deliveries: list[dict[str, Any]] = []
    headers = {"Content-Type": "application/json", SIGNATURE_HEADER: signature}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for url in urls:
            try:
                resp = await client.post(url, content=body, headers=headers)
                deliveries.append({"url": url, "status_code": resp.status_code})
            except httpx.HTTPError as exc:
                deliveries.append({"url": url, "error": str(exc)})
    return deliveries
