# Deploy a GCP (V2)

Guía para llevar el webhook receiver a Cloud Run y migrar a infra GCP real.
Todo el código y la IaC están **deploy-ready y verificados localmente**; esta guía
son los comandos que ejecutas tú con tu cuenta autenticada.

> **Nota sobre costos:** Cloud Run, Pub/Sub real y Secret Manager requieren una
> cuenta de billing activa (tarjeta asociada). Con uso de portfolio el costo real
> es ~$0–5/mes (Cloud Run con `minScale=0`). **BigQuery Sandbox** es la única
> pieza GCP que corre sin tarjeta — ver [V2.3](#v23--bigquery--dbt-scheduled).

---

## Prerequisitos (una vez)

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project "$PROJECT_ID"

# APIs necesarias
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  pubsub.googleapis.com \
  secretmanager.googleapis.com

# Artifact Registry para la imagen
gcloud artifacts repositories create rosh \
  --repository-format=docker --location="$REGION"
```

---

## V2.1 — Cloud Run (webhook receiver)

El receiver es el único servicio con URL pública (los marketplaces le hacen POST).

**Artefactos:**
- `infra/Dockerfile.webhook` — imagen productiva multi-stage, non-root, escucha `$PORT`.
- `infra/cloudrun/service.yaml` — spec Knative (`minScale=0`, secrets, service account).
- `infra/cloudrun/deploy.sh` — build + deploy en un comando.

**Verificación local (sin gastar):**
```bash
docker build -f infra/Dockerfile.webhook -t rosh-webhook:local .
docker run --rm -e PORT=8080 -p 8090:8080 rosh-webhook:local
curl http://localhost:8090/health   # 200 OK
```

**Deploy real:**
```bash
PROJECT_ID=mi-proyecto REGION=us-central1 ./infra/cloudrun/deploy.sh
```
El script imprime la URL (`https://webhook-receiver-xxx.run.app`). Regístrala en
la app sandbox de MercadoLibre como callback de webhooks.

---

## V2.2 — Pub/Sub real + IAM

Reemplaza el emulador local por Pub/Sub real con service accounts de permiso mínimo.

**Artefactos:** `infra/terraform/` (topics, subscriptions con dead-letter, 2 service accounts).

```bash
cd infra/terraform
terraform init
terraform plan  -var="project_id=$PROJECT_ID"
terraform apply -var="project_id=$PROJECT_ID"
```

El código no cambia: `google-cloud-pubsub` ya habla con emulador y real. En
producción quita `PUBSUB_EMULATOR_HOST` y deja `PUBSUB_PROJECT_ID=$PROJECT_ID`.

---

## V2.3 — BigQuery + dbt scheduled

**BigQuery Sandbox (sin tarjeta):**
1. Entra a https://console.cloud.google.com/bigquery — si no tienes billing,
   activa el modo Sandbox (banner azul).
2. Crea los datasets `bronze`, `silver`, `gold`.
3. `cp dbt/profiles.yml.template ~/.dbt/profiles.yml` y ajusta `project`.
4. `cd dbt && uv run dbt run && uv run dbt test`.

Limitaciones del sandbox: tablas expiran a 60 días, 1 TB query/mes, 10 GB storage.
Suficiente para el proyecto.

**dbt scheduled:** `.github/workflows/dbt-scheduled.yml` corre `dbt run && dbt test`
por cron. Requiere los secrets `GCP_WORKLOAD_IDENTITY_PROVIDER` y `GCP_SERVICE_ACCOUNT`
en el repo (mismo patrón que `dbt-docs.yml`).

**Cloud Trace:** apunta el exporter OTLP al endpoint de telemetría de GCP. Ver
`docs/observability.md` — es cambio de `OTEL_EXPORTER_OTLP_ENDPOINT`, no de código.

---

## Rollback

- Cloud Run: `gcloud run services update-traffic webhook-receiver --to-revisions=PREV=100`
- Pub/Sub: `terraform destroy` (cuidado: borra topics y mensajes en vuelo).
