"""Normalize raw marketplace webhook payloads into a common shape."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class PoisonError(Exception):
    """Raised when an event cannot be normalized (sent to DLQ)."""


@dataclass(frozen=True)
class NormalizedOrder:
    marketplace: str
    marketplace_order_id: str
    odoo_order_id: int | None
    status: str


def _odoo_id_from_external_ref(ref: Any) -> int | None:
    if isinstance(ref, str) and ref.startswith("odoo-"):
        try:
            return int(ref.split("-", 1)[1])
        except ValueError:
            return None
    return None


def normalize_event(source: str, raw_body: dict[str, Any]) -> NormalizedOrder:
    """Map a source-specific payload to a ``NormalizedOrder`` or raise PoisonError."""
    try:
        if source == "paris":
            return NormalizedOrder(
                marketplace="paris",
                marketplace_order_id=str(raw_body["order_id"]),
                odoo_order_id=_odoo_id_from_external_ref(raw_body.get("external_ref")),
                status=str(raw_body["status"]),
            )
        if source == "mercadolibre":
            resource = str(raw_body.get("resource", ""))
            order_id = str(raw_body.get("order_id") or resource.rsplit("/", 1)[-1])
            if not order_id:
                raise KeyError("order_id")
            return NormalizedOrder(
                marketplace="mercadolibre",
                marketplace_order_id=order_id,
                odoo_order_id=_odoo_id_from_external_ref(raw_body.get("external_reference")),
                status=str(raw_body.get("status", "unknown")),
            )
        raise PoisonError(f"unknown source: {source}")
    except (KeyError, TypeError) as exc:
        raise PoisonError(f"cannot normalize {source} event: {exc}") from exc
