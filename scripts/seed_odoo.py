"""Seed Odoo with reproducible demo data via the XML-RPC API.

Creates 3 products, 2 customers and 1 sale order. Idempotent: every record is
matched by a stable business key (SKU / partner ref / client_order_ref) and
updated in place, so running it repeatedly converges to the same state.

Usage:
    uv run python scripts/seed_odoo.py
"""

from __future__ import annotations

import sys
import xmlrpc.client
from typing import Any, cast

from src.common.config import Settings, get_settings
from src.common.logging import configure_logging, get_logger

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


class OdooClient:
    """Thin idempotent XML-RPC wrapper around the Odoo external API."""

    def __init__(self, settings: Settings) -> None:
        self._db = settings.odoo_db
        self._password = settings.odoo_password
        common = xmlrpc.client.ServerProxy(f"{settings.odoo_url}/xmlrpc/2/common")
        uid = common.authenticate(self._db, settings.odoo_user, self._password, {})
        if not uid:
            raise RuntimeError("Odoo authentication failed — check ODOO_* settings")
        self._uid: int = cast(int, uid)
        self._models = xmlrpc.client.ServerProxy(f"{settings.odoo_url}/xmlrpc/2/object")

    def execute(self, model: str, method: str, *args: Any, **kwargs: Any) -> Any:
        return self._models.execute_kw(
            self._db, self._uid, self._password, model, method, list(args), kwargs
        )

    def upsert(self, model: str, key_field: str, values: dict[str, Any]) -> int:
        """Create or update a record matched by ``key_field``; return its id."""
        existing: list[int] = self.execute(
            model, "search", [(key_field, "=", values[key_field])], limit=1
        )
        if existing:
            record_id = existing[0]
            self.execute(model, "write", [record_id], values)
            return record_id
        return int(self.execute(model, "create", values))


def seed(client: OdooClient) -> dict[str, Any]:
    """Apply the seed and return a summary of created/updated ids."""
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
