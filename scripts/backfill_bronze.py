"""Backfill bronze layer from a given date.

Usage:
    uv run python -m scripts.backfill_bronze --from-date 2026-01-01
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime

from src.bq_sync.client import BQClient
from src.bq_sync.sync import sync_orders, sync_webhooks
from src.common.config import get_settings
from src.common.logging import configure_logging, get_logger

log = get_logger()


def _parse_date(value: str) -> str:
    dt = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)
    return dt.isoformat()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill bronze BQ tables from a given date.")
    parser.add_argument("--from-date", required=True, help="Start date YYYY-MM-DD (UTC)")
    args = parser.parse_args()

    since = _parse_date(args.from_date)
    settings = get_settings()
    configure_logging(settings.log_level)
    bq = BQClient(settings)

    webhooks = sync_webhooks(bq, settings, since=since)
    orders = sync_orders(bq, settings, since=since)
    log.info("backfill.done", from_date=args.from_date, webhooks=webhooks, orders=orders)


if __name__ == "__main__":
    main()
