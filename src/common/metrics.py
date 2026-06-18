"""Custom business metrics (Phase 6).

Instruments are created on the proxy meter at import time and activate once a
real ``MeterProvider`` is installed via ``setup_metrics`` — so importing this
module before OTel setup is safe.
"""

from __future__ import annotations

from collections.abc import Iterable

from opentelemetry.metrics import CallbackOptions, Observation
from sqlalchemy import func, select

from src.common.db import session_scope
from src.common.models import OutboxEntry
from src.common.otel import get_meter

_meter = get_meter("rosh.business")

webhook_received = _meter.create_counter(
    "webhook_received", description="Inbound webhooks received", unit="1"
)
order_sync = _meter.create_counter(
    "order_sync", description="Outbox push outcomes (status=done|retry|dlq)", unit="1"
)
order_sync_duration = _meter.create_histogram(
    "order_sync_duration_seconds", description="Time to push an order to a marketplace", unit="s"
)


def _count_outbox(status: str) -> int:
    with session_scope() as session:
        value = session.scalar(
            select(func.count()).select_from(OutboxEntry).where(OutboxEntry.status == status)
        )
        return int(value or 0)


def _outbox_pending_cb(options: CallbackOptions) -> Iterable[Observation]:
    yield Observation(_count_outbox("pending"))


def _dlq_depth_cb(options: CallbackOptions) -> Iterable[Observation]:
    yield Observation(_count_outbox("dlq"))


def register_db_gauges() -> None:
    """Register observable gauges backed by app_db counts (call after setup_metrics)."""
    _meter.create_observable_gauge("outbox_pending", callbacks=[_outbox_pending_cb])
    _meter.create_observable_gauge("dlq_depth", callbacks=[_dlq_depth_cb])
