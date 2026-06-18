# Marketplace adapters

El sistema integra dos marketplaces detrás de una interfaz común
(`MarketplaceAdapter`, formalizada en Fase 4). Esto demuestra el **adapter
pattern**: el core no sabe si habla con MercadoLibre o con Paris.

| Aspecto | MercadoLibre (sandbox) | paris-mock |
|---|---|---|
| Auth | OAuth2 (authorization code + refresh) | API key (`X-API-Key`) |
| Token storage | `app_db.oauth_tokens` (auto-refresh) | — |
| Idempotencia (outbound) | `external_reference` en la orden | `external_ref` (dedupe en create) |
| Webhooks (inbound) | firmados por ML, validados en receiver | HMAC-SHA256 (`X-Paris-Signature`) |
| Modelo de datos | rico (items, payments, shipping) | mínimo (buyer + items + status) |
| Rate limits | sí (429 + `Retry-After`) → backoff | no (controlado por nosotros) |
| Control en tests | limitado (servicio externo) | total (admin endpoint dispara webhooks) |

## MercadoLibre

OAuth2 authorization-code flow real contra el sandbox.

```bash
# 1) crear app en https://developers.mercadolibre.com (modo sandbox)
# 2) completar ML_CLIENT_ID / ML_CLIENT_SECRET / ML_REDIRECT_URI en .env
# 3) correr el dance inicial:
uv run python -m src.adapters.mercadolibre auth
# 4) verificar:
uv run python -m src.adapters.mercadolibre get_user
```

- Los tokens (`access_token` + `refresh_token` + `expires_at`) se guardan en
  `app_db.oauth_tokens` (provider = `mercadolibre`).
- `valid_access_token()` refresca automáticamente cuando faltan
  `ML_REFRESH_SKEW_SECONDS` (default 300s) o menos para expirar.
- El `TokenStore` y el `httpx.AsyncClient` son inyectables → la lógica de
  refresh se testea sin DB ni red (ver `tests/unit/test_mercadolibre.py`).

## paris-mock

FastAPI con auth por `X-API-Key` y SQLite propio (no toca `app_db`).

```
GET  /health                                 sin auth
POST /orders                                 crea orden (idempotente por external_ref)
GET  /orders/{id}                            lee orden
POST /webhooks/register                      registra URL callback
POST /admin/orders/{id}/emit-webhook         dispara webhook firmado (para tests)
```

Los webhooks salientes se firman con HMAC-SHA256 sobre el body (header
`X-Paris-Signature`), usando `PARIS_API_SECRET`. El webhook receiver (Fase 3)
valida con la misma función (`src/common/signing.py`).

```bash
make up                       # levanta paris_mock en :9100
curl -H "X-API-Key: $PARIS_API_KEY" -X POST localhost:9100/orders \
  -H 'Content-Type: application/json' \
  -d '{"buyer":"Comex","items":[{"sku":"ROSH-TSHIRT-001","qty":2}]}'
```

## Mapeo conceptual a SAP B1

El entorno productivo del rol usa **SAP Business One**. El mismo patrón aplica:

- **Service Layer** (REST/OData) ↔ los endpoints REST de los marketplaces:
  crear/leer órdenes, actualizar stock. El adapter traduce el modelo interno al
  payload de cada backend igual que traduciría a un `BusinessPartners` /
  `Orders` de SAP B1.
- **DI API** (operaciones transaccionales) ↔ el outbox + reintentos (Fase 4):
  garantiza entrega exactly-once-ish con idempotencia, como se haría envolviendo
  llamadas DI API en una unidad transaccional.
- **Auth**: SAP B1 Service Layer usa login por sesión (cookie `B1SESSION`); ML
  usa OAuth2 y Paris API key. El adapter aísla esa diferencia: el core nunca ve
  el mecanismo de auth.
