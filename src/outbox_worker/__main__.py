"""Outbox worker loop: poll Odoo -> enqueue -> push due entries.

Run with ``python -m src.outbox_worker``.
"""

from __future__ import annotations

import asyncio

from src.adapters.base import MarketplaceAdapter
from src.common.config import Settings, get_settings
from src.common.logging import configure_logging, get_logger
from src.common.odoo import OdooClient
from src.common.otel import setup_tracing
from src.outbox_worker.enqueue import enqueue_orders
from src.outbox_worker.processor import default_adapters, process_pending
from src.outbox_worker.source import fetch_confirmed_orders
from src.webhook_receiver.publisher import Publisher, PubSubPublisher

log = get_logger()


async def run_once(
    settings: Settings, adapters: dict[str, MarketplaceAdapter], publisher: Publisher
) -> None:
    orders = fetch_confirmed_orders(OdooClient(settings))
    added = enqueue_orders(orders, list(adapters))
    outcomes = await process_pending(adapters, publisher, settings)
    log.info("outbox.cycle", enqueued=added, processed=len(outcomes))


async def run_forever() -> None:
    settings = get_settings()
    adapters = default_adapters()
    publisher = PubSubPublisher(settings)
    while True:
        try:
            await run_once(settings, adapters, publisher)
        except Exception as exc:
            log.error("outbox.cycle_failed", error=str(exc))
        await asyncio.sleep(settings.outbox_poll_interval_seconds)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    setup_tracing(
        service_name=f"{settings.otel_service_name}-outbox-worker",
        endpoint=settings.otel_exporter_otlp_endpoint,
    )
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
