# ADR 003 — Message broker: Pub/Sub emulator (V1) → Pub/Sub real (V2)

- **Status:** Accepted
- **Fecha:** 2026-06-17
- **Decisores:** Julio Pradenas

## Contexto

El flujo de eventos (webhooks entrantes, sync saliente) necesita mensajería
asíncrona con **retry y DLQ**. El JD de The Brands Club nombra explícitamente
**Pub/Sub**.

## Opciones consideradas

- **A) Google Pub/Sub** (emulator local en V1, real en V2) — nombrado en el JD,
  mismo cliente `google-cloud-pubsub` contra emulator y producción.
- **B) RabbitMQ / Redis Streams** — válidos, pero no mapean al JD.
- **C) Kafka** — sobredimensionado para el volumen del proyecto.

## Decisión

Usamos **Google Pub/Sub**:

- **V1:** Pub/Sub **emulator** (`cloud-sdk:emulators`) en docker-compose. Mismo
  SDK que producción; sin costo.
- **V2:** Pub/Sub **real** en GCP, con service accounts de permisos mínimos y
  políticas de retry/dead-letter a nivel GCP.

Topics: `marketplace.events`, `marketplace.sync.dlq`, `marketplace.dlq`.

## Consecuencias

- (+) Cero cambios de código emulator → real (solo config/endpoint).
- (+) DLQ y retry de primera clase, alineados al JD.
- (−) El emulator no replica 100% el comportamiento de IAM/cuotas; se valida en
  V2 contra Pub/Sub real.
