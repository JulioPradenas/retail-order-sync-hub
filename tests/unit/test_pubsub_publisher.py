"""Unit tests for PubSubPublisher — pubsub_v1 mocked at google.cloud level."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.common.config import Settings
from src.webhook_receiver.publisher import PubSubPublisher

_SETTINGS = Settings()


def _make_mock_client(message_id: str = "msg-id-1") -> MagicMock:
    mock_client = MagicMock()
    mock_client.topic_path.return_value = "projects/p/topics/t"
    mock_client.publish.return_value.result.return_value = message_id
    return mock_client


def test_publish_returns_message_id() -> None:
    mock_client = _make_mock_client("msg-42")
    mock_pubsub = MagicMock()
    mock_pubsub.PublisherClient.return_value = mock_client

    # patch the attribute on google.cloud so the local import gets the mock
    with patch("google.cloud.pubsub_v1", mock_pubsub, create=True):
        publisher = PubSubPublisher(_SETTINGS)
        result = publisher.publish("events-topic", b"payload", source="paris")

    assert result == "msg-42"
    mock_client.publish.assert_called_once_with("projects/p/topics/t", b"payload", source="paris")


def test_publisher_stores_settings() -> None:
    mock_client = _make_mock_client()
    mock_pubsub = MagicMock()
    mock_pubsub.PublisherClient.return_value = mock_client

    with patch("google.cloud.pubsub_v1", mock_pubsub, create=True):
        publisher = PubSubPublisher(_SETTINGS)

    assert publisher._settings is _SETTINGS
    assert publisher._client is mock_client
