"""Fire a burst of signed Paris webhooks at the receiver for demo purposes.

Usage:
    uv run python scripts/send_webhooks.py [--count N] [--delay SECONDS] [--url URL]

The Grafana dashboards plot live rates (e.g. ``rate(webhook_received_total[5m])``),
so the panels look empty until fresh traffic arrives. This populates them on demand.
Requires the stack to be running (``make up``).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

# Allow running from repo root without installing
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common.config import get_settings
from src.common.signing import SIGNATURE_HEADER, sign_payload


def _post_webhook(url: str, secret: str) -> int:
    body = json.dumps({"event_id": f"demo-{uuid.uuid4().hex[:12]}", "status": "delivered"}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", SIGNATURE_HEADER: sign_payload(secret, body)},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return int(resp.status)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--count", type=int, default=40, help="Number of webhooks to send (default: 40)"
    )
    parser.add_argument(
        "--delay", type=float, default=0.4, help="Seconds between webhooks (default: 0.4)"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000/webhooks/paris",
        help="Receiver endpoint (default: %(default)s)",
    )
    args = parser.parse_args()

    secret = get_settings().paris_api_secret
    sent = 0
    for _ in range(args.count):
        try:
            if _post_webhook(args.url, secret) == 200:
                sent += 1
        except (urllib.error.URLError, OSError) as exc:
            print(f"error after {sent} webhooks: {exc}", file=sys.stderr)
            sys.exit(1)
        time.sleep(args.delay)

    print(f"Sent {sent}/{args.count} webhooks to {args.url}")
    print("Open Grafana → Comex Ops, set the range to 'Last 15 minutes'.")


if __name__ == "__main__":
    main()
