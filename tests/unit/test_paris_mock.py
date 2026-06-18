from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from src.common.config import Settings
from src.paris_mock.app import create_app

HEADERS = {"X-API-Key": "k"}


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(paris_api_key="k", paris_api_secret="s")
    app = create_app(settings=settings, db_path=str(tmp_path / "paris.db"))
    with TestClient(app) as test_client:
        yield test_client


def test_health_needs_no_auth(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_missing_api_key_returns_401(client: TestClient) -> None:
    resp = client.post("/orders", json={"buyer": "x", "items": [{"sku": "A", "qty": 1}]})
    assert resp.status_code == 401


def test_create_and_get_order(client: TestClient) -> None:
    created = client.post(
        "/orders",
        headers=HEADERS,
        json={"buyer": "Comex", "items": [{"sku": "ROSH-TSHIRT-001", "qty": 2}]},
    )
    assert created.status_code == 201
    order_id = created.json()["id"]

    fetched = client.get(f"/orders/{order_id}", headers=HEADERS)
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "created"
    assert fetched.json()["items"][0]["sku"] == "ROSH-TSHIRT-001"


def test_create_is_idempotent_by_external_ref(client: TestClient) -> None:
    payload = {
        "buyer": "Comex",
        "items": [{"sku": "A", "qty": 1}],
        "external_ref": "EXT-1",
    }
    first = client.post("/orders", headers=HEADERS, json=payload).json()
    second = client.post("/orders", headers=HEADERS, json=payload).json()
    assert first["id"] == second["id"]


def test_get_unknown_order_404(client: TestClient) -> None:
    assert client.get("/orders/does-not-exist", headers=HEADERS).status_code == 404


def test_emit_webhook_updates_status(client: TestClient) -> None:
    order_id = client.post(
        "/orders", headers=HEADERS, json={"buyer": "Comex", "items": [{"sku": "A", "qty": 1}]}
    ).json()["id"]

    resp = client.post(
        f"/admin/orders/{order_id}/emit-webhook", headers=HEADERS, json={"status": "delivered"}
    )
    assert resp.status_code == 200
    assert resp.json()["event"]["status"] == "delivered"
    assert resp.json()["deliveries"] == []  # no webhooks registered

    assert client.get(f"/orders/{order_id}", headers=HEADERS).json()["status"] == "delivered"
