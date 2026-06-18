"""Unit tests for silver layer upsert."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.subscriber.normalize import NormalizedOrder
from src.subscriber.silver import upsert_order


def _normalized(**kwargs: object) -> NormalizedOrder:
    return NormalizedOrder(
        marketplace=str(kwargs.get("marketplace", "paris")),
        marketplace_order_id=str(kwargs.get("marketplace_order_id", "PM-1")),
        odoo_order_id=kwargs.get("odoo_order_id"),  # type: ignore[arg-type]
        status=str(kwargs.get("status", "delivered")),
    )


def test_upsert_returns_internal_id() -> None:
    session = MagicMock()
    session.execute.return_value.scalar_one.return_value = 42
    result = upsert_order(session, _normalized())
    assert result == 42
    session.execute.assert_called_once()


def test_upsert_with_odoo_order_id() -> None:
    session = MagicMock()
    session.execute.return_value.scalar_one.return_value = 7
    result = upsert_order(session, _normalized(odoo_order_id=99, status="confirmed"))
    assert result == 7


def test_upsert_different_marketplace() -> None:
    session = MagicMock()
    session.execute.return_value.scalar_one.return_value = 5
    result = upsert_order(
        session, _normalized(marketplace="mercadolibre", marketplace_order_id="ML-5")
    )
    assert result == 5
