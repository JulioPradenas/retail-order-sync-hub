"""Upsert normalized orders into the silver ``orders`` table."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.common.models import Order
from src.subscriber.normalize import NormalizedOrder


def upsert_order(session: Session, order: NormalizedOrder) -> int:
    """Insert or update the silver row keyed by (marketplace, marketplace_order_id).

    Returns the ``internal_id`` of the row.
    """
    stmt = (
        pg_insert(Order)
        .values(
            marketplace=order.marketplace,
            marketplace_order_id=order.marketplace_order_id,
            odoo_order_id=order.odoo_order_id,
            status=order.status,
            last_sync_at=func.now(),
        )
        .on_conflict_do_update(
            constraint="uq_orders_marketplace_id",
            set_={
                "status": order.status,
                "odoo_order_id": order.odoo_order_id,
                "last_sync_at": func.now(),
            },
        )
        .returning(Order.internal_id)
    )
    internal_id: int = session.execute(stmt).scalar_one()
    return internal_id
