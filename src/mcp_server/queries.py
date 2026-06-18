"""DB and BQ query helpers for MCP read tools."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from src.common.db import session_scope
from src.common.models import Order, OutboxEntry, WebhookLog


def get_order_by_id(order_id: str) -> dict[str, Any] | None:
    """
    Look up an order by internal_id, odoo_order_id, or marketplace_order_id.
    Returns a plain dict or None.
    """
    with session_scope() as session:
        # Try numeric internal_id first
        if order_id.isdigit():
            row = session.get(Order, int(order_id))
        else:
            row = session.scalar(
                select(Order).where(Order.marketplace_order_id == order_id).limit(1)
            )
        if row is None:
            return None
        return {
            "internal_id": row.internal_id,
            "odoo_order_id": row.odoo_order_id,
            "marketplace": row.marketplace,
            "marketplace_order_id": row.marketplace_order_id,
            "status": row.status,
            "last_sync_at": row.last_sync_at.isoformat() if row.last_sync_at else None,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
        }


def get_outbox_entries(aggregate_id: str) -> list[dict[str, Any]]:
    """Return all outbox entries for a given aggregate_id."""
    with session_scope() as session:
        rows = list(
            session.scalars(
                select(OutboxEntry)
                .where(OutboxEntry.aggregate_id == aggregate_id)
                .order_by(OutboxEntry.created_at)
            )
        )
        return [
            {
                "id": r.id,
                "target_adapter": r.target_adapter,
                "status": r.status,
                "attempts": r.attempts,
                "next_attempt_at": r.next_attempt_at.isoformat(),
                "error_log": r.error_log,
                "created_at": r.created_at.isoformat(),
                "updated_at": r.updated_at.isoformat(),
            }
            for r in rows
        ]


def get_webhook_events(
    event_id: str | None = None, source: str | None = None
) -> list[dict[str, Any]]:
    """Return webhook_log entries matching event_id or source."""
    with session_scope() as session:
        stmt = select(WebhookLog).order_by(WebhookLog.received_at.desc()).limit(20)
        if event_id:
            stmt = stmt.where(WebhookLog.event_id == event_id)
        if source:
            stmt = stmt.where(WebhookLog.source == source)
        rows = list(session.scalars(stmt))
        return [
            {
                "id": r.id,
                "event_id": r.event_id,
                "source": r.source,
                "received_at": r.received_at.isoformat(),
            }
            for r in rows
        ]


def count_dlq_entries() -> int:
    """Count outbox entries currently in dlq status."""
    with session_scope() as session:
        from sqlalchemy import func

        result = session.scalar(
            select(func.count()).select_from(OutboxEntry).where(OutboxEntry.status == "dlq")
        )
        return int(result or 0)


def find_failed_orders(
    since: datetime,
    marketplace: str | None = None,
) -> list[dict[str, Any]]:
    """Orders without a successful sync after ``since``."""
    with session_scope() as session:
        stmt = (
            select(Order)
            .where(Order.created_at >= since, Order.last_sync_at.is_(None))
            .order_by(Order.created_at.desc())
            .limit(100)
        )
        if marketplace:
            stmt = stmt.where(Order.marketplace == marketplace)
        rows = list(session.scalars(stmt))
        return [
            {
                "internal_id": r.internal_id,
                "marketplace": r.marketplace,
                "marketplace_order_id": r.marketplace_order_id,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]


def get_bq_sla_metrics(marketplace: str, window: str) -> list[dict[str, Any]]:
    """Query gold.sla_by_marketplace filtered by marketplace."""
    from google.cloud import bigquery

    from src.common.config import get_settings

    settings = get_settings()
    client = bigquery.Client(project=settings.bq_project_id)
    query = f"""
        SELECT marketplace, total_synced, avg_sync_seconds, p50_sync_seconds, p95_sync_seconds
        FROM `{settings.bq_project_id}.gold.sla_by_marketplace`
        WHERE marketplace = @marketplace
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("marketplace", "STRING", marketplace)]
    )
    rows = list(client.query(query, job_config=job_config).result())
    return [dict(r.items()) for r in rows]
