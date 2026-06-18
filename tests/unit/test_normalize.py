import pytest
from src.subscriber.normalize import NormalizedOrder, PoisonError, normalize_event


def test_normalize_paris_event() -> None:
    raw = {"order_id": "p123", "external_ref": "odoo-42", "status": "delivered"}
    assert normalize_event("paris", raw) == NormalizedOrder(
        marketplace="paris", marketplace_order_id="p123", odoo_order_id=42, status="delivered"
    )


def test_normalize_paris_without_external_ref_has_none_odoo_id() -> None:
    raw = {"order_id": "p1", "status": "created"}
    assert normalize_event("paris", raw).odoo_order_id is None


def test_normalize_mercadolibre_resource_path() -> None:
    raw = {"resource": "/orders/99", "status": "paid"}
    result = normalize_event("mercadolibre", raw)
    assert result.marketplace_order_id == "99"
    assert result.status == "paid"


def test_missing_required_field_is_poison() -> None:
    with pytest.raises(PoisonError):
        normalize_event("paris", {"status": "delivered"})  # no order_id


def test_unknown_source_is_poison() -> None:
    with pytest.raises(PoisonError):
        normalize_event("amazon", {"order_id": "x"})
