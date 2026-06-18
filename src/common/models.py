"""Operational data models for ``app_db``.

Phase 1 lays down the schema skeleton. Tables are created empty here; the
services that populate them land in later phases:

- ``webhook_log`` / ``webhook_dedup``  -> Phase 3 (receiver, bronze + dedupe)
- ``outbox``                            -> Phase 4 (outbound sync)
- ``orders``                            -> Phase 5 (subscriber, silver)
- ``oauth_tokens``                      -> Phase 2 (MercadoLibre OAuth)
- ``mcp_audit_log``                     -> Phase 9 (MCP write tools, append-only)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.common.db import Base


class WebhookLog(Base):
    """Raw inbound webhook payloads (bronze)."""

    __tablename__ = "webhook_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(255), index=True)
    source: Mapped[str] = mapped_column(String(50), index=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    raw_body: Mapped[dict[str, Any]] = mapped_column(JSON)
    headers: Mapped[dict[str, Any]] = mapped_column(JSON)


class WebhookDedup(Base):
    """Idempotency keys for inbound webhooks (insert ON CONFLICT DO NOTHING)."""

    __tablename__ = "webhook_dedup"

    source: Mapped[str] = mapped_column(String(50), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Order(Base):
    """Normalized order state (silver)."""

    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("marketplace", "marketplace_order_id", name="uq_orders_marketplace_id"),
    )

    internal_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    odoo_order_id: Mapped[int | None] = mapped_column(Integer, index=True)
    marketplace: Mapped[str] = mapped_column(String(50))
    marketplace_order_id: Mapped[str | None] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(50))
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class OutboxEntry(Base):
    """Transactional outbox for outbound marketplace sync."""

    __tablename__ = "outbox"
    __table_args__ = (
        UniqueConstraint("aggregate_id", "target_adapter", name="uq_outbox_aggregate_target"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    aggregate_type: Mapped[str] = mapped_column(String(50))
    aggregate_id: Mapped[str] = mapped_column(String(255), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    target_adapter: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    error_log: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class OAuthToken(Base):
    """Stored OAuth2 tokens per provider (e.g. MercadoLibre)."""

    __tablename__ = "oauth_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), unique=True)
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class McpAuditLog(Base):
    """Append-only audit trail for MCP write tools (enforced in Phase 9)."""

    __tablename__ = "mcp_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    tool_name: Mapped[str] = mapped_column(String(100), index=True)
    params_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    scope_used: Mapped[str | None] = mapped_column(String(100))
    result_status: Mapped[str] = mapped_column(String(20))
    error_message: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
