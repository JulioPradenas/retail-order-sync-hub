"""
Populate the outbox with DLQ entries for MCP demo purposes.

Usage:
    uv run python scripts/chaos/flood_dlq.py [--count N] [--adapter ADAPTER] [--dry-run]

Creates N OutboxEntry rows with status="dlq" so that MCP tools like
get_dlq_depth, trace_order, and replay_dlq_message have real data to work with.
Requires the stack to be running (make up && make migrate).
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Allow running from repo root without installing
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.common.config import get_settings
from src.common.db import get_session_factory, make_engine
from src.common.models import OutboxEntry

_ADAPTERS = ["mercadolibre", "paris"]

_ERROR_TEMPLATES = [
    "HTTPStatusError: 503 Service Unavailable after 4 attempts",
    "httpx.ConnectTimeout: timed out connecting to api.mercadolibre.com:443",
    "HTTPStatusError: 429 Too Many Requests — rate limit exceeded",
    "JSONDecodeError: Expecting value: line 1 column 1 (upstream returned HTML error page)",
    "HTTPStatusError: 401 Unauthorized — token expired mid-flight",
]


def _make_dlq_entry(
    order_id: int,
    adapter: str,
    created_at: datetime,
) -> OutboxEntry:
    entry = OutboxEntry()
    entry.aggregate_id = str(order_id)
    entry.aggregate_type = "order"
    entry.target_adapter = adapter
    entry.payload = {
        "odoo_order_id": order_id,
        "marketplace_order_id": f"{adapter[:2].upper()}-{order_id:05d}",
        "customer_name": f"Cliente Demo {order_id}",
        "total_amount": round(random.uniform(15_000, 350_000), 2),
        "currency": "CLP",
        "items": [
            {
                "sku": f"SKU-{random.randint(1000, 9999)}",
                "qty": random.randint(1, 5),
                "unit_price": round(random.uniform(5_000, 80_000), 2),
            }
        ],
    }
    entry.status = "dlq"
    entry.attempts = 4
    entry.created_at = created_at
    entry.updated_at = created_at + timedelta(minutes=random.randint(5, 120))
    entry.next_attempt_at = created_at  # already in DLQ — won't be retried
    entry.error_log = random.choice(_ERROR_TEMPLATES)
    return entry


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--count", type=int, default=10, help="Number of DLQ entries to create (default: 10)"
    )
    parser.add_argument(
        "--adapter", choices=[*_ADAPTERS, "both"], default="both", help="Target adapter"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print what would be inserted without writing"
    )
    args = parser.parse_args()

    adapters = _ADAPTERS if args.adapter == "both" else [args.adapter]
    settings = get_settings()
    make_engine(settings)
    factory = get_session_factory()

    base_order_id = random.randint(10_000, 90_000)
    now = datetime.now(UTC)
    entries = [
        _make_dlq_entry(
            order_id=base_order_id + i,
            adapter=adapters[i % len(adapters)],
            created_at=now - timedelta(hours=random.randint(1, 48)),
        )
        for i in range(args.count)
    ]

    if args.dry_run:
        for e in entries:
            err = e.error_log[:60] if e.error_log else ""
            print(f"  [dry-run] order={e.aggregate_id} adapter={e.target_adapter} error={err!r}")
        print(f"\nWould insert {len(entries)} DLQ entries.")
        return

    with factory() as session:
        session.add_all(entries)
        session.commit()
        ids = [e.id for e in entries]

    print(f"Inserted {len(ids)} DLQ entries: ids {ids[0]}..{ids[-1]}")
    print("Run 'make mcp-demo' or use Claude to replay them.")


if __name__ == "__main__":
    main()
