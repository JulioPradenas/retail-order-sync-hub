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

    # MercadoLibre OAuth (sandbox)
    ml_client_id: str = ""
    ml_client_secret: str = ""
    ml_redirect_uri: str = "http://localhost:8000/oauth/mercadolibre/callback"
    ml_auth_base: str = "https://auth.mercadolibre.cl"
    ml_api_base: str = "https://api.mercadolibre.com"
    #: refresh the access token when it has this many seconds (or less) of life left
    ml_refresh_skew_seconds: int = 300

    # paris-mock
    paris_api_key: str = "change-me"
    paris_api_secret: str = "change-me"
    paris_mock_db_path: str = "paris_mock.db"
    paris_base_url: str = "http://localhost:9100"
    #: max in-adapter HTTP attempts (transient errors / 429); durable retry lives in the outbox
    adapter_max_attempts: int = 4

    # Outbox worker
    outbox_max_attempts: int = 5
    outbox_poll_interval_seconds: float = 5.0

    # MercadoLibre inbound webhook secret (HMAC shared secret)
    ml_webhook_secret: str = "change-me"

    # Pub/Sub (emulator in V1)
    pubsub_emulator_host: str = "localhost:8085"
    pubsub_project_id: str = "retail-order-sync-local"
    pubsub_topic_events: str = "marketplace.events"
    pubsub_sub_events: str = "marketplace.events.sub"
    pubsub_topic_dlq: str = "marketplace.dlq"
    pubsub_sub_dlq: str = "marketplace.dlq.sub"
    pubsub_topic_sync_dlq: str = "marketplace.sync.dlq"
    pubsub_sub_sync_dlq: str = "marketplace.sync.dlq.sub"

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
