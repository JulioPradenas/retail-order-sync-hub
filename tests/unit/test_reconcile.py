from typing import Any, cast

from sqlalchemy.orm import Session
from src.common.odoo import OdooClient
from src.reconciler.reconcile import reconcile_once, reconcile_to_odoo


class FakeOdoo:
    def __init__(self, note: Any = None) -> None:
        self.records: dict[int, dict[str, Any]] = {1: {"id": 1, "note": note}}
        self.writes = 0

    def search_read(
        self, model: str, domain: list[Any], fields: list[str], **kwargs: Any
    ) -> list[dict[str, Any]]:
        rid = domain[0][2]
        rec = self.records.get(rid)
        return [{"note": rec["note"]}] if rec else []

    def execute(self, model: str, method: str, *args: Any, **kwargs: Any) -> Any:
        if method == "write":
            ids, vals = args
            for rid in ids:
                self.records[rid]["note"] = vals["note"]
            self.writes += 1
        return True


class _Result:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


class FakeSession:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def execute(self, statement: Any) -> _Result:
        return _Result(self._rows)


def test_reconcile_to_odoo_writes_then_is_idempotent() -> None:
    odoo = FakeOdoo(note=None)
    assert reconcile_to_odoo(cast(OdooClient, odoo), 1, "delivered") is True
    assert reconcile_to_odoo(cast(OdooClient, odoo), 1, "delivered") is False
    assert odoo.writes == 1


def test_reconcile_to_odoo_returns_false_when_order_not_found() -> None:
    odoo = FakeOdoo(note=None)
    assert reconcile_to_odoo(cast(OdooClient, odoo), 9999, "delivered") is False


def test_reconcile_once_detects_and_fixes_drift() -> None:
    odoo = FakeOdoo(note=None)
    session = cast(Session, FakeSession([(1, "delivered")]))
    assert reconcile_once(cast(OdooClient, odoo), session) == 1
    # second pass: Odoo already reflects the status -> no drift
    assert reconcile_once(cast(OdooClient, odoo), session) == 0
