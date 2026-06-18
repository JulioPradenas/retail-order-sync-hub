import pytest
from src.common.config import Settings, get_settings


def test_defaults_are_local_dev() -> None:
    settings = Settings()
    assert settings.env == "local"
    assert settings.app_db_port == 5433
    assert settings.otel_service_name == "retail-order-sync-hub"


def test_app_db_dsn_uses_psycopg_driver() -> None:
    settings = Settings(
        app_db_user="rosh",
        app_db_password="secret",
        app_db_host="db",
        app_db_port=5432,
        app_db_name="rosh",
    )
    assert settings.app_db_dsn == "postgresql+psycopg://rosh:secret@db:5432/rosh"


def test_env_vars_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_DB_HOST", "example.internal")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    settings = Settings()
    assert settings.app_db_host == "example.internal"
    assert settings.log_level == "DEBUG"


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()
