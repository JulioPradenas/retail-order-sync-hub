# IAM — Scopes, Roles y Tokens MCP

## Modelo de acceso

El MCP server usa tokens estáticos configurados en la variable de entorno `MCP_STATIC_TOKENS`.
Formato: `"token1:scope_a,scope_b;token2:scope_c"`.

Cada llamada a una herramienta write pasa el token como `api_token` y el servidor verifica que el token tenga el scope requerido antes de ejecutar cualquier operación.

## Scopes disponibles

| Scope | Descripción |
|---|---|
| `orders.read` | Consultar estado y trazabilidad de órdenes |
| `metrics.read` | Consultar DLQ depth, SLA metrics, fallos |
| `outbox.retry` | Re-encolar órdenes con entradas DLQ/pending |
| `dlq.replay` | Resetear una entrada DLQ individual a pending |
| `dlq.admin` | Listar o limpiar en bulk todas las entradas DLQ |

## Roles predefinidos

Los roles son conjuntos de scopes convenientes para generar valores de token.

| Rol | Scopes |
|---|---|
| `viewer` | `orders.read`, `metrics.read` |
| `operator` | `orders.read`, `metrics.read`, `outbox.retry`, `dlq.replay` |
| `admin` | `orders.read`, `metrics.read`, `outbox.retry`, `dlq.replay`, `dlq.admin` |

Los roles no se configuran directamente — se listan aquí como referencia para construir el string de `MCP_STATIC_TOKENS`.

## Herramientas y sus scopes requeridos

| Herramienta MCP | Scope requerido | Tipo |
|---|---|---|
| `get_order_status` | `orders.read` | read |
| `trace_order` | `orders.read` | read |
| `get_dlq_depth` | `metrics.read` | read |
| `get_sla_metrics` | `metrics.read` | read |
| `find_failed_orders` | `metrics.read` | read |
| `replay_dlq_message` | `dlq.replay` | write, auditada |
| `retry_failed_sync` | `outbox.retry` | write, auditada |
| `drain_dlq` | `dlq.admin` | write, auditada |

## Configuración de ejemplo

```bash
# Desarrollo local — un token por rol
MCP_STATIC_TOKENS="dev-viewer:orders.read,metrics.read;dev-operator:orders.read,metrics.read,outbox.retry,dlq.replay;dev-admin:orders.read,metrics.read,outbox.retry,dlq.replay,dlq.admin"
```

En producción rotar los tokens vía Secret Manager e inyectarlos como variable de entorno en Cloud Run.

## Audit log

Todas las herramientas write registran cada llamada en la tabla `mcp_audit_log`:

| Campo | Tipo | Descripción |
|---|---|---|
| `user_id` | `text` | Prefijo del token (`token:<primeros 16 chars>`) |
| `tool_name` | `text` | Nombre de la herramienta sin prefijo `_` |
| `params_json` | `jsonb` | Parámetros de la llamada (sin `api_token`) |
| `scope_used` | `text` | Scope que se verificó |
| `result_status` | `text` | `ok`, `denied` o `error` |
| `error_message` | `text` | Mensaje de error si aplica |
| `latency_ms` | `integer` | Latencia de ejecución en ms |
| `created_at` | `timestamptz` | Timestamp UTC del registro |

El audit write corre en una transacción separada y nunca propaga excepciones al caller — una falla de escritura en audit no bloquea la operación principal.

### Consulta de ejemplo

```sql
SELECT
    created_at,
    user_id,
    tool_name,
    result_status,
    latency_ms,
    error_message
FROM mcp_audit_log
WHERE result_status IN ('denied', 'error')
ORDER BY created_at DESC
LIMIT 50;
```
