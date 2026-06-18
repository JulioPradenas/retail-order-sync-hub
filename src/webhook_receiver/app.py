"""Webhook receiver — signature check, dedupe, bronze log, publish to Pub/Sub.

Two endpoints (``/webhooks/mercadolibre`` and ``/webhooks/paris``) share one
handler. New events are written to bronze and published to
``marketplace.events``; duplicates short-circuit with 200 and no reprocessing.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse

from src.common.config import Settings, get_settings
from src.common.logging import get_logger
from src.common.otel import get_tracer
from src.common.signing import SIGNATURE_HEADER, verify_signature
from src.webhook_receiver.publisher import Publisher, PubSubPublisher
from src.webhook_receiver.store import DbWebhookStore, WebhookStore

log = get_logger()
tracer = get_tracer("webhook_receiver")

EventIdFn = Callable[[dict[str, Any]], str]


def _ml_event_id(body: dict[str, Any]) -> str:
    if body.get("_id"):
        return str(body["_id"])
    return f"{body.get('resource', '')}:{body.get('sent', '')}"


def _paris_event_id(body: dict[str, Any]) -> str:
    return str(body["event_id"])


def _envelope_bytes(envelope: dict[str, Any]) -> bytes:
    return json.dumps(envelope, separators=(",", ":"), sort_keys=True).encode()


def create_app(
    *,
    settings: Settings | None = None,
    store: WebhookStore | None = None,
    publisher: Publisher | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    store = store or DbWebhookStore()
    publisher = publisher or PubSubPublisher(settings)
    app = FastAPI(title="webhook-receiver", version="0.1.0")

    async def handle(
        request: Request, source: str, signature_header: str, secret: str, event_id_of: EventIdFn
    ) -> Response:
        raw = await request.body()
        signature = request.headers.get(signature_header, "")
        if not verify_signature(secret, raw, signature):
            log.warning("webhook.invalid_signature", source=source)
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": "invalid signature"}
            )

        try:
            payload: dict[str, Any] = json.loads(raw)
            event_id = event_id_of(payload)
        except (json.JSONDecodeError, KeyError, TypeError):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST, content={"detail": "malformed payload"}
            )

        with tracer.start_as_current_span("webhook.receive") as span:
            span.set_attribute("marketplace", source)
            span.set_attribute("event_id", event_id)
            result = store.record(source, event_id, payload, dict(request.headers))
            span.set_attribute("dedup_status", "new" if result.is_new else "duplicate")

            if result.is_new:
                envelope = {
                    "event_id": event_id,
                    "source": source,
                    "received_at": datetime.now(UTC).isoformat(),
                    "raw_ref": result.raw_ref,
                }
                publisher.publish(
                    settings.pubsub_topic_events,
                    _envelope_bytes(envelope),
                    source=source,
                    event_id=event_id,
                )

        log.info(
            "webhook.received",
            source=source,
            event_id=event_id,
            dedup_status="new" if result.is_new else "duplicate",
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"event_id": event_id, "duplicate": not result.is_new},
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/webhooks/mercadolibre")
    async def mercadolibre(request: Request) -> Response:
        return await handle(
            request, "mercadolibre", "X-Signature", settings.ml_webhook_secret, _ml_event_id
        )

    @app.post("/webhooks/paris")
    async def paris(request: Request) -> Response:
        return await handle(
            request, "paris", SIGNATURE_HEADER, settings.paris_api_secret, _paris_event_id
        )

    return app
