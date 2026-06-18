# MCP Server — Setup con Claude Desktop (Phase 8)

## Qué expone

El MCP server de ROSH provee 5 tools de lectura que Claude puede invocar para diagnosticar órdenes:

| Tool | Scope | Descripción |
|---|---|---|
| `get_order_status` | `orders.read` | Estado actual de una orden desde silver (Postgres) |
| `trace_order` | `orders.read` | Timeline cross-source: webhooks → outbox → silver + DLQ |
| `get_dlq_depth` | `metrics.read` | Cantidad de órdenes atascadas en DLQ |
| `get_sla_metrics` | `metrics.read` | p50/p95 de latencia de sync por marketplace (BigQuery gold) |
| `find_failed_orders` | `orders.read` | Órdenes sin sync exitoso en un período |

## Autenticación (V1 estático)

Tokens configurados via variable de entorno `MCP_STATIC_TOKENS`:

```
MCP_STATIC_TOKENS="dev-token:orders.read,metrics.read;admin-token:orders.read,metrics.read,dlq.admin"
```

Formato: `token:scope1,scope2;token2:scope3`. Cada tool recibe el parámetro `api_token`.

## Configurar Claude Desktop

Edita `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "retail-order-sync-hub": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/ruta/al/retail-order-sync-hub",
        "python",
        "-m",
        "src.mcp_server"
      ],
      "env": {
        "APP_DB_HOST": "localhost",
        "APP_DB_PORT": "5433",
        "APP_DB_USER": "rosh",
        "APP_DB_PASSWORD": "change-me",
        "APP_DB_NAME": "rosh",
        "BQ_PROJECT_ID": "retail-order-sync-hub",
        "MCP_STATIC_TOKENS": "dev-token:orders.read,metrics.read"
      }
    }
  }
}
```

Reemplaza `/ruta/al/retail-order-sync-hub` con la ruta real del proyecto.

## Demo: trazar una orden

Con el stack corriendo (`make up`) y Claude Desktop configurado:

> "¿Qué pasó con la orden 1? Usa api_token=dev-token"

Claude invocará `trace_order("1", api_token="dev-token")` y retornará el timeline completo: webhook recibido → enqueue en outbox → push al adapter → estado en silver.

Si la orden está en DLQ:

> "¿Cuántas órdenes hay en DLQ? Usa api_token=dev-token"

Claude invocará `get_dlq_depth(api_token="dev-token")`.

## Ejecutar localmente (sin Claude Desktop)

```bash
# Modo stdio (para Claude Desktop)
uv run python -m src.mcp_server

# Test manual con fastmcp CLI
uv run fastmcp dev src/mcp_server/server.py
```

## Roles definidos (Phase 9 los implementa completamente)

| Rol | Scopes |
|---|---|
| `viewer` | `orders.read`, `metrics.read` |
| `operator` | viewer + `outbox.retry`, `dlq.replay` |
| `admin` | operator + `dlq.admin` |
