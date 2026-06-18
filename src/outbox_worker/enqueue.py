"""Enqueue confirmed Odoo orders into the outbox (idempotent)."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.adapters.base import OrderDTO
from src.common.db import session_scope
from src.common.models import OutboxEntry


def enqueue_orders(orders: Iterable[OrderDTO], target_adapters: list[str]) -> int:
    """Insert one outbox row per (order, target). Returns rows actually added.

    Idempotent via ``uq_outbox_aggregate_target``: re-enqueuing the same Odoo
    order for the same adapter is a no-op.
    """
    inserted = 0
    with session_scope() as session:
        for order in orders:
            for target in target_adapters:
                stmt = (
                    pg_insert(OutboxEntry)
                    .values(
                        aggregate_type="order",
                        aggregate_id=str(order.odoo_order_id),
                        payload=order.model_dump(mode="json"),
                        target_adapter=target,
                        status="pending",
                    )
                    .on_conflict_do_nothing(constraint="uq_outbox_aggregate_target")
                    .returning(OutboxEntry.id)
                )
                if session.execute(stmt).first() is not None:
                    inserted += 1
    return inserted
