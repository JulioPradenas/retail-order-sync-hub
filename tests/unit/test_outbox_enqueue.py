"""Unit tests for enqueue_orders — session + pg_insert mocked."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.adapters.base import OrderDTO, OrderItemDTO
from src.outbox_worker.enqueue import enqueue_orders

_ORDER = OrderDTO(
    odoo_order_id=1,
    buyer="Comex",
    items=[OrderItemDTO(sku="MUG-001", qty=2)],
    external_ref="odoo-1",
)


def _ctx(session: MagicMock) -> MagicMock:
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=session)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def test_insert_returns_row_increments_count() -> None:
    session = MagicMock()
    session.execute.return_value.first.return_value = (1,)  # row returned → inserted

    with patch("src.outbox_worker.enqueue.session_scope", return_value=_ctx(session)):
        count = enqueue_orders([_ORDER], ["paris", "mercadolibre"])

    assert count == 2  # one per adapter
    assert session.execute.call_count == 2


def test_conflict_returns_none_no_increment() -> None:
    session = MagicMock()
    session.execute.return_value.first.return_value = None  # conflict → no row

    with patch("src.outbox_worker.enqueue.session_scope", return_value=_ctx(session)):
        count = enqueue_orders([_ORDER], ["paris"])

    assert count == 0


def test_empty_orders_returns_zero() -> None:
    session = MagicMock()
    with patch("src.outbox_worker.enqueue.session_scope", return_value=_ctx(session)):
        count = enqueue_orders([], ["paris"])
    assert count == 0
    session.execute.assert_not_called()


def test_multiple_orders_multiple_adapters() -> None:
    order2 = OrderDTO(
        odoo_order_id=2,
        buyer="Buyer2",
        items=[OrderItemDTO(sku="MUG-002", qty=1)],
        external_ref="odoo-2",
    )
    session = MagicMock()
    session.execute.return_value.first.return_value = (1,)

    with patch("src.outbox_worker.enqueue.session_scope", return_value=_ctx(session)):
        count = enqueue_orders([_ORDER, order2], ["paris", "mercadolibre"])

    assert count == 4  # 2 orders x 2 adapters
