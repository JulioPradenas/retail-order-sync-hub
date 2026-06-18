"""Subscriber loop: pull marketplace.events, write silver, reconcile, ack.

Run with ``python -m src.subscriber``.
"""

from __future__ import annotations

import json

from src.common.config import get_settings
from src.common.db import session_scope
from src.common.logging import configure_logging, get_logger
from src.common.odoo import OdooClient
from src.common.otel import setup_metrics, setup_tracing
from src.subscriber.handler import handle_envelope
from src.webhook_receiver.publisher import PubSubPublisher

log = get_logger()


def run_forever() -> None:
    from google.cloud import pubsub_v1

    settings = get_settings()
    subscriber = pubsub_v1.SubscriberClient()
    sub_path = subscriber.subscription_path(settings.pubsub_project_id, settings.pubsub_sub_events)
    publisher = PubSubPublisher(settings)
    odoo = OdooClient(settings)

    while True:
        response = subscriber.pull(subscription=sub_path, max_messages=20, timeout=20)
        ack_ids: list[str] = []
        for received in response.received_messages:
            try:
                envelope = json.loads(received.message.data)
                with session_scope() as session:
                    handle_envelope(
                        envelope,
                        session=session,
                        settings=settings,
                        publisher=publisher,
                        odoo=odoo,
                    )
                ack_ids.append(received.ack_id)
            except Exception as exc:
                log.error("subscriber.transient_error", error=str(exc))
        if ack_ids:
            subscriber.acknowledge(subscription=sub_path, ack_ids=ack_ids)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    setup_tracing(
        service_name=f"{settings.otel_service_name}-subscriber",
        endpoint=settings.otel_exporter_otlp_endpoint,
    )
    setup_metrics(
        service_name=f"{settings.otel_service_name}-subscriber",
        endpoint=settings.otel_exporter_otlp_endpoint,
    )
    run_forever()


if __name__ == "__main__":
    main()
