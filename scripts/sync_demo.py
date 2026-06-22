"""Enqueue pending outbox entries so the worker emits live sync outcomes.

Usage:
    uv run python scripts/sync_demo.py [--count N] [--adapter ADAPTER]

The "Order sync outcomes / min" panel plots ``rate(order_sync_total[5m])`` by
status, so it stays empty until the outbox worker *processes* entries and fails
them. (``flood_dlq.py`` inserts ``status=dlq`` rows directly and never triggers
the worker, so it does not feed this panel.)

This inserts *pending* entries that the running worker will pick up and fail
(mercadolibre has no OAuth creds locally, so every push fails):
  - half start at attempts=0          -> first failure -> status=retry
  - half start at outbox_max_attempts-1 -> first failure -> status=dlq

Requires the stack to be running (make up && make migrate). Outcomes appear
within one worker poll cycle (~5s); leave it a minute for the rate to build up.
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

# Allow running from repo root without installing
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common.config import get_settings
from src.common.db import get_session_factory, make_engine
from src.common.models import OutboxEntry


def _make_pending_entry(order_id: int, adapter: str, attempts: int, now: datetime) -> OutboxEntry:
    entry = OutboxEntry()
    entry.aggregate_id = str(order_id)
    entry.aggregate_type = "order"
    entry.target_adapter = adapter
    entry.payload = {
        "odoo_order_id": order_id,
        "buyer": f"Cliente Demo {order_id}",
        "external_ref": f"odoo-{order_id}",
        "items": [{"sku": f"SKU-{random.randint(1000, 9999)}", "qty": random.randint(1, 5)}],
    }
    entry.status = "pending"
    entry.attempts = attempts
    entry.created_at = now
    entry.updated_at = now
    entry.next_attempt_at = now  # due immediately
    return entry


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--count", type=int, default=12, help="Number of pending entries to create (default: 12)"
    )
    parser.add_argument("--adapter", default="mercadolibre", help="Target adapter")
    args = parser.parse_args()

    settings = get_settings()
    make_engine(settings)
    factory = get_session_factory()

    near_dlq = settings.outbox_max_attempts - 1
    base_order_id = random.randint(700_000, 800_000)
    now = datetime.now(UTC)
    entries = [
        _make_pending_entry(
            order_id=base_order_id + i,
            adapter=args.adapter,
            attempts=0 if i % 2 == 0 else near_dlq,
            now=now,
        )
        for i in range(args.count)
    ]

    with factory() as session:
        session.add_all(entries)
        session.commit()

    n_retry = sum(1 for e in entries if e.attempts == 0)
    n_dlq = len(entries) - n_retry
    print(
        f"Enqueued {len(entries)} pending '{args.adapter}' entries "
        f"({n_retry} → retry, {n_dlq} → dlq)."
    )
    print("The outbox worker will fail them within ~5s and emit order_sync_total.")
    print("Open Grafana → Comex Ops, range 'Last 15 minutes'.")


if __name__ == "__main__":
    main()
