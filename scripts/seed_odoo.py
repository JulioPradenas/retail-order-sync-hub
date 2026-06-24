"""Seed Odoo with reproducible demo data via the XML-RPC API.

Creates 3 products, 2 customers and 1 sale order. Idempotent: every record is
matched by a stable business key (SKU / partner ref / client_order_ref) and
updated in place, so running it repeatedly converges to the same state.

Usage:
    uv run python scripts/seed_odoo.py
"""

from __future__ import annotations

import sys
from typing import Any

from src.common.config import get_settings
from src.common.logging import configure_logging, get_logger
from src.common.odoo import OdooClient

log = get_logger()

# Stable business keys so the seed is idempotent.
PRODUCTS: list[dict[str, Any]] = [
    {"default_code": "ROSH-TSHIRT-001", "name": "Camiseta Retail Demo", "list_price": 12990.0},
    {"default_code": "ROSH-MUG-002", "name": "Taza Retail Demo", "list_price": 5990.0},
    {"default_code": "ROSH-CAP-003", "name": "Gorro Retail Demo", "list_price": 8990.0},
]
PARTNERS: list[dict[str, Any]] = [
    {"ref": "ROSH-CUST-001", "name": "Comex Test Buyer", "email": "comex.buyer@example.cl"},
    {"ref": "ROSH-CUST-002", "name": "Retail Demo Client", "email": "demo.client@example.cl"},
]
ORDER_REF = "ROSH-ORDER-0001"

# Odoo boots with `--init base,sale_management`, which leaves the admin user
# without the Sales group, so creating a sale.order over XML-RPC is denied.
# Grant it here (idempotent: re-adding an existing group is a no-op) so that a
# fresh `make up && make seed` always works without manual steps.
SALES_GROUP_XMLID = ("sales_team", "group_sale_manager")


def ensure_sales_access(client: OdooClient) -> None:
    """Make sure the seed user can read/write sale orders."""
    _, group_id = client.execute(
        "ir.model.data", "check_object_reference", *SALES_GROUP_XMLID
    )
    client.execute("res.users", "write", [client.uid], {"groups_id": [(4, group_id)]})


def seed(client: OdooClient) -> dict[str, Any]:
    """Apply the seed and return a summary of created/updated ids."""
    ensure_sales_access(client)
    product_ids = {
        p["default_code"]: client.upsert("product.product", "default_code", p) for p in PRODUCTS
    }
    partner_ids = {p["ref"]: client.upsert("res.partner", "ref", p) for p in PARTNERS}

    existing_order: list[int] = client.execute(
        "sale.order", "search", [("client_order_ref", "=", ORDER_REF)], limit=1
    )
    if existing_order:
        order_id = existing_order[0]
    else:
        order_lines = [
            (0, 0, {"product_id": pid, "product_uom_qty": qty})
            for pid, qty in zip(product_ids.values(), (2, 1, 3), strict=True)
        ]
        order_id = int(
            client.execute(
                "sale.order",
                "create",
                {
                    "partner_id": next(iter(partner_ids.values())),
                    "client_order_ref": ORDER_REF,
                    "order_line": order_lines,
                },
            )
        )

    return {
        "products": product_ids,
        "partners": partner_ids,
        "order_id": order_id,
        "order_ref": ORDER_REF,
    }


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    log.info("seed_odoo.start", odoo_url=settings.odoo_url, db=settings.odoo_db)
    try:
        client = OdooClient(settings)
        summary = seed(client)
    except Exception as exc:
        log.error("seed_odoo.failed", error=str(exc))
        return 1
    log.info("seed_odoo.done", **summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
