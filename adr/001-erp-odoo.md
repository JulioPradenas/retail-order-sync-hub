# ADR 001 — ERP: Odoo 17 Community dockerizado

- **Status:** Accepted
- **Fecha:** 2026-06-17
- **Decisores:** Julio Pradenas

## Contexto

El proyecto necesita un ERP que actúe como **fuente de verdad** de catálogo,
clientes y órdenes. Debe ser real (no un stub), exponer una API programable y
correr local sin costos de licencia. El JD de The Brands Club menciona SAP B1
como ERP del entorno productivo.

## Opciones consideradas

- **A) Odoo 17 Community dockerizado** — ERP real, REST/XML-RPC + webhooks
  nativos, imagen oficial, gratis.
- **B) SAP B1** — el ERP del JD, pero sin tier gratuito ni imagen local viable
  para un portfolio.
- **C) ERP stub propio (FastAPI)** — control total, pero deja de ser "real" y
  pierde credibilidad en entrevista.

## Decisión

Usamos **Odoo 17 Community** vía la imagen oficial en Docker. Es un ERP de
verdad con API XML-RPC, lo que permite seed reproducible y polling de órdenes
confirmadas.

El mapeo conceptual a **SAP B1** (Service Layer + DI API) se documenta en
`docs/adapters.md` para conectar explícitamente con el stack del JD.

## Consecuencias

- (+) ERP real con API estable y datos reproducibles vía seed idempotente.
- (+) Webhooks/eventos nativos y modelo de datos rico (sale.order, res.partner).
- (−) Odoo es pesado en RAM; se mitiga con healthchecks y un solo nodo local.
- (−) El modelo Odoo difiere de SAP B1; se cubre con la capa adapter y docs.
