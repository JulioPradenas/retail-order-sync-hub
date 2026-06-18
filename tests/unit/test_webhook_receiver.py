import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import settings as hyp_settings
from hypothesis import strategies as st
from src.common.config import Settings
from src.common.signing import SIGNATURE_HEADER, sign_payload
from src.webhook_receiver.app import create_app
from src.webhook_receiver.store import RecordResult

PARIS_SECRET = "paris-secret"
ML_SECRET = "ml-secret"


class FakeStore:
    def __init__(self) -> None:
        self.dedup: set[tuple[str, str]] = set()
        self.bronze: list[tuple[str, str, dict[str, Any]]] = []

    def record(
        self, source: str, event_id: str, raw_body: dict[str, Any], headers: dict[str, str]
    ) -> RecordResult:
        key = (source, event_id)
        if key in self.dedup:
            return RecordResult(is_new=False, raw_ref=f"webhook_log:{source}:{event_id}")
        self.dedup.add(key)
        self.bronze.append((source, event_id, raw_body))
        return RecordResult(is_new=True, raw_ref=f"webhook_log:{len(self.bronze)}")


class FakePublisher:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any], dict[str, str]]] = []

    def publish(self, topic: str, data: bytes, **attributes: str) -> str:
        self.published.append((topic, json.loads(data), attributes))
        return f"mid-{len(self.published)}"


def _settings() -> Settings:
    return Settings(paris_api_secret=PARIS_SECRET, ml_webhook_secret=ML_SECRET)


@pytest.fixture
def ctx() -> Iterator[tuple[TestClient, FakeStore, FakePublisher]]:
    store, publisher = FakeStore(), FakePublisher()
    app = create_app(settings=_settings(), store=store, publisher=publisher)
    with TestClient(app) as client:
        yield client, store, publisher


def _post(client: TestClient, path: str, secret: str, header: str, body: dict[str, Any]):  # type: ignore[no-untyped-def]
    raw = json.dumps(body).encode()
    return client.post(
        path,
        content=raw,
        headers={header: sign_payload(secret, raw), "Content-Type": "application/json"},
    )


def test_paris_idempotent_over_five_deliveries(
    ctx: tuple[TestClient, FakeStore, FakePublisher],
) -> None:
    client, store, publisher = ctx
    body = {"event_id": "evt-1", "order_id": "o1", "status": "delivered"}

    responses = [
        _post(client, "/webhooks/paris", PARIS_SECRET, SIGNATURE_HEADER, body) for _ in range(5)
    ]

    assert all(r.status_code == 200 for r in responses)
    assert responses[0].json()["duplicate"] is False
    assert all(r.json()["duplicate"] is True for r in responses[1:])
    assert len(store.bronze) == 1  # only one bronze row
    assert len(publisher.published) == 1  # published only once


def test_invalid_signature_returns_401(
    ctx: tuple[TestClient, FakeStore, FakePublisher],
) -> None:
    client, store, publisher = ctx
    raw = json.dumps({"event_id": "evt-x"}).encode()
    resp = client.post("/webhooks/paris", content=raw, headers={SIGNATURE_HEADER: "deadbeef"})
    assert resp.status_code == 401
    assert store.bronze == []
    assert publisher.published == []


def test_new_event_publishes_envelope(
    ctx: tuple[TestClient, FakeStore, FakePublisher],
) -> None:
    client, _store, publisher = ctx
    _post(client, "/webhooks/paris", PARIS_SECRET, SIGNATURE_HEADER, {"event_id": "evt-7"})

    topic, envelope, attrs = publisher.published[0]
    assert topic == "marketplace.events"
    assert envelope["event_id"] == "evt-7"
    assert envelope["source"] == "paris"
    assert envelope["raw_ref"].startswith("webhook_log:")
    assert "received_at" in envelope
    assert attrs == {"source": "paris", "event_id": "evt-7"}


def test_mercadolibre_endpoint_accepts_signed_event(
    ctx: tuple[TestClient, FakeStore, FakePublisher],
) -> None:
    client, store, _ = ctx
    resp = _post(
        client,
        "/webhooks/mercadolibre",
        ML_SECRET,
        "X-Signature",
        {"_id": "ml-1", "topic": "orders"},
    )
    assert resp.status_code == 200
    assert store.bronze[0][1] == "ml-1"


_PROP_STORE = FakeStore()
_PROP_APP = create_app(settings=_settings(), store=_PROP_STORE, publisher=FakePublisher())
_PROP_CLIENT = TestClient(_PROP_APP)


@hyp_settings(max_examples=60)
@given(
    event_id=st.text(min_size=1, max_size=40),
    extra=st.dictionaries(st.text(max_size=10), st.integers(), max_size=5),
)
def test_well_formed_payloads_never_crash(event_id: str, extra: dict[str, int]) -> None:
    body = {"event_id": event_id, **extra}
    resp = _post(_PROP_CLIENT, "/webhooks/paris", PARIS_SECRET, SIGNATURE_HEADER, body)
    assert resp.status_code == 200
