"""Unit tests for bq_sync logic — no real BigQuery or Postgres needed."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

from src.bq_sync.sync import sync_orders, sync_webhooks
from src.common.config import Settings


def _settings() -> Settings:
    return Settings(
        bq_project_id="test-project",
        bq_bronze_dataset="bronze",
        bq_batch_size=10,
    )


def _make_webhook(
    id: int = 1,
    event_id: str = "ev-1",
    source: str = "paris",
    received_at: datetime | None = None,
) -> MagicMock:
    row = MagicMock()
    row.id = id
    row.event_id = event_id
    row.source = source
    row.received_at = received_at or datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    row.raw_body = {"event_id": event_id}
    row.headers = {"x-foo": "bar"}
    return row


def _make_order(
    internal_id: int = 1,
    marketplace: str = "paris",
    status: str = "confirmed",
    updated_at: datetime | None = None,
) -> MagicMock:
    row = MagicMock()
    row.internal_id = internal_id
    row.odoo_order_id = 42
    row.marketplace = marketplace
    row.marketplace_order_id = f"MP-{internal_id}"
    row.status = status
    row.last_sync_at = None
    row.created_at = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    row.updated_at = updated_at or datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    return row


class TestSyncWebhooks:
    def test_inserts_rows_when_no_watermark(self) -> None:
        bq = MagicMock()
        bq.max_timestamp.return_value = None
        bq.insert_rows.return_value = 2

        webhooks = [_make_webhook(1), _make_webhook(2)]

        with patch("src.bq_sync.sync.session_scope") as mock_scope:
            session = MagicMock()
            session.scalars.return_value = iter(webhooks)
            mock_scope.return_value.__enter__ = MagicMock(return_value=session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            result = sync_webhooks(bq, _settings())

        assert result == 2
        bq.ensure_table.assert_called_once()
        bq.insert_rows.assert_called_once()
        inserted: list[dict[str, Any]] = bq.insert_rows.call_args[0][2]
        assert len(inserted) == 2
        assert inserted[0]["event_id"] == "ev-1"
        assert inserted[0]["source"] == "paris"

    def test_uses_watermark_from_bq(self) -> None:
        bq = MagicMock()
        bq.max_timestamp.return_value = "2026-01-01T00:00:00+00:00"
        bq.insert_rows.return_value = 0

        with patch("src.bq_sync.sync.session_scope") as mock_scope:
            session = MagicMock()
            session.scalars.return_value = iter([])
            mock_scope.return_value.__enter__ = MagicMock(return_value=session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            result = sync_webhooks(bq, _settings())

        assert result == 0
        bq.max_timestamp.assert_called_once_with("bronze", "raw_webhooks", "received_at")

    def test_overrides_watermark_with_since(self) -> None:
        bq = MagicMock()
        bq.insert_rows.return_value = 0

        with patch("src.bq_sync.sync.session_scope") as mock_scope:
            session = MagicMock()
            session.scalars.return_value = iter([])
            mock_scope.return_value.__enter__ = MagicMock(return_value=session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            sync_webhooks(bq, _settings(), since="2026-01-01T00:00:00+00:00")

        bq.max_timestamp.assert_not_called()

    def test_batches_rows(self) -> None:
        bq = MagicMock()
        bq.max_timestamp.return_value = None
        bq.insert_rows.return_value = 5

        webhooks = [_make_webhook(i, f"ev-{i}") for i in range(12)]

        with patch("src.bq_sync.sync.session_scope") as mock_scope:
            session = MagicMock()
            session.scalars.return_value = iter(webhooks)
            mock_scope.return_value.__enter__ = MagicMock(return_value=session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            sync_webhooks(bq, _settings(), batch_size=5)

        # 12 rows / batch_size 5 → 3 insert calls (5 + 5 + 2)
        assert bq.insert_rows.call_count == 3


class TestSyncOrders:
    def test_inserts_rows(self) -> None:
        bq = MagicMock()
        bq.max_timestamp.return_value = None
        bq.insert_rows.return_value = 1

        orders = [_make_order(1)]

        with patch("src.bq_sync.sync.session_scope") as mock_scope:
            session = MagicMock()
            session.scalars.return_value = iter(orders)
            mock_scope.return_value.__enter__ = MagicMock(return_value=session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            result = sync_orders(bq, _settings())

        assert result == 1
        inserted: list[dict[str, Any]] = bq.insert_rows.call_args[0][2]
        assert inserted[0]["marketplace"] == "paris"
        assert inserted[0]["status"] == "confirmed"
        assert "ingested_at" in inserted[0]

    def test_empty_table_returns_zero(self) -> None:
        bq = MagicMock()
        bq.max_timestamp.return_value = None
        bq.insert_rows.return_value = 0

        with patch("src.bq_sync.sync.session_scope") as mock_scope:
            session = MagicMock()
            session.scalars.return_value = iter([])
            mock_scope.return_value.__enter__ = MagicMock(return_value=session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            result = sync_orders(bq, _settings())

        assert result == 0
        bq.insert_rows.assert_not_called()
