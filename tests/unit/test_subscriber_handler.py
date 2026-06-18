import json
from typing import Any

from src.common.config import Settings
from src.subscriber.handler import handle_envelope

SETTINGS = Settings()


class FakeSession:
    def __init__(self, raw: Any) -> None:
        self._raw = raw

    def scalar(self, statement: Any) -> Any:
        return self._raw

    def execute(self, statement: Any) -> Any:  # pragma: no cover - poison paths never upsert
        raise AssertionError("upsert should not be reached on poison events")


class FakePublisher:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any], dict[str, str]]] = []

    def publish(self, topic: str, data: bytes, **attributes: str) -> str:
        self.published.append((topic, json.loads(data), attributes))
        return "mid"


def test_missing_bronze_row_is_poisoned_to_dlq() -> None:
    pub = FakePublisher()
    outcome = handle_envelope(
        {"event_id": "e1", "source": "paris"},
        session=FakeSession(None),
        settings=SETTINGS,
        publisher=pub,
    )
    assert outcome == "poison"
    topic, body, attrs = pub.published[0]
    assert topic == SETTINGS.pubsub_topic_dlq
    assert attrs["reason"] == "poison"
    assert body["reason"] == "bronze row not found"


def test_unnormalizable_payload_is_poisoned_to_dlq() -> None:
    pub = FakePublisher()
    outcome = handle_envelope(
        {"event_id": "e2", "source": "paris"},
        session=FakeSession({"status": "delivered"}),  # bronze present but no order_id
        settings=SETTINGS,
        publisher=pub,
    )
    assert outcome == "poison"
    assert "cannot normalize" in pub.published[0][1]["reason"]


class _UpsertSession:
    """Session that returns a raw body and a successful upsert execute."""

    def __init__(self, raw: Any) -> None:
        self._raw = raw

    def scalar(self, statement: Any) -> Any:
        return self._raw

    def execute(self, statement: Any) -> Any:
        m = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()
        m.scalar_one.return_value = 1
        return m


_VALID_RAW = {
    "event_id": "e3",
    "source": "paris",
    "order_id": "PM-42",
    "external_ref": "odoo-1",
    "status": "delivered",
}


def test_happy_path_returns_processed() -> None:
    outcome = handle_envelope(
        {"event_id": "e3", "source": "paris"},
        session=_UpsertSession(_VALID_RAW),
        settings=SETTINGS,
        publisher=FakePublisher(),
    )
    assert outcome == "processed"


def test_reconcile_called_when_odoo_provided_and_delivered() -> None:
    from unittest.mock import MagicMock, patch

    odoo = MagicMock()
    with patch("src.subscriber.handler.reconcile_to_odoo") as mock_reconcile:
        outcome = handle_envelope(
            {"event_id": "e4", "source": "paris"},
            session=_UpsertSession({**_VALID_RAW, "event_id": "e4"}),
            settings=SETTINGS,
            publisher=FakePublisher(),
            odoo=odoo,
        )
    assert outcome == "processed"
    mock_reconcile.assert_called_once()
