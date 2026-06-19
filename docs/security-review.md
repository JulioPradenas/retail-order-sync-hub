# Security review checklist (V2)

Checklist de seguridad para el deployment productivo. Estado: lo implementado en
el repo vs. lo que queda como hardening recomendado.

## Autenticación y secretos

- [x] **Webhooks firmados (HMAC-SHA256).** Receiver rechaza con 401 toda request sin
  firma válida (`src/common/signing.py`). Comparación con `hmac.compare_digest`
  (constante en tiempo, resiste timing attacks).
- [x] **Secretos fuera del código.** V2 carga HMAC keys desde Secret Manager
  (`src/common/secrets.py`); nunca en el repo ni en la imagen Docker.
- [x] **`.env` gitignoreado**, solo `.env.example` con placeholders.
- [x] **Terraform no persiste secretos en state** — los contenedores se crean por IaC,
  los valores se agregan con `gcloud secrets versions add` fuera de Terraform.
- [ ] **Rotación automática de secretos** — V3: rotación programada + versionado.
- [x] **MCP IAM por scopes** — tokens con scopes (`orders.read`, `dlq.replay`,
  `dlq.admin`); cada tool exige su scope (`src/mcp_server/auth.py`).
- [ ] **JWT + Secret Manager para tokens MCP** — hoy tokens estáticos; V3.

## Privilegio mínimo (IAM)

- [x] **Dos service accounts separadas** (`webhook-receiver`, `subscriber-worker`),
  cada una con el mínimo rol necesario (`infra/terraform/iam.tf`).
- [x] **Receiver solo publica** al topic de events + lee sus 2 secrets; no toca DLQ.
- [x] **Worker solo consume** events/dlq + publica sync_dlq.
- [x] **Cloud Run como SA dedicada**, no la default de Compute.
- [ ] **VPC Service Controls** — fuera de alcance para portfolio.

## Superficie de red

- [x] **Solo el receiver es público.** Workers, DB y MCP corren sin ingress externo.
- [x] **Receiver público pero autenticado a nivel app** (HMAC), no a nivel IAM —
  los marketplaces no pueden firmar tokens GCP. Es la decisión correcta para webhooks.
- [x] **Contenedor non-root** (`infra/Dockerfile.webhook`, usuario `app`).
- [ ] **Imagen distroless / escaneo de vulnerabilidades** — `python:3.11-slim` está
  bien para portfolio; V3 podría usar distroless + Artifact Analysis.

## Datos e integridad

- [x] **Idempotencia en webhooks** — dedup con `(source, event_id)` + `ON CONFLICT
  DO NOTHING`. Un webhook replicado no produce doble efecto.
- [x] **Outbox transaccional** — el intento de sync es atómico con la escritura en Odoo.
- [x] **Audit log append-only** (`mcp_audit_log`) — toda operación write del MCP queda
  registrada con user, scope, params, resultado y latencia.
- [x] **Audit en transacción separada** — una falla de auditoría no interrumpe la
  operación; una falla de operación no impide el registro.

## CI/CD

- [x] **CI con lint + types + tests** en cada PR (`make check`, mypy strict).
- [x] **Cobertura enforced ≥85%** (`fail_under` en pyproject).
- [x] **Workload Identity Federation** para GitHub Actions → GCP (sin keys de SA
  en secrets del repo).
- [ ] **Firma de imágenes (cosign / binary authorization)** — V3.

## Pendientes priorizados para V3

1. Rotación automática de secretos HMAC.
2. JWT real + Secret Manager para tokens MCP.
3. Binary Authorization en Cloud Run.
4. Rate limiting en el receiver (defensa ante flood de webhooks).
