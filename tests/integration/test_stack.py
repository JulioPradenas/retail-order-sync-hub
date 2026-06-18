"""Integration checks against the running docker stack.

Skipped unless ``ROSH_INTEGRATION=1`` (see tests/conftest.py). Run with:

    make up && ROSH_INTEGRATION=1 uv run pytest -m integration
"""

from __future__ import annotations

import json
import os
import urllib.request

import pytest
from sqlalchemy import inspect
from src.common.db import make_engine

pytestmark = pytest.mark.integration

PARIS_API_KEY = os.getenv("PARIS_API_KEY", "change-me")

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
