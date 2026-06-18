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
