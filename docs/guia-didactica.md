# Guía didáctica — Retail Order Sync Hub

Para entender el proyecto de punta a punta: de la pregunta de negocio al porqué de
cada decisión técnica, y qué mirar para contar la historia. Léela una vez antes de
una entrevista o de una demo.

---

## 1. La pregunta de negocio (por qué existe esto)

Un retailer vende en su ERP (Odoo) y también en marketplaces (MercadoLibre, Paris).
Cuando una orden se confirma en el ERP, **tiene que aparecer en el marketplace**. Si no
aparece, hay penalidades y ventas perdidas.

El dolor real no es "conectar dos APIs". Son tres preguntas que nadie podía responder:

1. **¿Apareció la orden en el marketplace?** Nadie tenía visibilidad.
2. **¿Y si el marketplace está caído justo ahora?** No había garantía de reintento.
3. **¿Por qué la orden X no llegó?** Solo IT podía investigar, leyendo logs a mano.

**El proyecto es la respuesta a esas tres preguntas.** No es una integración: es un
sistema confiable, observable y operable — incluso por un agente IA.

> Frase de una línea: *"Odoo es la fuente de verdad; el sistema garantiza que cada
> orden se refleje en los marketplaces de forma confiable, lo muestra en dashboards,
> y deja que un agente IA trace y resuelva incidentes."*

---

## 2. Por qué la arquitectura tiene ESTA forma

La arquitectura sigue el viaje de una orden. Cada "salto" resuelve un problema concreto:

```
Odoo → [outbox] → adapters → marketplace → [webhook] → subscriber → silver
                     │                                                  │
                  falla→DLQ                                       BigQuery (dbt)
                                                                        │
                                                              MCP server (agente IA)
                                                                        │
                                                              Observabilidad (Grafana)
```

| Salto | Problema que resuelve | Decisión | Por qué esa y no otra |
|---|---|---|---|
| Odoo → outbox | "¿se intentó sincronizar?" | **Outbox pattern** | La fila se escribe en la MISMA transacción que la orden. Si la orden existe, el sync va a ocurrir. CDC (Debezium) era demasiada infra para el volumen. |
| outbox → marketplace | el marketplace puede fallar | **Retry + DLQ** | Backoff exponencial; tras N intentos va al Dead Letter Queue, no se pierde ni bloquea la cola. |
| marketplace → webhook | confirmar qué pasó allá | **Webhook receiver + HMAC** | Valida firma (seguridad) y deduplica (los webhooks llegan *at-least-once*). |
| webhook → silver | normalizar y reflejar estado | **Subscriber + reconciler** | Subscriber actualiza la tabla `orders`; reconciler es la red de seguridad que detecta drift. |
| silver → BigQuery | analytics sin frenar la operación | **Bronze/silver/gold + dbt** | Separar lo operacional (Postgres) de lo analítico (BigQuery). Queries pesadas no compiten con escrituras. |
| BigQuery → agente | operar sin depender de IT | **MCP server + IAM** | Claude puede trazar y reparar órdenes, con permisos por scope y audit log. |
| todo → Grafana | "¿está sano el sistema?" | **OpenTelemetry → Grafana** | Métricas y trazas en una capa neutral; se ve el sistema en vivo. |

**La idea de fondo:** cada garantía está puesta donde es *estructural* (una transacción,
un constraint, un scope), no donde alguien tiene que acordarse de hacerla bien.

---

## 3. Las piezas, una por una

| Componente | Su rol en una frase | Tecnología y por qué |
|---|---|---|
| **Odoo** | Fuente de verdad de órdenes | ERP real open-source, con API y webhooks. No un CSV de juguete. |
| **Postgres operacional** | Outbox, dedup, orders silver, audit | Transaccional, confiable, el `ON CONFLICT` da idempotencia gratis. |
| **Adapters** | Traducen orden Odoo → modelo marketplace | `Protocol` de Python: un contrato, dos implementaciones (ML OAuth, Paris API-key). |
| **Outbox worker** | Lee la cola y empuja con retry | Polling + tenacity. Simple y observable. |
| **Pub/Sub** | Mensajería async + DLQ | Está nombrado en el JD; emulador local sin costo, real en GCP. |
| **Webhook receiver** | Recibe, valida, deduplica | FastAPI; HMAC para seguridad; el único servicio público. |
| **Subscriber/Reconciler** | Refleja estado y corrige drift | Dos redes de seguridad: evento + polling. |
| **BigQuery + dbt** | Capa analítica bronze/silver/gold | dbt da contratos, tests y docs. SQL versionado. |
| **MCP server** | API de dominio para el agente IA | FastMCP; IAM por scope + audit log inmutable. El diferenciador. |
| **OTel + Grafana** | Observabilidad end-to-end | Estándar abierto; sin vendor lock-in. |

---

## 4. Qué mirar (y dónde) para contar la historia

La demo se cuenta en tres pantallas. Esto es exactamente qué abrir y qué decir.

### A. Grafana — "el sistema está vivo y lo veo"
`make obs-up` → http://localhost:3000 → dashboard **Comex Ops**.

| Panel | Qué demuestra | Qué decir |
|---|---|---|
| **Webhooks recibidos / min** | el sistema recibe tráfico real | "Cada webhook que entra del marketplace, contado en vivo." |
| **Order sync outcomes** | done / retry / dlq por adapter | "Aquí veo si las órdenes llegan, reintentan o fallan." |
| **DLQ depth** | órdenes bloqueadas ahora | "Este número es el dolor del lunes: órdenes atascadas." |
| **Latencia push p50/p95/p99** | SLA por marketplace | "Cuánto tarda Odoo→marketplace. Esto es el SLA que cobra penalidad." |

> Para que haya datos: `make seed` (genera órdenes) y `make chaos` (llena el DLQ).

### B. MCP + Claude — "un agente opera el incidente"
El momento fuerte. En Claude:

1. *"¿Por qué la orden X no llegó a MercadoLibre?"* → el agente llama `trace_order` →
   responde con el timeline (outbox → error → DLQ) y la causa raíz.
2. *"Reintenta esa orden."* → llama `retry_failed_sync` → la orden vuelve a la cola.
3. En Grafana, el **DLQ depth** baja. La historia se cierra visualmente.

> Lo que demuestra: no es un chatbot, es un agente con permisos acotados (scope) y todo
> queda en el **audit log**. Eso es "AI-native real", no una demo.

### C. dbt / BigQuery — "los datos cuentan tendencias"
`gold.sla_by_marketplace`, `gold.dlq_root_causes`: de lo operacional pasamos a *insight*
de negocio. "No solo muevo órdenes; mido el SLA y las causas de fallo."

---

## 5. El relato de 90 segundos (para la entrevista)

> "Un lunes, Comercio Exterior no sabe por qué las órdenes no aparecen en los marketplaces.
> Construí el sistema que responde eso end-to-end.
>
> Odoo es la fuente de verdad. Cuando una orden se confirma, un **outbox pattern** garantiza
> —en la misma transacción— que se va a sincronizar, con **retry y DLQ** si el marketplace
> falla. Los webhooks de vuelta se **validan y deduplican**, se normalizan a una capa silver,
> y se reconcilian contra Odoo.
>
> Todo emite **trazas y métricas** que veo en **Grafana**: throughput, SLA por marketplace,
> profundidad del DLQ en vivo.
>
> Lo analítico va a **BigQuery con dbt** —bronze/silver/gold— para medir SLA y causas de fallo.
>
> Y lo que lo hace AI-native: un **MCP server** deja que Claude trace una orden y la repare,
> con **permisos por scope y un audit log inmutable**. El operador pregunta '¿por qué no llegó
> la orden X?', el agente responde con la causa raíz y la reintenta.
>
> Está corriendo local y **deploy-ready en GCP**: Cloud Run, Pub/Sub real, BigQuery Sandbox,
> por menos de cinco dólares al mes."

---

## 6. Cómo conecta con el rol (FDE)

Un Forward Deployed Engineer se sienta con negocio, traduce un proceso a código, y lo deja
en producción con dueño y métrica. Este proyecto es ese ciclo completo: parte de un dolor
real de Comex, lo resuelve con decisiones de ingeniería justificadas, lo deja medible en
Grafana y operable por un agente. No demuestra que sé un framework: demuestra que sé llevar
un problema de negocio a un sistema confiable.
