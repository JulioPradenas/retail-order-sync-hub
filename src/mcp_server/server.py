"""MCP server — read tools for Retail Order Sync Hub.

Tools exposed:
  - get_order_status    — current state from Postgres silver layer
  - trace_order         — cross-source timeline: webhooks → outbox → silver
  - get_dlq_depth       — count of orders stuck in DLQ
  - get_sla_metrics     — p50/p95 sync latency from BigQuery gold layer
  - find_failed_orders  — orders never synced within a time window
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from fastmcp import FastMCP

from src.mcp_server.auth import require_scope
from src.mcp_server.queries import (
    count_dlq_entries,
    find_failed_orders,
    get_bq_sla_metrics,
    get_order_by_id,
    get_outbox_entries,
    get_webhook_events,
)

mcp = FastMCP(
    "retail-order-sync-hub",
    instructions=(
        "Read-only tools for the Retail Order Sync Hub. "
        "Pass your api_token on every call. "
        "Scope required: orders.read for order tools, metrics.read for SLA/DLQ tools."
    ),
)


# --- business logic functions (imported by tests) ---


def _get_order_status(order_id: str, api_token: str = "") -> str:
    require_scope(api_token, "orders.read")
    order = get_order_by_id(order_id)
    if order is None:
        return f"Order '{order_id}' not found."
    return json.dumps(order, indent=2)


def _trace_order(order_id: str, api_token: str = "") -> str:
    require_scope(api_token, "orders.read")

    order = get_order_by_id(order_id)
    if order is None:
        return f"Order '{order_id}' not found."

    mp_order_id = order.get("marketplace_order_id") or ""
    internal_id = str(order["internal_id"])

    webhooks = get_webhook_events(event_id=mp_order_id) if mp_order_id else []
    outbox = get_outbox_entries(internal_id)

    timeline: list[dict[str, object]] = []
    for w in webhooks:
        timeline.append(
            {"at": w["received_at"], "layer": "bronze", "event": "webhook_received", **w}
        )
    for o in outbox:
        timeline.append({"at": o["created_at"], "layer": "outbox", "event": "outbox_enqueued", **o})
    timeline.append(
        {"at": order["created_at"], "layer": "silver", "event": "order_created", **order}
    )
    timeline.sort(key=lambda e: str(e["at"]))

    result = {
        "order": order,
        "timeline": timeline,
        "dlq_entries": [e for e in outbox if e["status"] == "dlq"],
    }
    return json.dumps(result, indent=2)


def _get_dlq_depth(api_token: str = "") -> str:
    require_scope(api_token, "metrics.read")
    depth = count_dlq_entries()
    return json.dumps({"dlq_depth": depth, "checked_at": datetime.now(UTC).isoformat()})


def _get_sla_metrics(marketplace: str, window: str = "7d", api_token: str = "") -> str:
    require_scope(api_token, "metrics.read")
    rows = get_bq_sla_metrics(marketplace, window)
    if not rows:
        return f"No SLA data found for marketplace '{marketplace}'."
    return json.dumps({"marketplace": marketplace, "window": window, "metrics": rows}, indent=2)


def _find_failed_orders(
    since: str = "24h",
    marketplace: str | None = None,
    api_token: str = "",
) -> str:
    require_scope(api_token, "orders.read")

    unit = since[-1]
    try:
        value = int(since[:-1])
    except ValueError:
        return f"Invalid 'since' format '{since}'. Use e.g. '24h', '7d', '1h'."

    delta_map = {"h": timedelta(hours=value), "d": timedelta(days=value)}
    if unit not in delta_map:
        return f"Invalid unit '{unit}' in since='{since}'. Use 'h' (hours) or 'd' (days)."

    since_dt = datetime.now(UTC) - delta_map[unit]
    orders = find_failed_orders(since_dt, marketplace)
    return json.dumps(
        {
            "since": since_dt.isoformat(),
            "marketplace": marketplace,
            "count": len(orders),
            "orders": orders,
        },
        indent=2,
    )


# --- MCP tool registrations ---

get_order_status = mcp.tool(
    description="Return the current status of an order from the silver layer."
)(_get_order_status)

trace_order = mcp.tool(
    description=(
        "Return a cross-source timeline for an order: "
        "inbound webhooks → outbox pushes → silver state."
    )
)(_trace_order)

get_dlq_depth = mcp.tool(description="Return the number of orders currently stuck in the DLQ.")(
    _get_dlq_depth
)

get_sla_metrics = mcp.tool(
    description=(
        "Return SLA metrics (avg, p50, p95 sync time in seconds) for a marketplace "
        "from the BigQuery gold layer."
    )
)(_get_sla_metrics)

find_failed_orders_tool = mcp.tool(
    description="Find orders that were created but never successfully synced to a marketplace."
)(_find_failed_orders)
