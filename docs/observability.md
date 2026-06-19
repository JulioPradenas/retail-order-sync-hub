# Observabilidad — ROSH (Phase 6)

## Arquitectura

```
Services (webhook_receiver, outbox_worker, subscriber, reconciler)
    │  OTLP/gRPC :4317
    ▼
OTel Collector
    ├── traces  → Tempo  :3200   (almacenamiento local)
    └── metrics → Prometheus :9090 (scrape :8889 cada 10 s)
                        │
                        ▼
                   Grafana :3000  (dashboards + alertas)
```

## Levantar el stack

```bash
# Stack principal primero
make up

# Stack de observabilidad (red compartida `rosh`)
make obs-up
```

Grafana estará en [http://localhost:3000](http://localhost:3000) (anónimo, rol Admin).

## Métricas de negocio

| Métrica | Tipo | Atributos | Descripción |
|---|---|---|---|
| `webhook_received_total` | Counter | `source`, `dedup_status` | Webhooks inbound (new / duplicate) |
| `order_sync_total` | Counter | `target_adapter`, `status` | Push outcomes (done / retry / dlq) |
| `order_sync_duration_seconds` | Histogram | `target_adapter`, `status` | Duración del push al marketplace |
| `outbox_pending` | Gauge | — | Entradas pendientes en outbox |
| `dlq_depth` | Gauge | — | Entradas en estado dlq |

## Auto-instrumentación

- **FastAPI** (`opentelemetry-instrumentation-fastapi`): spans HTTP server + `http_server_duration_milliseconds`
- **httpx** (`opentelemetry-instrumentation-httpx`): spans HTTP client + `http_client_duration_milliseconds`
- **SQLAlchemy** (`opentelemetry-instrumentation-sqlalchemy`): spans de queries DB

## Dashboards

| Dashboard | UID | Descripción |
|---|---|---|
| Comex Ops | `rosh-comex-ops` | Throughput webhooks, sync outcomes, DLQ, latencia push p50/p95/p99 |
| Pipeline Health | `rosh-pipeline-health` | OTel collector, HTTP auto-instr, targets Prometheus |

## Alertas Prometheus

Definidas en `infra/prometheus/alerts.yml`:

| Alerta | Expresión | Severidad |
|---|---|---|
| `DLQDepthHigh` | `dlq_depth > 10` por 1 min | warning |
| `OutboxBacklogHigh` | `outbox_pending > 50` por 5 min | warning |
| `SyncErrorRateHigh` | tasa dlq / total > 5% por 5 min | critical |

## Trazas

Tempo recibe spans via OTLP/gRPC. En Grafana → Explore → datasource Tempo, buscar por `service.name`:
- `rosh-webhook-receiver`
- `rosh-outbox-worker`
- `rosh-subscriber`
- `rosh-reconciler`

## Switch a Cloud Trace (V2.3)

El cambio de Tempo local a Cloud Trace es **solo config del collector** — los
servicios siguen enviando OTLP al collector sin cambiar nada.

1. Apunta el collector a `infra/otel-collector-config.gcp.yml` (usa el exporter
   `googlecloud` para trazas y `googlemanagedprometheus` para métricas):
   ```
   --config=/etc/otel-collector-config.gcp.yml
   ```
2. Define `GCP_PROJECT_ID` en el entorno del collector.
3. Auth via Application Default Credentials (service account del collector con
   `roles/cloudtrace.agent` y `roles/monitoring.metricWriter`).

Las trazas aparecen en la consola GCP → Trace; las métricas en Cloud Monitoring.
Requiere billing activo (no disponible en BigQuery Sandbox).
