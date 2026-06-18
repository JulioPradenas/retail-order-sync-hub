"""Shared building blocks: config, logging, OTel setup, db helpers.

Phase 0 keeps this package minimal. It grows in Phase 1 (config, logging,
OTel) and beyond.
"""

from src import __version__

#: Logical name used across services for logging/OTel resource attributes.
SERVICE_NAMESPACE = "retail-order-sync-hub"


def service_identity() -> str:
    """Return ``namespace@version`` used to tag logs, spans and metrics."""
    return f"{SERVICE_NAMESPACE}@{__version__}"
