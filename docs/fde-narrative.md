# Narrativa FDE — Retail Order Sync Hub

Este documento explica el **por qué** detrás de las decisiones técnicas, y cómo el proyecto demuestra el trabajo de un Forward Deployed Engineer.

---

## El problema real

El brief original: *"Integrar Odoo con MercadoLibre y Paris para que las órdenes se sincronicen automáticamente."*

El problema real, que emerge en la primera semana con el equipo de Comercio Exterior:

1. **Visibilidad cero.** Cuando una orden no aparece en el marketplace, nadie sabe si el problema está en Odoo, en la red, en el adapter, o en el webhook de respuesta. Soporte abre un ticket. IT revisa logs manualmente. La orden se retrasa dos días.

2. **Fiabilidad no negociable.** Los marketplaces cobran penalidades por órdenes no sincronizadas dentro de un SLA. Un timeout de red no puede ser motivo de pérdida de venta.

3. **Operabilidad sin IT.** El equipo de Comex no puede depender de IT para saber si una orden se envió. Necesitan un canal directo.

El sistema resultante no es solo una integración — es la respuesta a esas tres preguntas.

---

## Decisiones arquitectónicas y su motivación

### 1. Outbox pattern en lugar de llamadas síncronas al adapter

**Alternativa descartada:** llamar directamente al adapter de MercadoLibre en el mismo request que confirma la orden en Odoo.

**Problema:** si MercadoLibre tarda 5 segundos o devuelve 503, la transacción de Odoo queda en limbo. El operador no sabe si la orden se procesó o no.

**Decisión:** escribir la orden en `outbox` dentro de la misma transacción Postgres que la actualiza en Odoo. El outbox worker lee y envía en background, con retry y backoff exponencial.

**Garantía concreta:** si Postgres acepta la transacción, la orden **va a ser enviada** eventualmente. El outbox es la única fuente de verdad del intento de sync.

**Implementación clave:** `ON CONFLICT DO NOTHING + RETURNING` para que re-encolar la misma orden sea un no-op. Un adapter que falla 4 veces llega al DLQ — no bloquea el resto de la cola.

---

### 2. DLQ como herramienta de operación, no de descarte

**Patrón común:** el DLQ es el cementerio de los mensajes que fallaron.

**Decisión:** el DLQ es la entrada del MCP server. Cuando una orden llega al DLQ, el agente puede:

- Trazar por qué falló (`trace_order` → outbox entries → error_log).
- Reintentar el envío con un solo comando (`replay_dlq_message`).
- Limpiar en bulk el DLQ después de un incidente resuelto (`drain_dlq`, siempre con `dry_run=True` por default).

El DLQ deja de ser un lugar donde las cosas mueren y se convierte en **una cola de trabajo para el agente**.

---

### 3. Idempotencia en webhooks: no es opcional

Los marketplaces garantizan entrega *at-least-once*. El mismo webhook puede llegar dos veces.

**Decisión:** `WebhookDedup` con `(source, event_id)` únicos y `ON CONFLICT DO NOTHING + RETURNING`. Si la fila no se creó, es duplicado y no se escribe bronze. Un webhook duplicado es invisible para el sistema.

**Por qué importa:** sin esto, un webhook duplicado genera dos filas en bronze, dos normalizaciones en silver, y potencialmente dos actualizaciones en Odoo. El reconciliador detectaría drift y sobrescribiría — pero la trazabilidad quedaría sucia.

---

### 4. Bronze / Silver / Gold en BigQuery

**Alternativa descartada:** analytics directo sobre Postgres operacional.

**Problema:** los queries analíticos (latencia p95, throughput diario, root causes de DLQ) compiten con las escrituras transaccionales. Además, Postgres no escala bien para queries ad-hoc sobre millones de filas.

**Decisión:** sync watermark-based a BigQuery (bronze = raw, silver = normalizado deduplicado, gold = SLA/KPIs calculados con dbt). Los modelos gold son los que alimentan `get_sla_metrics` del MCP server.

**Invariante de los modelos dbt:** contratos de schema enforced (`contract: enforced: true`) y tests singulares que garantizan que `p50_sync_seconds >= 0`. Si el modelo falla el contrato, el CI de dbt-docs no despliega.

---

### 5. MCP server: el puente entre el sistema y el operador

El MCP server no es un chatbot. Es una **API con semántica de dominio** que Claude puede llamar.

La distinción importa porque:

- Un API REST genérico obliga al agente a entender la estructura de las tablas para formular una consulta útil.
- Las herramientas MCP tienen descripciones que incluyen el contexto de negocio: cuándo usar `trace_order` vs `find_failed_orders`, qué significa cada campo.

**IAM por scope, no por servicio.** El scope `dlq.replay` permite reintentar una entrada específica. El scope `dlq.admin` permite vaciar el DLQ completo. Un operador de turno tiene el primero; solo el ingeniero de guardia tiene el segundo.

**Audit log en transacción separada.** Si la operación de negocio falla, el registro de auditoría igual se escribe. Si el audit falla, la operación no se interrumpe. Esta garantía se diseñó explícitamente: el `try/except Exception: pass` en `_write_audit` es la implementación de ese contrato.

---

### 6. Observabilidad antes que features

Las métricas y trazas se implementaron en la Fase 6 — antes de BigQuery, antes del MCP server.

**Motivación:** sin saber cuántos webhooks entran, cuántos outbox entries llegan al DLQ, y cuál es la latencia p95 del adapter de MercadoLibre, no hay forma de saber si el sistema funciona. Los dashboards de Grafana son la primera herramienta que usa Comex cuando algo no cuadra.

**Decisión de instrumentación:** OpenTelemetry como capa de abstracción (no vendor lock-in), con exportación OTLP gRPC al Collector. El Collector decide el destino (Prometheus para métricas, Tempo para traces). Cambiar de Tempo a Jaeger es editar el compose, no el código.

---

## Qué hace que esto sea un proyecto FDE y no un tutorial

### Priorización bajo incertidumbre

Las fases 0–4 (setup, Odoo, adapters, outbox) son la base. Las fases 5–11 responden a necesidades que surgieron al construir las primeras:

- La reconciliación (fase 5) surgió de preguntarse "¿qué pasa si el webhook llega pero la orden en Odoo no se actualiza?"
- El MCP server (fases 8–9) surgió de preguntarse "¿cómo puede un operador no-técnico diagnosticar un incidente a las 2am?"
- Los tests de chaos (fase 10) surgieron de preguntarse "¿qué pasa si el publisher de Pub/Sub falla justo cuando una entrada llega al DLQ?"

Cada fase respondió una pregunta concreta, no un ítem de una checklist.

### Decisiones que no se tomaron

- **No se usó Kafka.** Pub/Sub es suficiente para el volumen de un retailer mediano y tiene un emulador local que hace el desarrollo local reproducible sin Zookeeper.
- **No se usó Airflow para dbt.** El sync watermark-based con un cron o Cloud Scheduler es suficiente para el caso de uso. Airflow es complejidad operacional que no se justifica hasta que los DAGs son complejos.
- **No se usó JWT en el MCP server.** Los tokens estáticos con scopes son suficientes para V1. El diseño de la función `_token_scopes()` con `@lru_cache` hace trivial cambiar a Secret Manager en V2 sin tocar los tests de herramientas.
- **No se usó async en el subscriber.** El subscriber es I/O bound (Pub/Sub + Postgres) pero el volumen no justifica la complejidad de asyncio. Si el throughput escala, la migración es aislada a ese módulo.

### El stack de tests como contrato

141 tests unitarios + 6 de integración + `fail_under = 85` en CI. Los tests de chaos prueban condiciones que el stack de integración no puede reproducir fácilmente:

- Adapter que falla justo al llegar a `max_attempts` → DLQ entry.
- Publisher de Pub/Sub que falla durante la publicación del DLQ → excepción propagada (comportamiento explícito, no silenciado).
- `_write_audit` que falla al escribir en Postgres → la excepción se traga, la operación de negocio continúa.

Cada uno de esos tests documenta una decisión de diseño que no está en los comentarios del código.

---

## Cómo leer el repo en una entrevista

**Si tienes 5 minutos:** lee `src/mcp_server/server.py` y `src/outbox_worker/processor.py`. Ahí está el núcleo del valor: el puente entre el sistema operacional y el agente, y el mecanismo que garantiza entrega confiable.

**Si tienes 15 minutos:** suma `src/mcp_server/audit.py` y `src/common/db.py`. Las decisiones de diseño no obvias (transacción separada para el audit, el `try/except` que swallows intencionalmente) están ahí.

**Si tienes 30 minutos:** lee los ADRs en `adr/` y los modelos dbt en `dbt/models/gold/`. Los ADRs explican el contexto de las decisiones; el gold layer muestra qué KPIs importan al negocio.

---

## V2 — qué haría diferente con más tiempo

| Área | Mejora |
|---|---|
| Auth MCP | JWT + Secret Manager para rotación automática de tokens |
| Outbox | Particionado por `target_adapter` para paralelismo sin lock contention |
| BigQuery sync | Cloud Scheduler + Cloud Run en lugar de cron local |
| MercadoLibre | Token refresh con refresh_token → actualmente usa access_token de sandbox |
| Chaos tests | Testcontainers para levantar Postgres real en CI sin Docker Compose |
| dbt | Exposures para conectar los modelos gold con los dashboards de Grafana |
