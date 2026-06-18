"""Reconcile silver order state back into Odoo (safety net for drift)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.common.models import Order
from src.common.odoo import OdooClient
from src.common.otel import get_meter

_meter = get_meter("reconciler")
_drift_counter = _meter.create_counter(
    "reconciliation_drift_detected_total",
    description="Orders whose Odoo state was advanced to match the marketplace",
)


def _delivered_marker(status: str) -> str:
    return f"[sync] marketplace status: {status}"


def reconcile_to_odoo(odoo: OdooClient, odoo_order_id: int, status: str) -> bool:
    """Write the marketplace status into Odoo idempotently. Returns True if changed."""
    desired = _delivered_marker(status)
    rows = odoo.search_read("sale.order", [("id", "=", odoo_order_id)], ["note"])
    if not rows:
        return False
    if rows[0].get("note") == desired:
        return False
    odoo.execute("sale.order", "write", [odoo_order_id], {"note": desired})
    return True


def reconcile_once(odoo: OdooClient, session: Session) -> int:
    """Compare silver delivered orders against Odoo and fix drift. Returns drift count."""
    rows = session.execute(
        select(Order.odoo_order_id, Order.status).where(
            Order.status == "delivered", Order.odoo_order_id.is_not(None)
        )
    ).all()
    drift = 0
    for odoo_order_id, status in rows:
        if odoo_order_id is not None and reconcile_to_odoo(odoo, odoo_order_id, status):
            drift += 1
    if drift:
        _drift_counter.add(drift)
    return drift
