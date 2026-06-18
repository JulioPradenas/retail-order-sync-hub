"""Handle one ``marketplace.events`` envelope: bronze lookup -> silver -> reconcile.

Poison events (missing bronze row or unnormalizable payload) are published to
the DLQ and acked, so they never block the subscription.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from sqlalchemy import select

from src.common.config import Settings
from src.common.logging import get_logger
from src.common.models import WebhookLog
from src.common.odoo import OdooClient
from src.common.otel import get_meter
from src.reconciler.reconcile import reconcile_to_odoo
from src.subscriber.normalize import PoisonError, normalize_event
from src.subscriber.silver import upsert_order
from src.webhook_receiver.publisher import Publisher

log = get_logger()
_meter = get_meter("subscriber")
_silver_counter = _meter.create_counter(
    "silver_orders_total", description="Orders upserted into the silver layer"
)


class SessionLike(Protocol):
    def scalar(self, statement: Any) -> Any: ...
    def execute(self, statement: Any) -> Any: ...


def _to_dlq(
    publisher: Publisher, settings: Settings, envelope: dict[str, Any], reason: str
) -> None:
    body = json.dumps(
        {"reason": reason, "envelope": envelope}, separators=(",", ":"), sort_keys=True
    ).encode()
    publisher.publish(settings.pubsub_topic_dlq, body, reason="poison")
    log.warning("subscriber.poison", reason=reason, event_id=envelope.get("event_id"))


def handle_envelope(
    envelope: dict[str, Any],
    *,
    session: SessionLike,
    settings: Settings,
    publisher: Publisher,
    odoo: OdooClient | None = None,
) -> str:
    """Process one envelope. Returns ``processed`` or ``poison``."""
    event_id = envelope.get("event_id")
    source = str(envelope.get("source", ""))
    raw = session.scalar(
        select(WebhookLog.raw_body).where(
            WebhookLog.event_id == event_id, WebhookLog.source == source
        )
    )
    if raw is None:
        _to_dlq(publisher, settings, envelope, "bronze row not found")
        return "poison"

    try:
        normalized = normalize_event(source, raw)
        upsert_order(session, normalized)  # type: ignore[arg-type]
        _silver_counter.add(1, {"marketplace": normalized.marketplace})
        if (
            odoo is not None
            and normalized.odoo_order_id is not None
            and normalized.status == "delivered"
        ):
            reconcile_to_odoo(odoo, normalized.odoo_order_id, normalized.status)
    except PoisonError as exc:
        _to_dlq(publisher, settings, envelope, str(exc))
        return "poison"

    log.info(
        "subscriber.processed",
        event_id=event_id,
        marketplace=normalized.marketplace,
        status=normalized.status,
    )
    return "processed"
