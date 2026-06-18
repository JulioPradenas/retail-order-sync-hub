"""Process outbox entries: push to adapters, retry with backoff, DLQ on exhaustion.

``process_entry`` is pure (mutates the row, talks to adapter + publisher) so it
unit-tests without a database; ``process_pending`` wraps it with the query and
transaction.
"""

from __future__ import annotations

import json
import random
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from src.adapters.base import MarketplaceAdapter, OrderDTO
from src.common.config import Settings, get_settings
from src.common.db import session_scope
from src.common.logging import get_logger
from src.common.metrics import order_sync, order_sync_duration
from src.common.models import OutboxEntry
from src.webhook_receiver.publisher import Publisher, PubSubPublisher

log = get_logger()


def _backoff(attempts: int) -> timedelta:
    base = min(2**attempts, 300)
    jitter = random.uniform(0, base * 0.25)
    return timedelta(seconds=base + jitter)


def _dlq_bytes(row: OutboxEntry, error: str) -> bytes:
    return json.dumps(
        {
            "outbox_id": row.id,
            "aggregate_id": row.aggregate_id,
            "target_adapter": row.target_adapter,
            "attempts": row.attempts,
            "error": error,
            "payload": row.payload,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


async def process_entry(
    row: OutboxEntry,
    adapters: dict[str, MarketplaceAdapter],
    publisher: Publisher,
    settings: Settings,
    now: datetime,
) -> str:
    """Process a single entry; mutate it in place. Returns done|retry|dlq."""
    adapter = adapters.get(row.target_adapter)
    t0 = time.perf_counter()
    try:
        if adapter is None:
            raise RuntimeError(f"no adapter registered for '{row.target_adapter}'")
        order = OrderDTO.model_validate(row.payload)
        result = await adapter.push_order(order)
    except Exception as exc:
        row.attempts += 1
        row.error_log = str(exc)
        if row.attempts >= settings.outbox_max_attempts:
            row.status = "dlq"
            publisher.publish(
                settings.pubsub_topic_sync_dlq,
                _dlq_bytes(row, str(exc)),
                aggregate_id=row.aggregate_id,
                target_adapter=row.target_adapter,
            )
            log.warning("outbox.dlq", outbox_id=row.id, attempts=row.attempts, error=str(exc))
            attrs = {"target_adapter": row.target_adapter, "status": "dlq"}
            order_sync.add(1, attrs)
            order_sync_duration.record(time.perf_counter() - t0, attrs)
            return "dlq"
        row.status = "pending"
        row.next_attempt_at = now + _backoff(row.attempts)
        log.info("outbox.retry", outbox_id=row.id, attempts=row.attempts, error=str(exc))
        attrs = {"target_adapter": row.target_adapter, "status": "retry"}
        order_sync.add(1, attrs)
        order_sync_duration.record(time.perf_counter() - t0, attrs)
        return "retry"

    row.status = "done"
    row.error_log = None
    log.info(
        "outbox.done",
        outbox_id=row.id,
        marketplace_order_id=result.marketplace_order_id,
        target_adapter=row.target_adapter,
    )
    attrs = {"target_adapter": row.target_adapter, "status": "done"}
    order_sync.add(1, attrs)
    order_sync_duration.record(time.perf_counter() - t0, attrs)
    return "done"


async def process_pending(
    adapters: dict[str, MarketplaceAdapter],
    publisher: Publisher | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
    batch_size: int = 50,
) -> list[tuple[int, str]]:
    """Process due pending entries; return ``(outbox_id, outcome)`` tuples."""
    settings = settings or get_settings()
    publisher = publisher or PubSubPublisher(settings)
    now = now or datetime.now(UTC)

    outcomes: list[tuple[int, str]] = []
    with session_scope() as session:
        rows: list[OutboxEntry] = list(
            session.scalars(
                select(OutboxEntry)
                .where(OutboxEntry.status == "pending", OutboxEntry.next_attempt_at <= now)
                .order_by(OutboxEntry.id)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
        )
        for row in rows:
            outcome = await process_entry(row, adapters, publisher, settings, now)
            outcomes.append((row.id, outcome))
    return outcomes


def default_adapters() -> dict[str, MarketplaceAdapter]:
    """Build the production adapter registry."""
    from src.adapters.mercadolibre import MercadoLibreAdapter
    from src.adapters.paris import ParisAdapter

    paris: MarketplaceAdapter = ParisAdapter()
    ml: MarketplaceAdapter = MercadoLibreAdapter()
    return {paris.name: paris, ml.name: ml}
