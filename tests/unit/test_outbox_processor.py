from datetime import UTC, datetime
from typing import Any

from hypothesis import given
from hypothesis import strategies as st
from src.adapters.base import AdapterError, OrderDTO, OrderItemDTO, PushResult, order_from_payload
from src.common.config import Settings
from src.common.models import OutboxEntry
from src.outbox_worker.processor import process_entry

SETTINGS = Settings(outbox_max_attempts=5)
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
        raise AdapterError("boom")


class FakePublisher:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, str]]] = []

    def publish(self, topic: str, data: bytes, **attributes: str) -> str:
        self.published.append((topic, attributes))
        return "mid"


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


async def test_success_marks_done() -> None:
    row, pub = _row(), FakePublisher()
    outcome = await process_entry(row, {"paris": OkAdapter()}, pub, SETTINGS, NOW)
    assert outcome == "done"
    assert row.status == "done"
    assert pub.published == []


async def test_failure_schedules_retry_with_backoff() -> None:
    row, pub = _row(attempts=0), FakePublisher()
    outcome = await process_entry(row, {"paris": FailAdapter()}, pub, SETTINGS, NOW)
    assert outcome == "retry"
    assert row.status == "pending"
    assert row.attempts == 1
    assert row.next_attempt_at > NOW
    assert pub.published == []


async def test_dlq_when_max_attempts_exceeded() -> None:
    row, pub = _row(attempts=4), FakePublisher()  # next failure hits max=5
    outcome = await process_entry(row, {"paris": FailAdapter()}, pub, SETTINGS, NOW)
    assert outcome == "dlq"
    assert row.status == "dlq"
    assert row.attempts == 5
    assert pub.published[0][0] == "marketplace.sync.dlq"


async def test_unknown_adapter_is_treated_as_failure() -> None:
    row, pub = _row(attempts=0), FakePublisher()
    outcome = await process_entry(row, {}, pub, SETTINGS, NOW)
    assert outcome == "retry"
    assert row.attempts == 1


@given(
    odoo_id=st.integers(min_value=1, max_value=10**9),
    sku=st.text(min_size=1, max_size=20),
    qty=st.integers(min_value=1, max_value=1000),
)
def test_order_dto_payload_roundtrip(odoo_id: int, sku: str, qty: int) -> None:
    dto = OrderDTO(
        odoo_order_id=odoo_id,
        buyer="buyer",
        items=[OrderItemDTO(sku=sku, qty=qty)],
        external_ref=f"odoo-{odoo_id}",
    )
    payload: dict[str, Any] = dto.model_dump(mode="json")
    assert order_from_payload(payload) == dto
