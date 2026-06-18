"""Integration checks against the running docker stack.

Skipped unless ``ROSH_INTEGRATION=1`` (see tests/conftest.py). Run with:

    make up && ROSH_INTEGRATION=1 uv run pytest -m integration
"""

from __future__ import annotations

import urllib.request

import pytest
from sqlalchemy import inspect
from src.common.db import make_engine

pytestmark = pytest.mark.integration

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
