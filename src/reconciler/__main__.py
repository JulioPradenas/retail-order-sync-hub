"""Reconciler loop (safety net): periodically fix Odoo drift vs silver.

Run with ``python -m src.reconciler``.
"""

from __future__ import annotations

import time

from src.common.config import get_settings
from src.common.db import session_scope
from src.common.logging import configure_logging, get_logger
from src.common.odoo import OdooClient
from src.common.otel import setup_metrics
from src.reconciler.reconcile import reconcile_once

log = get_logger()


def run_forever() -> None:
    settings = get_settings()
    odoo = OdooClient(settings)
    while True:
        with session_scope() as session:
            drift = reconcile_once(odoo, session)
        log.info("reconciler.cycle", drift_fixed=drift)
        time.sleep(settings.reconciler_interval_seconds)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    setup_metrics(
        service_name=f"{settings.otel_service_name}-reconciler",
        endpoint=settings.otel_exporter_otlp_endpoint,
    )
    run_forever()


if __name__ == "__main__":
    main()
