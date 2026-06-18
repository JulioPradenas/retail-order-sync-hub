# ADR 005 — MCP server: Read + Write con IAM por rol y audit log

- **Status:** Accepted
- **Fecha:** 2026-06-17
- **Decisores:** Julio Pradenas

## Contexto

El diferenciador AI-native del proyecto es un **MCP server productivo** que deja
a un agente (Claude Desktop/Code) consultar trazabilidad y **operar** sobre el
sistema. El JD pide explícitamente **Seguridad e IAM**. Exponer escritura sin
control sería irresponsable.

## Opciones consideradas

- **A) Solo read tools** — seguro y simple, pero no demuestra IAM ni operación
  real; el agente queda como un dashboard de lectura.
- **B) Read + Write con IAM por rol y audit log inmutable** — el agente resuelve
  incidentes (replay DLQ, retry sync) bajo control de scopes y trazabilidad.
- **C) Write sin IAM** — descartado: inseguro y contrario al JD.

## Decisión

Adoptamos la **opción B**:

- **Read tools:** `get_order_status`, `trace_order`, `get_dlq_depth`,
  `get_sla_metrics`, `find_failed_orders`.
- **Write tools (admin scope):** `replay_dlq_message`, `retry_failed_sync`,
  `drain_dlq` (con `dry_run` por defecto).
- **IAM:** JWT con claim `scopes`; decorator `@requires_scope`. Roles `viewer`
  ⊂ `operator` ⊂ `admin`. V1 tokens estáticos; V2 vía Secret Manager.
- **Audit log:** tabla `mcp_audit_log` **append-only** (enforced a nivel DB),
  decorator `@audit` envuelve toda llamada write.

## Consecuencias

- (+) Demuestra IAM real + auditoría inmutable + operación AI-native segura.
- (+) `dry_run` y scopes acotan el blast radius de las tools de escritura.
- (−) Más superficie de seguridad que mantener y testear (403 + audit en cada
  denegación).
- (−) JWT estático en V1 no es production-grade; se documenta y se migra en V2.
