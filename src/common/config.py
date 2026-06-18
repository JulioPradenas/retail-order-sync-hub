"""Application configuration via Pydantic Settings.

Values come from environment variables (see ``.env.example``) and fall back to
local-dev defaults so the package imports cleanly in tests and CI.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed settings shared across all services."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    env: str = "local"
    log_level: str = "INFO"

    # Operational Postgres (app_db)
    app_db_host: str = "localhost"
    app_db_port: int = 5433
    app_db_user: str = "rosh"
    app_db_password: str = "change-me"
    app_db_name: str = "rosh"

    # Odoo ERP
    odoo_url: str = "http://localhost:8069"
    odoo_db: str = "odoo"
    odoo_user: str = "admin"
    odoo_password: str = "admin"

    # OpenTelemetry
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "retail-order-sync-hub"

    @property
    def app_db_dsn(self) -> str:
        """SQLAlchemy DSN for the operational Postgres (psycopg 3 driver)."""
        return (
            f"postgresql+psycopg://{self.app_db_user}:{self.app_db_password}"
            f"@{self.app_db_host}:{self.app_db_port}/{self.app_db_name}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance (one parse per process)."""
    return Settings()
