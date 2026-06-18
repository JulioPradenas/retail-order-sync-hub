"""Integration checks against the running docker stack.

Skipped unless ``ROSH_INTEGRATION=1`` (see tests/conftest.py). Run with:

    make up && ROSH_INTEGRATION=1 uv run pytest -m integration
"""

from __future__ import annotations

import json
import os
import urllib.request
import uuid

import pytest
from sqlalchemy import inspect, text
from src.common.db import make_engine
from src.common.signing import SIGNATURE_HEADER, sign_payload

pytestmark = pytest.mark.integration

PARIS_API_KEY = os.getenv("PARIS_API_KEY", "change-me")
PARIS_API_SECRET = os.getenv("PARIS_API_SECRET", "change-me")

EXPECTED_TABLES = {
    "webhook_log",
    "webhook_dedup",
    "orders",
    "outbox",
    "oauth_tokens",
    "mcp_audit_log",
}


def test_odoo_health_endpoint_responds() -> None:
    with urllib.request.urlopen("http://localhost:8069/web/health", timeout=10) as resp:
        assert resp.status == 200


def test_app_db_has_migrated_tables() -> None:
    engine = make_engine()
    tables = set(inspect(engine).get_table_names())
    assert tables >= EXPECTED_TABLES
    assert "alembic_version" in tables


def test_paris_mock_creates_order_with_api_key() -> None:
    body = json.dumps({"buyer": "Comex", "items": [{"sku": "ROSH-MUG-002", "qty": 1}]}).encode()
    req = urllib.request.Request(
        "http://localhost:9100/orders",
        data=body,
        headers={"Content-Type": "application/json", "X-API-Key": PARIS_API_KEY},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 201
        payload = json.loads(resp.read())
        assert payload["status"] == "created"
        assert payload["id"]


def _post_paris_webhook(event_id: str) -> int:
    body = json.dumps({"event_id": event_id, "status": "delivered"}).encode()
    req = urllib.request.Request(
        "http://localhost:8000/webhooks/paris",
        data=body,
        headers={
            "Content-Type": "application/json",
            SIGNATURE_HEADER: sign_payload(PARIS_API_SECRET, body),
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return int(resp.status)


def test_webhook_receiver_writes_bronze_and_dedupes() -> None:
    event_id = f"int-{uuid.uuid4().hex[:12]}"
    assert _post_paris_webhook(event_id) == 200
    assert _post_paris_webhook(event_id) == 200  # duplicate

    engine = make_engine()
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM webhook_log WHERE event_id = :eid"),
            {"eid": event_id},
        ).scalar()
    assert count == 1  # idempotent: single bronze row despite two deliveries
