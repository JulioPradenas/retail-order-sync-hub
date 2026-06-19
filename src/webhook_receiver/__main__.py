"""Run the webhook receiver: ``python -m src.webhook_receiver``."""

from __future__ import annotations

import uvicorn
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

from src.common.config import get_settings
from src.common.logging import configure_logging
from src.common.otel import setup_metrics, setup_tracing
from src.common.secrets import maybe_load_secrets
from src.webhook_receiver.app import create_app


def main() -> None:
    maybe_load_secrets()  # V2: pull HMAC secrets from Secret Manager before Settings parse
    settings = get_settings()
    configure_logging(settings.log_level)
    setup_tracing(
        service_name=f"{settings.otel_service_name}-webhook-receiver",
        endpoint=settings.otel_exporter_otlp_endpoint,
    )
    setup_metrics(
        service_name=f"{settings.otel_service_name}-webhook-receiver",
        endpoint=settings.otel_exporter_otlp_endpoint,
    )
    SQLAlchemyInstrumentor().instrument()
    app = create_app(settings=settings)
    FastAPIInstrumentor.instrument_app(app)
    uvicorn.run(app, host="0.0.0.0", port=settings.http_port)


if __name__ == "__main__":
    main()
