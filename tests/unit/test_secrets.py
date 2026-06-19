"""Unit tests for the Secret Manager loader (V2.1)."""

from __future__ import annotations

import sys
from contextlib import AbstractContextManager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from src.common import secrets
from src.common.secrets import _secret_env_name, load_secrets_into_env, maybe_load_secrets


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("PARIS_API_SECRET", "ML_WEBHOOK_SECRET", "USE_SECRET_MANAGER", "GCP_PROJECT_ID"):
        monkeypatch.delenv(var, raising=False)


def _fake_client(values: dict[str, str]) -> MagicMock:
    client = MagicMock()

    def access(*, name: str) -> SimpleNamespace:
        secret_id = name.split("/secrets/")[1].split("/versions/")[0]
        payload = SimpleNamespace(data=values[secret_id].encode())
        return SimpleNamespace(payload=payload)

    client.access_secret_version.side_effect = access
    return client


def _patch_secretmanager(client: MagicMock) -> AbstractContextManager[None]:
    module = SimpleNamespace(SecretManagerServiceClient=MagicMock(return_value=client))
    return patch.dict(sys.modules, {"google.cloud.secretmanager": module})


def test_secret_env_name_maps_hyphen_to_upper_snake() -> None:
    assert _secret_env_name("paris-api-secret") == "PARIS_API_SECRET"


def test_load_sets_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _fake_client({"PARIS_API_SECRET": "real-secret", "ML_WEBHOOK_SECRET": "ml-secret"})
    with _patch_secretmanager(client):
        loaded = load_secrets_into_env(
            project_id="my-proj", secret_ids=["PARIS_API_SECRET", "ML_WEBHOOK_SECRET"]
        )
    assert loaded == 2
    import os

    assert os.environ["PARIS_API_SECRET"] == "real-secret"
    assert os.environ["ML_WEBHOOK_SECRET"] == "ml-secret"


def test_existing_env_var_is_not_overwritten(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PARIS_API_SECRET", "local-dev-value")
    client = _fake_client({"PARIS_API_SECRET": "remote-value"})
    with _patch_secretmanager(client):
        loaded = load_secrets_into_env(project_id="my-proj", secret_ids=["PARIS_API_SECRET"])
    assert loaded == 0
    import os

    assert os.environ["PARIS_API_SECRET"] == "local-dev-value"


def test_no_op_without_project_or_secrets() -> None:
    assert load_secrets_into_env(project_id="", secret_ids=["X"]) == 0
    assert load_secrets_into_env(project_id="p", secret_ids=[]) == 0


def test_one_bad_secret_does_not_abort_others(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()

    def access(*, name: str) -> SimpleNamespace:
        if "BAD" in name:
            raise RuntimeError("permission denied")
        return SimpleNamespace(payload=SimpleNamespace(data=b"ok"))

    client.access_secret_version.side_effect = access
    with _patch_secretmanager(client):
        loaded = load_secrets_into_env(project_id="p", secret_ids=["BAD_ONE", "GOOD_ONE"])
    assert loaded == 1
    import os

    assert os.environ["GOOD_ONE"] == "ok"


def test_missing_client_library_is_handled(monkeypatch: pytest.MonkeyPatch) -> None:
    with patch.dict(sys.modules, {"google.cloud.secretmanager": None}):
        loaded = load_secrets_into_env(project_id="p", secret_ids=["X"])
    assert loaded == 0


def test_maybe_load_disabled_by_default() -> None:
    assert maybe_load_secrets() == 0


def test_maybe_load_enabled_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USE_SECRET_MANAGER", "true")
    monkeypatch.setenv("GCP_PROJECT_ID", "my-proj")
    monkeypatch.setenv("SECRET_MANAGER_SECRETS", "PARIS_API_SECRET")
    called: dict[str, object] = {}

    def fake_load(*, project_id: str, secret_ids: list[str]) -> int:
        called["project_id"] = project_id
        called["secret_ids"] = secret_ids
        return len(secret_ids)

    monkeypatch.setattr(secrets, "load_secrets_into_env", fake_load)
    assert maybe_load_secrets() == 1
    assert called == {"project_id": "my-proj", "secret_ids": ["PARIS_API_SECRET"]}
