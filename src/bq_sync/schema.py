"""BigQuery table schemas for bronze layer."""

from __future__ import annotations

from google.cloud import bigquery

RAW_WEBHOOKS: list[bigquery.SchemaField] = [
    bigquery.SchemaField("id", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("event_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("source", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("received_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("raw_body", "JSON", mode="NULLABLE"),
    bigquery.SchemaField("headers", "JSON", mode="NULLABLE"),
    bigquery.SchemaField("ingested_at", "TIMESTAMP", mode="REQUIRED"),
]

RAW_ORDERS: list[bigquery.SchemaField] = [
    bigquery.SchemaField("internal_id", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("odoo_order_id", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("marketplace", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("marketplace_order_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("last_sync_at", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("updated_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("ingested_at", "TIMESTAMP", mode="REQUIRED"),
]
