"""Unit tests for OdooClient — XML-RPC mocked."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from src.common.config import Settings
from src.common.odoo import OdooClient

_SETTINGS = Settings(
    odoo_url="http://odoo:8069",
    odoo_db="rosh",
    odoo_user="admin",
    odoo_password="admin",
)


def _make_client(
    uid: int = 7, execute_side_effect: list[object] | None = None
) -> tuple[OdooClient, MagicMock]:
    """Return a configured OdooClient with a mocked ServerProxy."""
    mock_proxy = MagicMock()
    mock_proxy.authenticate.return_value = uid
    if execute_side_effect:
        mock_proxy.execute_kw.side_effect = execute_side_effect
    with patch("src.common.odoo.xmlrpc.client.ServerProxy", return_value=mock_proxy):
        client = OdooClient(_SETTINGS)
    return client, mock_proxy


def test_init_success_stores_uid() -> None:
    client, proxy = _make_client(uid=7)
    assert client._uid == 7
    proxy.authenticate.assert_called_once_with("rosh", "admin", "admin", {})


def test_init_auth_failure_raises() -> None:
    mock_proxy = MagicMock()
    mock_proxy.authenticate.return_value = 0  # Odoo returns 0 on bad credentials
    with (
        patch("src.common.odoo.xmlrpc.client.ServerProxy", return_value=mock_proxy),
        pytest.raises(RuntimeError, match="authentication failed"),
    ):
        OdooClient(_SETTINGS)


def test_execute_delegates_to_execute_kw() -> None:
    client, proxy = _make_client(uid=7)
    proxy.execute_kw.return_value = [1, 2, 3]
    result = client.execute("res.partner", "search", [("active", "=", True)])
    assert result == [1, 2, 3]
    proxy.execute_kw.assert_called_once_with(
        "rosh", 7, "admin", "res.partner", "search", [[("active", "=", True)]], {}
    )


def test_upsert_creates_when_not_found() -> None:
    client, _ = _make_client(uid=7, execute_side_effect=[[], 99])
    result = client.upsert("res.partner", "name", {"name": "Comex"})
    assert result == 99


def test_upsert_writes_when_found() -> None:
    client, _ = _make_client(uid=7, execute_side_effect=[[42], True])
    result = client.upsert("res.partner", "name", {"name": "Comex"})
    assert result == 42


def test_search_read_returns_list() -> None:
    client, proxy = _make_client(uid=7)
    proxy.execute_kw.return_value = [{"id": 1, "name": "Test"}]
    result = client.search_read("sale.order", [("state", "=", "sale")], ["id", "name"])
    assert result == [{"id": 1, "name": "Test"}]
