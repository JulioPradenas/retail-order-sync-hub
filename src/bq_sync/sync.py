"""Watermark-based incremental sync: Postgres → BigQuery bronze."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text

from src.bq_sync.client import BQClient
from src.bq_sync.schema import RAW_ORDERS, RAW_WEBHOOKS
from src.common.config import Settings, get_settings
from src.common.db import session_scope
from src.common.logging import get_logger
from src.common.models import Order, WebhookLog

log = get_logger()


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def sync_webhooks(
    bq: BQClient,
    settings: Settings,
    since: str | None = None,
    batch_size: int | None = None,
) -> int:
    """Sync new rows from webhook_log → bronze.raw_webhooks. Returns row count synced."""
    bs = batch_size or settings.bq_batch_size
    watermark = since or bq.max_timestamp(settings.bq_bronze_dataset, "raw_webhooks", "received_at")

    bq.ensure_table(settings.bq_bronze_dataset, "raw_webhooks", RAW_WEBHOOKS)

    ingested_at = _now_iso()
    total = 0

    with session_scope() as session:
        stmt = select(WebhookLog).order_by(WebhookLog.received_at, WebhookLog.id)
        if watermark:
            stmt = stmt.where(text("received_at > :wm").bindparams(wm=watermark))
        rows_iter = session.scalars(stmt)

        batch: list[dict[str, Any]] = []
        for row in rows_iter:
            batch.append(
                {
                    "id": row.id,
                    "event_id": row.event_id,
                    "source": row.source,
                    "received_at": row.received_at.isoformat(),
                    "raw_body": json.dumps(row.raw_body),
                    "headers": json.dumps(row.headers),
                    "ingested_at": ingested_at,
                }
            )
            if len(batch) >= bs:
                total += bq.insert_rows(settings.bq_bronze_dataset, "raw_webhooks", batch)
                batch = []
        if batch:
            total += bq.insert_rows(settings.bq_bronze_dataset, "raw_webhooks", batch)

    log.info("bq_sync.webhooks", synced=total, watermark=watermark)
    return total


def sync_orders(
    bq: BQClient,
    settings: Settings,
    since: str | None = None,
    batch_size: int | None = None,
) -> int:
    """Sync new/updated rows from orders → bronze.raw_orders. Returns row count synced."""
    bs = batch_size or settings.bq_batch_size
    watermark = since or bq.max_timestamp(settings.bq_bronze_dataset, "raw_orders", "updated_at")

    bq.ensure_table(settings.bq_bronze_dataset, "raw_orders", RAW_ORDERS)

    ingested_at = _now_iso()
    total = 0

    with session_scope() as session:
        stmt = select(Order).order_by(Order.updated_at, Order.internal_id)
        if watermark:
            stmt = stmt.where(text("updated_at > :wm").bindparams(wm=watermark))
        rows_iter = session.scalars(stmt)

        batch: list[dict[str, Any]] = []
        for row in rows_iter:
            batch.append(
                {
                    "internal_id": row.internal_id,
                    "odoo_order_id": row.odoo_order_id,
                    "marketplace": row.marketplace,
                    "marketplace_order_id": row.marketplace_order_id,
                    "status": row.status,
                    "last_sync_at": _iso(row.last_sync_at),
                    "created_at": row.created_at.isoformat(),
                    "updated_at": row.updated_at.isoformat(),
                    "ingested_at": ingested_at,
                }
            )
            if len(batch) >= bs:
                total += bq.insert_rows(settings.bq_bronze_dataset, "raw_orders", batch)
                batch = []
        if batch:
            total += bq.insert_rows(settings.bq_bronze_dataset, "raw_orders", batch)

    log.info("bq_sync.orders", synced=total, watermark=watermark)
    return total


def run_sync(settings: Settings | None = None) -> dict[str, int]:
    settings = settings or get_settings()
    bq = BQClient(settings)
    webhooks = sync_webhooks(bq, settings)
    orders = sync_orders(bq, settings)
    return {"webhooks": webhooks, "orders": orders}
