"""MCP write tools — state-mutating operations with IAM + audit log (Phase 9).

Write tools:
  - replay_dlq_message  — reset a single DLQ outbox entry back to pending
  - retry_failed_sync   — re-enqueue an order for all adapters
  - drain_dlq           — bulk reset DLQ entries (dry_run safe by default)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select

from src.common.db import session_scope
from src.common.models import Order, OutboxEntry
from src.mcp_server.audit import audit
from src.mcp_server.auth import require_scope


@audit("dlq.replay")
def _replay_dlq_message(outbox_id: str, api_token: str = "") -> str:
    """
    Reset a DLQ outbox entry back to pending so the outbox worker retries it.

    Args:
        outbox_id: The outbox entry ID (integer, from trace_order DLQ entries).
        api_token: Token with scope dlq.replay.
    """
    require_scope(api_token, "dlq.replay")

    try:
        oid = int(outbox_id)
    except ValueError:
        return f"Invalid outbox_id '{outbox_id}' — must be an integer."

    with session_scope() as session:
        row = session.get(OutboxEntry, oid)
        if row is None:
            return f"Outbox entry {oid} not found."
        if row.status != "dlq":
            return f"Outbox entry {oid} is in status '{row.status}', not 'dlq'. Nothing to replay."

        row.status = "pending"
        row.attempts = 0
        row.next_attempt_at = datetime.now(UTC)
        row.error_log = None

    return json.dumps(
        {
            "replayed": True,
            "outbox_id": oid,
            "message": f"Entry {oid} reset to pending — will be picked up on next worker cycle.",
        }
    )


@audit("outbox.retry")
def _retry_failed_sync(order_id: str, api_token: str = "") -> str:
    """
    Force re-enqueue of an order into the outbox for all active adapters.
    Creates new outbox entries if none exist, or resets existing DLQ entries.

    Args:
        order_id: Internal order ID or marketplace_order_id.
        api_token: Token with scope outbox.retry.
    """
    require_scope(api_token, "outbox.retry")

    with session_scope() as session:
        if order_id.isdigit():
            order = session.get(Order, int(order_id))
        else:
            order = session.scalar(
                select(Order).where(Order.marketplace_order_id == order_id).limit(1)
            )
        if order is None:
            return f"Order '{order_id}' not found."

        aggregate_id = str(order.internal_id)
        existing = list(
            session.scalars(select(OutboxEntry).where(OutboxEntry.aggregate_id == aggregate_id))
        )
        now = datetime.now(UTC)
        reset_count = 0

        for entry in existing:
            if entry.status in ("dlq", "pending"):
                entry.status = "pending"
                entry.attempts = 0
                entry.next_attempt_at = now
                entry.error_log = None
                reset_count += 1

    return json.dumps(
        {
            "retried": True,
            "order_id": order_id,
            "internal_id": order.internal_id,
            "entries_reset": reset_count,
            "message": f"Order {order.internal_id} re-queued for sync.",
        }
    )


@audit("dlq.admin")
def _drain_dlq(dry_run: bool = True, api_token: str = "") -> str:
    """
    List (dry_run=True) or bulk-reset (dry_run=False) all DLQ outbox entries.

    Args:
        dry_run: If True (default), returns the list without modifying anything.
        api_token: Token with scope dlq.admin.
    """
    require_scope(api_token, "dlq.admin")

    with session_scope() as session:
        rows = list(
            session.scalars(
                select(OutboxEntry).where(OutboxEntry.status == "dlq").order_by(OutboxEntry.id)
            )
        )

        entries = [
            {
                "outbox_id": r.id,
                "aggregate_id": r.aggregate_id,
                "target_adapter": r.target_adapter,
                "attempts": r.attempts,
                "error_log": r.error_log,
            }
            for r in rows
        ]

        if not dry_run:
            now = datetime.now(UTC)
            for row in rows:
                row.status = "pending"
                row.attempts = 0
                row.next_attempt_at = now
                row.error_log = None

    return json.dumps(
        {
            "dry_run": dry_run,
            "dlq_count": len(entries),
            "entries": entries,
            "message": (f"{'Would reset' if dry_run else 'Reset'} {len(entries)} DLQ entries."),
        },
        indent=2,
    )
