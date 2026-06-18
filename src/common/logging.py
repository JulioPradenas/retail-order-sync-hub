"""Structured JSON logging via structlog.

A single :func:`configure_logging` call wires structlog to emit one JSON object
per log line, with ISO timestamps and the service identity attached — the shape
log aggregators and Grafana/Loki expect.
"""

from __future__ import annotations

import logging

import structlog

from src.common import service_identity


def configure_logging(level: str = "INFO") -> None:
    """Configure stdlib logging + structlog to emit JSON to stdout."""
    log_level = logging.getLevelName(level.upper())
    logging.basicConfig(format="%(message)s", level=log_level, force=True)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(**initial_values: object) -> structlog.stdlib.BoundLogger:
    """Return a bound logger pre-tagged with the service identity."""
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(
        service=service_identity(), **initial_values
    )
    return logger
