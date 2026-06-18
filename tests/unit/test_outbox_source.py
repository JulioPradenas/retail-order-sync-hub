from typing import Any, cast

from src.common.odoo import OdooClient
from src.outbox_worker.source import fetch_confirmed_orders


class FakeOdoo:
    def search_read(
        self, model: str, domain: list[Any], fields: list[str], **kwargs: Any
    ) -> list[dict[str, Any]]:
        if model == "sale.order":
            return [{"id": 10, "partner_id": [5, "Comex"], "order_line": [100, 101]}]
        if model == "sale.order.line":
            return [
                {"id": 100, "product_id": [7, "Tee"], "product_uom_qty": 2.0},
                {"id": 101, "product_id": [8, "Mug"], "product_uom_qty": 1.0},
            ]
        if model == "product.product":
            return [{"id": 7, "default_code": "SKU-7"}, {"id": 8, "default_code": False}]
        return []


def test_fetch_maps_orders_to_dtos() -> None:
    dtos = fetch_confirmed_orders(cast(OdooClient, FakeOdoo()))
    assert len(dtos) == 1
    order = dtos[0]
    assert order.odoo_order_id == 10
    assert order.buyer == "Comex"
    assert order.external_ref == "odoo-10"
    skus = {item.sku for item in order.items}
    assert skus == {"SKU-7", "PID-8"}  # missing default_code falls back to PID-<id>
