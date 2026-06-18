# ADR 004 — Storage analítico: PostgreSQL operacional + BigQuery bronze/silver/gold con dbt

- **Status:** Accepted
- **Fecha:** 2026-06-17
- **Decisores:** Julio Pradenas

## Contexto

Se necesitan dos planos de datos: uno **operacional** (baja latencia, escrituras
transaccionales: outbox, dedupe, orders, audit) y uno **analítico** (SLA,
tendencias de error, throughput). El JD pide explícitamente **bronze/silver/gold**,
**BigQuery** y **dbt**.

## Opciones consideradas

- **A) Postgres operacional + BigQuery (bronze/silver/gold) con dbt** — separa
  OLTP de OLAP y cubre tres bullets del JD de una vez.
- **B) Solo Postgres** (incl. analítica) — simple pero no demuestra DWH ni dbt.
- **C) Solo BigQuery** — mal fit para escrituras transaccionales de baja latencia.

## Decisión

Adoptamos la **opción A**:

- **PostgreSQL 16** operacional para outbox, dedupe, `orders` (silver
  operacional), `mcp_audit_log`.
- **BigQuery** como DWH con capas `bronze` (raw), `silver` (normalizado) y
  `gold` (marts: `sla_by_marketplace`, `error_trends`, `daily_throughput`,
  `dlq_root_causes`).
- **dbt-bigquery** para transformaciones, **contracts** (schema evolution
  segura), **tests** (unique/not_null/relationships/custom) y **docs**.
- Sync incremental Postgres → BigQuery bronze vía watermark (`src/bq_sync/`).

## Consecuencias

- (+) Cubre bronze/silver/gold + BigQuery + dbt (tres requisitos del JD).
- (+) Contracts y tests dan confianza ante cambios de esquema.
- (−) Introduce GCP y costos; se acota con BQ free tier (1 TB query/mes) y
  control de costos en V2.4.
- (−) Latencia bronze por ser batch; aceptable para analítica (no operacional).
