"""Reusable Odoo XML-RPC client (seed + outbox poller share it)."""

from __future__ import annotations

import xmlrpc.client
from typing import Any, cast

from src.common.config import Settings, get_settings


class OdooClient:
    """Thin XML-RPC wrapper around the Odoo external API."""

    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        self._db = settings.odoo_db
        self._password = settings.odoo_password
        common = xmlrpc.client.ServerProxy(f"{settings.odoo_url}/xmlrpc/2/common")
        uid = common.authenticate(self._db, settings.odoo_user, self._password, {})
        if not uid:
            raise RuntimeError("Odoo authentication failed — check ODOO_* settings")
        self._uid: int = cast(int, uid)
        self._models = xmlrpc.client.ServerProxy(f"{settings.odoo_url}/xmlrpc/2/object")

    @property
    def uid(self) -> int:
        """Authenticated user id (used to grant the seed user its own groups)."""
        return self._uid

    def execute(self, model: str, method: str, *args: Any, **kwargs: Any) -> Any:
        return self._models.execute_kw(
            self._db, self._uid, self._password, model, method, list(args), kwargs
        )

    def upsert(self, model: str, key_field: str, values: dict[str, Any]) -> int:
        """Create or update a record matched by ``key_field``; return its id."""
        existing: list[int] = self.execute(
            model, "search", [(key_field, "=", values[key_field])], limit=1
        )
        if existing:
            record_id = existing[0]
            self.execute(model, "write", [record_id], values)
            return record_id
        return int(self.execute(model, "create", values))

    def search_read(
        self, model: str, domain: list[Any], fields: list[str], **kwargs: Any
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = self.execute(
            model, "search_read", domain, fields=fields, **kwargs
        )
        return result
