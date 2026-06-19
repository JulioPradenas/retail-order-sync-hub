# Retail Order Sync Hub — ERP ↔ Marketplaces

[![CI](https://github.com/JulioPradenas/retail-order-sync-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/JulioPradenas/retail-order-sync-hub/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11-blue)
![Coverage](https://img.shields.io/badge/coverage-85%25-brightgreen)
![Status](https://img.shields.io/badge/status-complete-success)

Sistema de sincronización de órdenes entre **Odoo ERP** y múltiples **marketplaces** (MercadoLibre sandbox + paris-mock), construido con outbox pattern, DLQ, observabilidad end-to-end y un **MCP server** que permite a un agente IA trazar y operar incidentes de sincronización.

> "¿Por qué la orden ML-98345 no apareció en MELI?" → El agente responde con el trace completo y puede reintentar el envío con los permisos correctos.

---

## El escenario

Un lunes con el equipo de Comercio Exterior:

- Las órdenes en Odoo no aparecen en los marketplaces.
- Los webhooks llegan pero nadie sabe si se procesaron.
- El equipo de soporte no tiene visibilidad — necesita abrir un ticket a IT.

Este repo resuelve ese escenario **end-to-end**:

1. Odoo como fuente de verdad de órdenes.
2. Sync confiable a MercadoLibre y Paris con retry exponencial y DLQ.
3. Webhooks idempotentes con deduplicación y firma HMAC.
4. Bronze/Silver/Gold en BigQuery para analytics (dbt).
5. Observabilidad con OpenTelemetry, Grafana y alertas.
6. MCP server con IAM por scope y audit log — el agente puede responder y actuar.

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Retail Order Sync Hub                             │
│                                                                             │
│  ┌─────────┐   outbox   ┌──────────────┐    ┌────────────┐                │
│  │  Odoo   │──pattern──▶│ Outbox Worker│───▶│ Adapters   │──▶ MercadoLibre│
│  │  (ERP)  │            │  retry/DLQ   │    │ ML · Paris │──▶ paris-mock  │
│  └─────────┘            └──────────────┘    └────────────┘                │
│       ▲                        │                   │                       │
│       │                   sync.dlq            webhooks                     │
│  reconcile              (Pub/Sub)           (signed · idempotent)         │
│       │                                           │                        │
│  ┌────┴────────────┐                    ┌─────────▼──────┐                │
│  │ Subscriber +    │◀── marketplace ────│ Webhook         │               │
│  │ Reconciler      │      .events       │ Receiver        │               │
│  │ (silver orders) │    (Pub/Sub)       │ (bronze · dedup)│               │
│  └────────┬────────┘                    └────────┬────────┘               │
│           │                                      │                         │
│     ┌─────▼──────────────────────────────────────▼──────┐                 │
│     │                   BigQuery                         │                 │
│     │   bronze (raw) → silver (clean) → gold (SLA/KPIs) │                 │
│     │   dbt models · contracts · singular tests          │                 │
│     └─────────────────────────┬──────────────────────────┘                │
│                               │                                            │
│  ┌────────────────────────────▼──────────────────────────┐                │
│  │                    MCP Server                          │                │
│  │  get_order_status · trace_order · get_dlq_depth        │                │
│  │  get_sla_metrics · find_failed_orders                  │                │
│  │  replay_dlq_message · retry_failed_sync · drain_dlq    │                │
│  │  IAM (scopes: orders.read / dlq.replay / dlq.admin)    │                │
│  │  Audit log (mcp_audit_log, transacción separada)       │                │
│  └────────────────────────────▲──────────────────────────┘                │
│                               │ MCP protocol (stdio)                       │
│                          Claude Code / Desktop                             │
│                                                                            │
│  ┌──────────────────────────────────────────────────────┐                 │
│  │  Observabilidad: OTel Collector → Prometheus + Tempo  │                │
│  │  Grafana: Comex Ops dashboard · Pipeline Health       │                │
│  └──────────────────────────────────────────────────────┘                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

Diagrama Mermaid completo: [`docs/diagrams/architecture.mmd`](docs/diagrams/architecture.mmd)

---

## Stack

| Capa | Tecnología |
|---|---|
| Runtime | Python 3.11, uv, ruff, mypy strict |
| API | FastAPI + Pydantic v2 |
| DB | PostgreSQL (psycopg3) + SQLAlchemy 2.x + Alembic |
| Broker | Google Cloud Pub/Sub (emulator local, real en GCP) |
| Outbox | Patrón outbox con `ON CONFLICT DO NOTHING + RETURNING` |
| DLQ | Pub/Sub topic `marketplace.sync.dlq` |
| Analytics | BigQuery + dbt (bronze/silver/gold, contratos, tests singulares) |
| AI | FastMCP 2.x, stdio transport, MCP_STATIC_TOKENS IAM |
| Observabilidad | OpenTelemetry SDK + Collector → Prometheus + Tempo → Grafana |
| Infra local | Docker Compose (stack + obs stack separados) |
| CI | GitHub Actions (ruff + mypy + pytest, coverage ≥ 85%) |

---

## Quickstart (10 minutos)

### Prerequisitos

- Docker Desktop
- Python 3.11 (`uv` lo gestiona automáticamente)
- `uv` instalado: `curl -LsSf https://astral.sh/uv/install.sh | sh`

### 1. Clonar e instalar

```bash
git clone https://github.com/JulioPradenas/retail-order-sync-hub.git
cd retail-order-sync-hub
uv sync --dev
```

### 2. Levantar el stack

```bash
make up         # Odoo, Postgres, Pub/Sub emulator, paris-mock
make migrate    # aplica migraciones Alembic
make seed       # carga órdenes demo en Odoo
```

El primer `make up` descarga ~2 GB de imágenes. Odoo tarda ~60 s en iniciar.

### 3. Verificar

```bash
# Check de código + tests (85%+ cobertura)
make check

# Odoo disponible en
open http://localhost:8069  # admin / admin

# Paris-mock en
curl http://localhost:9100/orders -H "X-API-Key: change-me"

# Webhook receiver
curl http://localhost:8000/health
```

### 4. Observabilidad (opcional)

```bash
make obs-up     # Grafana + Prometheus + Tempo + OTel Collector
open http://localhost:3000  # Grafana — admin / admin
```

Dashboards disponibles:
- **Comex Ops** — webhook throughput, sync outcomes, DLQ depth, latencia p95
- **Pipeline Health** — OTel spans, FastAPI requests, Prometheus targets

### 5. Tests de integración

```bash
make up && make migrate
ROSH_INTEGRATION=1 uv run pytest -m integration -v
```

### 6. BigQuery + dbt (requiere GCP)

```bash
cp dbt/profiles.yml.template ~/.dbt/profiles.yml
# Edita con tu project_id y credenciales
cd dbt && uv run dbt run && uv run dbt test
```

---

## MCP Server — Claude como operador de turno

El MCP server expone 8 herramientas a Claude Code o Claude Desktop para trazar y operar incidentes de sincronización.

### Configuración (Claude Desktop)

```json
{
  "mcpServers": {
    "retail-order-sync-hub": {
      "command": "uv",
      "args": ["run", "python", "-m", "src.mcp_server"],
      "cwd": "/ruta/al/retail-order-sync-hub",
      "env": {
        "MCP_STATIC_TOKENS": "mi-token:orders.read,metrics.read,outbox.retry,dlq.replay",
        "APP_DB_HOST": "localhost",
        "APP_DB_PORT": "5433"
      }
    }
  }
}
```

Guía completa: [`docs/mcp-setup.md`](docs/mcp-setup.md)

### Herramientas disponibles

| Herramienta | Scope requerido | Descripción |
|---|---|---|
| `get_order_status` | `orders.read` | Estado actual de una orden en Postgres silver |
| `trace_order` | `orders.read` | Timeline completa: webhooks → outbox → silver |
| `get_dlq_depth` | `metrics.read` | Cantidad de órdenes en DLQ |
| `get_sla_metrics` | `metrics.read` | p50/p95 de latencia de sync desde BigQuery gold |
| `find_failed_orders` | `metrics.read` | Órdenes sin sync en un período |
| `replay_dlq_message` | `dlq.replay` | Resetea una entrada DLQ a pending (auditado) |
| `retry_failed_sync` | `outbox.retry` | Re-encola todas las entradas DLQ de una orden (auditado) |
| `drain_dlq` | `dlq.admin` | Lista o limpia en bulk el DLQ (dry_run por default, auditado) |

### Demo prompts

```
¿Por qué la orden ML-12345 no llegó a MercadoLibre?
trace_order("ML-12345")
```

```
¿Cuántas órdenes están bloqueadas en DLQ en este momento?
get_dlq_depth()
```

```
Hay 3 órdenes atascadas — reintentar todas con retry
retry_failed_sync("12345")
```

---

## IAM y scopes

Tres roles predefinidos para configurar tokens:

| Rol | Scopes |
|---|---|
| viewer | `orders.read`, `metrics.read` |
| operator | + `outbox.retry`, `dlq.replay` |
| admin | + `dlq.admin` |

Cada operación write queda registrada en `mcp_audit_log` con user_id, scope, params, resultado y latencia. Referencia completa: [`docs/iam.md`](docs/iam.md)

---

## Documentación

| Documento | Contenido |
|---|---|
| [`docs/iam.md`](docs/iam.md) | Scopes, roles, tokens, audit log |
| [`docs/mcp-setup.md`](docs/mcp-setup.md) | Configuración Claude Desktop, demo prompts |
| [`docs/observability.md`](docs/observability.md) | Stack OTel, catálogo de métricas, dashboards |
| [`docs/adapters.md`](docs/adapters.md) | Contratos de adapters, retry policy |
| [`docs/fde-narrative.md`](docs/fde-narrative.md) | Narrativa FDE: decisiones, trade-offs, contexto |
| [`docs/deploy-gcp.md`](docs/deploy-gcp.md) | Deploy a GCP (Cloud Run, Pub/Sub, BigQuery Sandbox) |
| [`docs/cost-analysis.md`](docs/cost-analysis.md) | Análisis de costos GCP (objetivo <$10/mes) |
| [`docs/security-review.md`](docs/security-review.md) | Security review checklist |
| [`docs/blog/design-decisions.md`](docs/blog/design-decisions.md) | Outbox vs CDC, idempotencia, IAM del MCP |
| [`adr/`](adr/) | Architecture Decision Records (5 ADRs) |
| [`dbt/`](dbt/) | Modelos dbt, contratos de schema, tests singulares |

---

## Estructura del repo

```
src/
  adapters/          # Paris + MercadoLibre adapters (Protocol-based)
  bq_sync/           # BigQuery watermark sync (bronze)
  common/            # Config, DB, models, logging, OTel, signing
  mcp_server/        # FastMCP server (read + write tools, IAM, audit)
  outbox_worker/     # Outbox processor con retry exponencial + DLQ
  paris_mock/        # Mock del marketplace Paris (FastAPI)
  reconciler/        # Reconciliación silver → Odoo
  subscriber/        # Pub/Sub subscriber → normalize → silver
  webhook_receiver/  # Inbound webhooks (HMAC, dedupe, bronze)
infra/
  docker-compose.yml        # Stack operacional
  docker-compose.obs.yml    # Stack de observabilidad
  grafana/                  # Dashboards y datasources
dbt/                        # Modelos bronze/silver/gold + contratos
migrations/                 # Alembic migrations
tests/
  unit/              # 141 tests unitarios (85%+ cobertura)
  integration/       # Tests contra el stack real (ROSH_INTEGRATION=1)
docs/
adr/
```

---

## Fases completadas

| Fase | Descripción | PR |
|---|---|---|
| 0 | Setup repo, ADRs, CI | #1 |
| 1 | Odoo + Postgres + OTel collector | #2 |
| 2 | MercadoLibre OAuth + paris-mock | #3 |
| 3 | Webhook receiver + idempotencia + bronze | #4 |
| 4 | Adapter + outbox + outbound sync | #5 |
| 5 | Subscriber + reconciliación + silver | #6 |
| 6 | Observabilidad (OTel + Grafana) | #7 |
| 7 | BigQuery + dbt + gold | #8 |
| 8 | MCP read tools + IAM estático | #9 |
| 9 | MCP write tools + audit log | #10 |
| 10 | Tests unitarios + chaos (85% coverage) | #11 |
| 11 | Docs + narrativa FDE | #12 |

### V2 — GCP productivo (deploy-ready)

Artefactos de despliegue listos y verificados localmente. El deploy en vivo es un
comando con cuenta GCP autenticada (ver [`docs/deploy-gcp.md`](docs/deploy-gcp.md)).

| Sub-fase | Descripción | PR | Verificación local |
|---|---|---|---|
| V2.1 | Cloud Run: Dockerfile productivo + Secret Manager | #15 | `docker build` + contenedor honra `PORT` + `/health` 200 |
| V2.2 | Pub/Sub real + IAM least-privilege (Terraform) | #16 | `terraform validate` → Success |
| V2.3 | dbt scheduled (cron) + switch a Cloud Trace | #17 | YAML válido, `make check` |
| V2.4 | Cost analysis + security review + blog técnico | #18 | docs |

BigQuery Sandbox corre sin tarjeta; Cloud Run / Pub/Sub / Secret Manager requieren
billing activo.

---

## Licencia

MIT
