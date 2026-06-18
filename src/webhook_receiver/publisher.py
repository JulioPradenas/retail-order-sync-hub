"""Pub/Sub publisher (works against the emulator via PUBSUB_EMULATOR_HOST)."""

from __future__ import annotations

from typing import Protocol

from src.common.config import Settings, get_settings


class Publisher(Protocol):
    def publish(self, topic: str, data: bytes, **attributes: str) -> str: ...


class PubSubPublisher:
    """Publishes to Pub/Sub. The client reads ``PUBSUB_EMULATOR_HOST`` itself."""

    def __init__(self, settings: Settings | None = None) -> None:
        from google.cloud import pubsub_v1  # type: ignore[attr-defined]

        self._settings = settings or get_settings()
        self._client = pubsub_v1.PublisherClient()

    def publish(self, topic: str, data: bytes, **attributes: str) -> str:
        topic_path = self._client.topic_path(self._settings.pubsub_project_id, topic)
        future = self._client.publish(topic_path, data, **attributes)
        message_id: str = future.result(timeout=10)
        return message_id
