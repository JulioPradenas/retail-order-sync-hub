# Retail Order Sync Hub — ERP ↔ Marketplaces

[![CI](https://github.com/JulioPradenas/retail-order-sync-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/JulioPradenas/retail-order-sync-hub/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11-blue)
![Status](https://img.shields.io/badge/status-WIP%20(phase%200)-orange)

Sincroniza órdenes entre un **ERP (Odoo)** como fuente de verdad y múltiples
**marketplaces** (MercadoLibre sandbox real + un mock de Paris), con
**outbox pattern**, **retry/DLQ**, **observabilidad** end-to-end y un
**MCP server** que deja a un agente IA trazar y resolver incidentes de
sincronización.

> El sistema no solo mueve órdenes: deja a Comercio Exterior preguntarle a un
> agente *"¿por qué la orden 12345 no llegó a MELI?"* y obtener el trace
> completo — y, con los permisos correctos, reintentar el envío.

## El escenario (un lunes con Comex)

> *Un lunes estás con Comercio Exterior viendo por qué las órdenes tardan en
> aparecer en marketplaces. El martes prototipas una integración con IA. El
> viernes presentas la solución a quien la pidió.*

Este repo **es ese escenario**, ejecutado end-to-end:

- Odoo es la fuente de verdad de las órdenes.
- Las órdenes deben aparecer en MercadoLibre y Paris.
- Los webhooks vuelven del marketplace y se reconcilian contra Odoo.
- Un **MCP server** con IAM por rol y audit log permite trazar y operar.
- Observabilidad (OTel + Grafana), DLQ, retry y bronze/silver/gold incluidos.

## Arquitectura

Diagrama fuente en [`docs/diagrams/architecture.mmd`](docs/diagrams/architecture.mmd).

```
Odoo ──outbox──▶ adapters ──▶ marketplaces ──webhooks──▶ receiver
                                                            │
                                                  Pub/Sub events ──▶ subscriber/reconciler ──▶ silver
                                                            │                                     │
                                                          DLQ                                  BigQuery (bronze/silver/gold + dbt)
                                                                                                  │
                                          Claude Code ◀──MCP──▶ MCP server (read/write · IAM · audit)
```

## Stack

Python 3.11 · uv · FastAPI · Pydantic v2 · SQLAlchemy/Alembic · Pub/Sub
(emulator → real) · BigQuery + dbt · FastMCP · OpenTelemetry + Grafana +
Prometheus + Tempo · Odoo 17 · Docker Compose.

Decisiones clave en [`adr/`](adr/).

## Quickstart

> Placeholder — el quickstart completo de 10 minutos llega en la Fase 11.
> Por ahora, para validar el repo:

```bash
uv sync --dev      # instala dependencias (Python 3.11 gestionado por uv)
make check         # ruff + mypy + pytest
```

Targets disponibles: `make help`.

## Estado del proyecto

Plan de ejecución por fases (V1, fases 0–11; V2 a GCP). Fase actual: **0 —
setup, ADRs y CI**.

| Fase | Descripción | Estado |
|---|---|---|
| 0 | Setup repo, ADRs, CI | 🟡 en curso |
| 1 | Odoo + Postgres + OTel collector | ⬜ |
| 2 | MercadoLibre OAuth + paris-mock | ⬜ |
| 3 | Webhook receiver + idempotencia + bronze | ⬜ |
| 4 | Adapter + outbox + outbound sync | ⬜ |
| 5 | Subscriber + reconciliación + silver | ⬜ |
| 6 | Observabilidad (OTel + Grafana) | ⬜ |
| 7 | BigQuery + dbt + gold | ⬜ |
| 8 | MCP read tools | ⬜ |
| 9 | MCP write tools + IAM + audit | ⬜ |
| 10 | Tests E2E + chaos | ⬜ |
| 11 | Docs + narrativa FDE + screencast | ⬜ |

## Licencia

MIT (ver `LICENSE`).
