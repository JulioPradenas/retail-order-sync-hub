# Análisis de costos GCP (V2)

Objetivo de diseño: mantener el deployment de portfolio **bajo $10/mes**, idealmente
cerca de $0. Las decisiones de arquitectura (scale-to-zero, batch, sandbox) están
tomadas con el costo como restricción explícita.

## Resumen

| Servicio | Uso portfolio | Free tier | Costo estimado/mes |
|---|---|---|---|
| Cloud Run (webhook receiver) | tráfico esporádico, `minScale=0` | 2M requests, 360k GB-s | **$0** |
| Pub/Sub | < 1 GB mensajes/mes | 10 GB/mes | **$0** |
| Secret Manager | 2 secrets, pocos accesos | 6 versiones activas + 10k accesos | **$0** |
| Artifact Registry | 1 imagen ~150 MB | 0.5 GB | **$0** |
| Cloud Build | < 20 builds/mes | 120 build-min/día | **$0** |
| BigQuery (Sandbox) | < 1 GB storage, < 10 GB query | 10 GB storage + 1 TB query | **$0** |
| Cloud Trace | < 2.5M spans/mes | 2.5M spans | **$0** |
| Cloud Monitoring | métricas básicas | primeras métricas gratis | **$0** |
| **Total** | | | **~$0–3/mes** |

## Dónde está el riesgo real de costo

1. **Cloud Run con `minScale > 0`.** Mantener una instancia caliente cuesta ~$15/mes.
   Por eso el `service.yaml` fuerza `minScale=0`: se paga solo cuando llega un webhook.
   El trade-off es cold start (~1-2s en la primera request tras inactividad), aceptable
   para webhooks de marketplace.

2. **BigQuery query scanning.** El cobro es por bytes escaneados, no por filas. Una query
   mal hecha (`SELECT *` sobre tablas grandes sin partición) puede quemar el free tier.
   Mitigación: los modelos gold están particionados por fecha y las queries del MCP
   (`get_sla_metrics`) filtran por ventana temporal.

3. **Pub/Sub retención.** Mensajes no consumidos retienen storage. El dead-letter topic
   tiene su propia subscription (`marketplace.dlq.sub`) que el MCP drena, evitando
   acumulación indefinida.

## Decisiones de arquitectura motivadas por costo

| Decisión | Alternativa más cara | Ahorro |
|---|---|---|
| Cloud Run scale-to-zero | GKE / Compute Engine 24/7 | ~$50/mes |
| BigQuery Sandbox | BigQuery con billing + slots reservados | ~$20/mes mínimo |
| Batch sync a BQ (watermark) | Streaming inserts | $0.05/GB streaming evitado |
| Solo el receiver en Cloud Run | Todos los workers en la nube | ~$60/mes |
| Pub/Sub emulator en dev/CI | Pub/Sub real en cada test | quota + latencia |

## Cómo monitorear el gasto

```bash
# Budget alert a $5 (requiere billing account)
gcloud billing budgets create \
  --billing-account="$BILLING_ACCOUNT" \
  --display-name="rosh-portfolio-budget" \
  --budget-amount=5USD \
  --threshold-rule=percent=0.5 \
  --threshold-rule=percent=0.9
```

Sin tarjeta (BigQuery Sandbox), el gasto es estructuralmente imposible: GCP rechaza
cualquier operación que requiera billing.
