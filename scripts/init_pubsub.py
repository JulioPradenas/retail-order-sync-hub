"""Create Pub/Sub topics and subscriptions on the emulator (idempotent).

Reads ``PUBSUB_EMULATOR_HOST`` (set by docker-compose / .env) so it targets the
emulator, never real GCP. Run via ``uv run python -m scripts.init_pubsub``.
"""

from __future__ import annotations

from google.api_core.exceptions import AlreadyExists
from google.cloud import pubsub_v1
from src.common.config import get_settings
from src.common.logging import configure_logging, get_logger

log = get_logger()


def init_pubsub() -> None:
    settings = get_settings()
    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()
    project = settings.pubsub_project_id

    pairs = [
        (settings.pubsub_topic_events, settings.pubsub_sub_events),
        (settings.pubsub_topic_dlq, settings.pubsub_sub_dlq),
        (settings.pubsub_topic_sync_dlq, settings.pubsub_sub_sync_dlq),
    ]
    for topic, sub in pairs:
        topic_path = publisher.topic_path(project, topic)
        try:
            publisher.create_topic(name=topic_path)
            log.info("pubsub.topic_created", topic=topic)
        except AlreadyExists:
            log.info("pubsub.topic_exists", topic=topic)

        sub_path = subscriber.subscription_path(project, sub)
        try:
            subscriber.create_subscription(name=sub_path, topic=topic_path)
            log.info("pubsub.subscription_created", subscription=sub)
        except AlreadyExists:
            log.info("pubsub.subscription_exists", subscription=sub)


def main() -> int:
    configure_logging(get_settings().log_level)
    init_pubsub()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
