"""Thin BigQuery client wrapper for bq_sync."""

from __future__ import annotations

from typing import Any, cast

from google.cloud import bigquery

from src.common.config import Settings, get_settings


class BQClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self._s = settings or get_settings()
        self._client = bigquery.Client(project=self._s.bq_project_id)

    def table_ref(self, dataset: str, table: str) -> str:
        return f"{self._s.bq_project_id}.{dataset}.{table}"

    def max_timestamp(self, dataset: str, table: str, column: str) -> str | None:
        """Return ISO string of MAX(column) in table, or None if table is empty."""
        ref = self.table_ref(dataset, table)
        query = f"SELECT MAX({column}) AS ts FROM `{ref}`"
        rows = list(self._client.query(query).result())
        if not rows or rows[0].ts is None:
            return None
        return cast(str, rows[0].ts.isoformat())

    def insert_rows(self, dataset: str, table: str, rows: list[dict[str, Any]]) -> int:
        """Stream-insert rows; returns count inserted."""
        if not rows:
            return 0
        ref = self.table_ref(dataset, table)
        errors = self._client.insert_rows_json(ref, rows)
        if errors:
            raise RuntimeError(f"BigQuery insert errors: {errors}")
        return len(rows)

    def ensure_table(self, dataset: str, table: str, schema: list[bigquery.SchemaField]) -> None:
        """Create table if it doesn't exist (idempotent)."""
        ref = f"{self._s.bq_project_id}.{dataset}.{table}"
        bq_table = bigquery.Table(ref, schema=schema)
        self._client.create_table(bq_table, exists_ok=True)
