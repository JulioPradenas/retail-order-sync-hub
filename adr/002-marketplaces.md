# ADR 002 — Marketplaces: MercadoLibre sandbox + paris-mock

- **Status:** Accepted
- **Fecha:** 2026-06-17
- **Decisores:** Julio Pradenas

## Contexto

Las órdenes de Odoo deben aparecer en marketplaces. Queremos demostrar
**OAuth2 real productivo** y, a la vez, el **patrón adapter** que abstrae
múltiples integraciones detrás de una interfaz común.

## Opciones consideradas

- **A) Dos marketplaces reales** — máxima fidelidad, pero duplica el costo de
  credenciales/aprobaciones y bloquea el desarrollo en gates externos.
- **B) MercadoLibre sandbox (OAuth2 real) + `paris-mock` (FastAPI, API key)** —
  un integration real con OAuth productivo y un segundo controlado que ejercita
  el adapter pattern, idempotencia y disparo manual de webhooks en tests.
- **C) Dos mocks** — barato pero sin OAuth real; pierde el punto fuerte.

## Decisión

Adoptamos la **opción B**:

- **MercadoLibre sandbox** con Authorization Code flow real, almacenamiento de
  `access_token`/`refresh_token` en `app_db` y auto-refresh.
- **`paris-mock`**: FastAPI con auth por `X-API-Key`, persistencia SQLite
  propia y un endpoint admin para disparar webhooks (clave para tests E2E).

Ambos implementan el `Protocol` `MarketplaceAdapter` (`push_order`,
`update_stock`, `get_order_status`).

## Consecuencias

- (+) OAuth2 real demostrable + adapter pattern con dos backends distintos.
- (+) `paris-mock` controlable habilita chaos testing (timeouts, 429, payloads
  corruptos) sin depender de un tercero.
- (−) Mantener un mock es trabajo extra; se acota a lo necesario para el flujo.
- (−) El sandbox de ML puede cambiar; se aísla tras el adapter.
