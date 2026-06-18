"""Read confirmed Odoo orders and map them to ``OrderDTO``."""

from __future__ import annotations

from typing import Any

from src.adapters.base import OrderDTO, OrderItemDTO
from src.common.odoo import OdooClient

CONFIRMED_STATES = ["sale", "done"]


def fetch_confirmed_orders(client: OdooClient) -> list[OrderDTO]:
    """Return confirmed sale orders as internal DTOs."""
    orders: list[dict[str, Any]] = client.search_read(
        "sale.order",
        [("state", "in", CONFIRMED_STATES)],
        ["id", "partner_id", "order_line"],
    )
    if not orders:
        return []

    line_ids = [lid for order in orders for lid in order["order_line"]]
    lines = client.search_read(
        "sale.order.line",
        [("id", "in", line_ids)],
        ["id", "product_id", "product_uom_qty"],
    )
    lines_by_id = {line["id"]: line for line in lines}

    product_ids = list({line["product_id"][0] for line in lines if line.get("product_id")})
    products = client.search_read(
        "product.product", [("id", "in", product_ids)], ["id", "default_code"]
    )
    sku_by_product = {p["id"]: (p.get("default_code") or f"PID-{p['id']}") for p in products}

    dtos: list[OrderDTO] = []
    for order in orders:
        items = [
            OrderItemDTO(
                sku=sku_by_product.get(line["product_id"][0], f"PID-{line['product_id'][0]}"),
                qty=int(line["product_uom_qty"]),
            )
            for lid in order["order_line"]
            if (line := lines_by_id.get(lid)) and line.get("product_id")
        ]
        if not items:
            continue
        partner = order.get("partner_id") or [0, "unknown"]
        dtos.append(
            OrderDTO(
                odoo_order_id=order["id"],
                buyer=str(partner[1]),
                items=items,
                external_ref=f"odoo-{order['id']}",
            )
        )
    return dtos
