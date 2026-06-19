# Tres decisiones de diseño no triviales en Retail Order Sync Hub

Notas técnicas sobre las decisiones que más pensé al construir el sistema de
sincronización de órdenes Odoo ↔ marketplaces. No son las obvias (qué framework,
qué lenguaje) sino las que determinan si el sistema es confiable bajo fallo.

---

## 1. Outbox pattern en vez de CDC

**El problema:** cuando una orden se confirma en Odoo, tiene que terminar publicada
en MercadoLibre y Paris. ¿Cómo garantizo que *si la orden existe en Odoo, eventualmente
llega al marketplace*, incluso si el marketplace está caído en ese momento?

**Dos caminos:**

- **CDC (Change Data Capture):** un proceso lee el WAL de Postgres / el log de Odoo
  y reacciona a cambios. Potente, pero acopla el sistema al motor de la base, requiere
  Debezium o similar, y la semántica de "qué cambió" es a nivel de fila, no de intención
  de negocio.

- **Outbox pattern:** en la misma transacción que confirma la orden, escribo una fila
  en una tabla `outbox`. Un worker lee esa tabla y publica. El intento de sync es un
  hecho de negocio explícito, no una inferencia sobre filas que cambiaron.

**Por qué elegí outbox:**

La garantía clave es atomicidad. Esto es lo que la hace verdad:

```sql
INSERT INTO outbox (aggregate_id, target_adapter, payload, status)
VALUES (:order_id, :adapter, :payload, 'pending')
ON CONFLICT (aggregate_id, target_adapter) DO NOTHING
RETURNING id;
```

Si Postgres acepta el commit, la fila está. Si la fila está, el worker la va a procesar.
El `ON CONFLICT DO NOTHING` hace que re-encolar la misma orden sea un no-op: idempotente
por construcción. No hay ventana donde la orden "se confirmó pero no se sabe si se intentó
sincronizar".

CDC habría agregado una pieza de infraestructura (Debezium + su propio Kafka) para
resolver un problema que el outbox resuelve con una tabla y un constraint. Para el volumen
de un retailer mediano, esa complejidad no se paga.

**El trade-off:** el worker hace polling (`WHERE status='pending' AND next_attempt_at <= now()`),
lo que introduce latencia (segundos) vs. la reacción casi-instantánea de CDC. Para sync de
órdenes a marketplaces, segundos es irrelevante.

---

## 2. Idempotencia como invariante, no como feature

**El problema:** los marketplaces garantizan entrega *at-least-once* de webhooks. El mismo
evento "orden pagada" puede llegar dos, tres veces. Si cada llegada dispara un efecto, el
sistema corrompe su propio estado.

**La decisión:** tratar la idempotencia como un invariante que se enforced en el punto de
entrada, no como una verificación que cada handler recuerda hacer.

```python
result = store.record(source, event_id, payload, headers)
if not result.is_new:        # ON CONFLICT (source, event_id) DO NOTHING devolvió vacío
    return 200               # corto acá: no bronze, no publish, no efecto
```

La clave es que la deduplicación ocurre **antes** de cualquier efecto: antes de escribir
bronze, antes de publicar a Pub/Sub, antes de tocar Odoo. Un webhook duplicado es
literalmente invisible para el resto del sistema — no llega a las capas donde podría hacer
daño.

**Por qué importa el orden:** si dedujera *después* de escribir bronze, tendría dos filas
raw del mismo evento. El reconciliador eventualmente detectaría el drift y lo corregiría,
pero la trazabilidad quedaría sucia: "¿por qué esta orden tiene dos eventos de pago?".
Poner el dedup en la puerta mantiene el linaje de datos limpio.

**Property test que lo respalda:** enviar el mismo `event_id` N veces (con Hypothesis,
N y el payload aleatorios) siempre produce exactamente una fila en bronze. No es un caso
de prueba puntual; es una propiedad del sistema.

---

## 3. IAM del MCP server: scopes por operación, no roles por servicio

**El contexto:** el MCP server le da a un agente IA (Claude) la capacidad de no solo
*leer* el estado de las órdenes sino de *operar* incidentes: reintentar un sync, vaciar
el DLQ. Eso es poder real sobre el sistema productivo. ¿Cómo lo acoto?

**La tentación:** un token "admin" que puede todo y un token "readonly" que solo lee. Dos
roles, simple.

**El problema con eso:** "reintentar una orden específica" y "vaciar todo el DLQ" son
operaciones con radios de impacto radicalmente distintos. La primera la hace un operador
de turno a las 2am sin riesgo. La segunda puede borrar mensajes en vuelo y solo debería
hacerla el ingeniero de guardia. Agruparlas bajo "admin" obliga a dar demasiado poder
para tareas rutinarias.

**La decisión:** scopes por operación, mapeados a roles componibles.

```
viewer   = orders.read, metrics.read
operator = viewer  + outbox.retry, dlq.replay
admin    = operator + dlq.admin
```

Cada tool declara el scope que exige:

```python
@audit(scope="dlq.admin")
def _drain_dlq(topic: str, dry_run: bool = True, *, api_token: str) -> dict:
    require_scope(api_token, "dlq.admin")
    ...
```

El operador de turno tiene `dlq.replay` (reintentar uno) pero no `dlq.admin` (vaciar todo).
El principio de menor privilegio aplicado a la granularidad de la operación, no del servicio.

**La pieza que lo hace auditable:** cada llamada write pasa por `@audit`, que registra en
`mcp_audit_log` quién, qué scope usó, con qué params, resultado y latencia — en una
transacción separada, para que una falla de auditoría nunca tumbe la operación y viceversa.
Un intento denegado por falta de scope también queda registrado (`result_status='denied'`).
Cuando el agente IA opera el sistema, hay un rastro inmutable de todo lo que hizo.

**Lo que dejé para después conscientemente:** los tokens son estáticos (variable de entorno)
en vez de JWT firmados con rotación. La función que resuelve scopes (`_token_scopes()` con
`@lru_cache`) está aislada justamente para que migrar a Secret Manager + JWT en V3 sea un
cambio local que no toca ninguna de las tools ni sus tests.

---

## El hilo común

Las tres decisiones comparten una forma: **mover la garantía al punto donde es estructural
en vez de depender de que cada pieza se acuerde de hacer lo correcto.**

- Outbox: la atomicidad la da la transacción, no la disciplina del worker.
- Idempotencia: la da un constraint en la puerta, no un check en cada handler.
- IAM: la da el scope declarado en la tool, no la buena fe del que configura el token.

Para un sistema que va a producción y que un agente IA va a operar de forma autónoma, esa
es la diferencia entre "funciona en la demo" y "funciona el martes a las 2am".
