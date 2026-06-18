from typing import Any

import pytest
from scripts.seed_odoo import ORDER_REF, OdooClient, seed


def test_upsert_creates_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OdooClient.__new__(OdooClient)
    calls: list[tuple[str, str]] = []

    def fake_execute(model: str, method: str, *args: Any, **kwargs: Any) -> Any:
        calls.append((model, method))
        return [] if method == "search" else 42

    monkeypatch.setattr(client, "execute", fake_execute)
    record_id = client.upsert("product.product", "default_code", {"default_code": "X"})

    assert record_id == 42
    assert ("product.product", "create") in calls
    assert ("product.product", "write") not in calls


def test_upsert_updates_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OdooClient.__new__(OdooClient)
    calls: list[tuple[str, str]] = []

    def fake_execute(model: str, method: str, *args: Any, **kwargs: Any) -> Any:
        calls.append((model, method))
        return [7] if method == "search" else None

    monkeypatch.setattr(client, "execute", fake_execute)
    record_id = client.upsert("res.partner", "ref", {"ref": "ROSH-CUST-001"})

    assert record_id == 7
    assert ("res.partner", "write") in calls
    assert ("res.partner", "create") not in calls


def test_seed_builds_expected_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OdooClient.__new__(OdooClient)
    monkeypatch.setattr(client, "upsert", lambda model, key, values: 1)

    def fake_execute(model: str, method: str, *args: Any, **kwargs: Any) -> Any:
        return [] if method == "search" else 555

    monkeypatch.setattr(client, "execute", fake_execute)
    summary = seed(client)

    assert summary["order_id"] == 555
    assert summary["order_ref"] == ORDER_REF
    assert set(summary["products"]) == {
        "ROSH-TSHIRT-001",
        "ROSH-MUG-002",
        "ROSH-CAP-003",
    }
    assert set(summary["partners"]) == {"ROSH-CUST-001", "ROSH-CUST-002"}
