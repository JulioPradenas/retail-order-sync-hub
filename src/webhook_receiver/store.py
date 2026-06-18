"""Bronze + dedupe persistence for inbound webhooks.

``DbWebhookStore`` inserts the dedupe key with ``ON CONFLICT DO NOTHING`` and,
only on a genuinely new key, writes the raw payload to the bronze
``webhook_log``. The store is a Protocol so the receiver can be unit-tested with
an in-memory fake.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.common.db import session_scope
from src.common.models import WebhookDedup, WebhookLog


@dataclass(frozen=True)
class RecordResult:
    is_new: bool
    raw_ref: str


class WebhookStore(Protocol):
    def record(
        self, source: str, event_id: str, raw_body: dict[str, Any], headers: dict[str, str]
    ) -> RecordResult: ...


class DbWebhookStore:
    """Postgres-backed store (dedupe + bronze) for ``app_db``."""

    def record(
        self, source: str, event_id: str, raw_body: dict[str, Any], headers: dict[str, str]
    ) -> RecordResult:
        with session_scope() as session:
            # RETURNING makes the "did we insert?" check reliable: psycopg
            # reports rowcount=-1 for ON CONFLICT DO NOTHING, so we look at
            # whether a row came back instead.
            stmt = (
                pg_insert(WebhookDedup)
                .values(source=source, event_id=event_id)
                .on_conflict_do_nothing(index_elements=["source", "event_id"])
                .returning(WebhookDedup.event_id)
            )
            is_new = session.execute(stmt).first() is not None
            if not is_new:
                return RecordResult(is_new=False, raw_ref=f"webhook_log:{source}:{event_id}")

            row = WebhookLog(event_id=event_id, source=source, raw_body=raw_body, headers=headers)
            session.add(row)
            session.flush()
            return RecordResult(is_new=True, raw_ref=f"webhook_log:{row.id}")
