"""Chaos / resilience tests for the outbox processor."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from src.adapters.base import AdapterError, OrderDTO, PushResult
from src.common.config import Settings
from src.common.models import OutboxEntry
from src.outbox_worker.processor import default_adapters, process_entry, process_pending

SETTINGS = Settings(outbox_max_attempts=3)
NOW = datetime.now(UTC)
PAYLOAD = {
    "odoo_order_id": 1,
    "buyer": "Comex",
    "items": [{"sku": "A", "qty": 1}],
    "external_ref": "odoo-1",
}


class OkAdapter:
    name = "paris"

    async def push_order(self, order: OrderDTO) -> PushResult:
        return PushResult(marketplace_order_id="m1", status="created")

    async def update_stock(self, sku: str, qty: int) -> None: ...

    async def get_order_status(self, marketplace_order_id: str) -> str:
        return "created"


class FailAdapter(OkAdapter):
    async def push_order(self, order: OrderDTO) -> PushResult:
        raise AdapterError("network timeout")


class FakePublisher:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, str]]] = []

    def publish(self, topic: str, data: bytes, **attributes: str) -> str:
        self.published.append((topic, attributes))
        return "mid"


class RaisingPublisher:
    def publish(self, topic: str, data: bytes, **attributes: str) -> str:
        raise RuntimeError("pubsub unavailable")


def _row(attempts: int = 0) -> OutboxEntry:
    return OutboxEntry(
        id=1,
        aggregate_type="order",
        aggregate_id="1",
        payload=PAYLOAD,
        target_adapter="paris",
        status="pending",
        attempts=attempts,
        next_attempt_at=NOW,
    )


async def test_dlq_then_publisher_raises_propagates() -> None:
    """Publisher failure during DLQ publishing propagates to caller."""
    row = _row(attempts=2)  # next failure hits max=3
    with pytest.raises(RuntimeError, match="pubsub unavailable"):
        await process_entry(row, {"paris": FailAdapter()}, RaisingPublisher(), SETTINGS, NOW)


async def test_invalid_payload_treated_as_retry() -> None:
    """Malformed payload in outbox → model_validate fails → retry."""
    row = _row()
    row.payload = {"bad": "data"}  # missing required fields
    outcome = await process_entry(row, {"paris": OkAdapter()}, FakePublisher(), SETTINGS, NOW)
    assert outcome == "retry"
    assert row.attempts == 1


async def test_second_failure_still_retries_below_max() -> None:
    row = _row(attempts=1)  # attempts=2 after failure, max=3 → still retry
    outcome = await process_entry(row, {"paris": FailAdapter()}, FakePublisher(), SETTINGS, NOW)
    assert outcome == "retry"
    assert row.attempts == 2
    assert row.status == "pending"


async def test_process_pending_empty_session() -> None:
    """process_pending with no due rows returns empty list."""
    session = MagicMock()
    session.scalars.return_value = []
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=session)
    ctx.__exit__ = MagicMock(return_value=False)

    with patch("src.outbox_worker.processor.session_scope", return_value=ctx):
        outcomes = await process_pending({}, publisher=FakePublisher(), settings=SETTINGS, now=NOW)
    assert outcomes == []


async def test_process_pending_processes_rows() -> None:
    row = _row()
    session = MagicMock()
    session.scalars.return_value = [row]
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=session)
    ctx.__exit__ = MagicMock(return_value=False)

    with patch("src.outbox_worker.processor.session_scope", return_value=ctx):
        outcomes = await process_pending(
            {"paris": OkAdapter()}, publisher=FakePublisher(), settings=SETTINGS, now=NOW
        )

    assert len(outcomes) == 1
    assert outcomes[0] == (1, "done")


def test_default_adapters_returns_both_adapters() -> None:
    mock_paris = MagicMock()
    mock_paris.name = "paris"
    mock_ml = MagicMock()
    mock_ml.name = "mercadolibre"

    with (
        patch("src.adapters.paris.ParisAdapter", return_value=mock_paris),
        patch("src.adapters.mercadolibre.MercadoLibreAdapter", return_value=mock_ml),
    ):
        result = default_adapters()

    assert "paris" in result
    assert "mercadolibre" in result
