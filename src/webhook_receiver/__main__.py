"""Run the webhook receiver: ``python -m src.webhook_receiver``."""

from __future__ import annotations

import uvicorn
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

from src.common.config import get_settings
from src.common.logging import configure_logging
from src.common.otel import setup_metrics, setup_tracing
from src.webhook_receiver.app import create_app

_settings = get_settings()
configure_logging(_settings.log_level)
setup_tracing(
    service_name=f"{_settings.otel_service_name}-webhook-receiver",
    endpoint=_settings.otel_exporter_otlp_endpoint,
)
setup_metrics(
    service_name=f"{_settings.otel_service_name}-webhook-receiver",
    endpoint=_settings.otel_exporter_otlp_endpoint,
)
SQLAlchemyInstrumentor().instrument()
app = create_app(settings=_settings)
FastAPIInstrumentor.instrument_app(app)


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
