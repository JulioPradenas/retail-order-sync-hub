# Guía de demo — Retail Order Sync Hub

Guía para **mostrar el proyecto completo en vivo**, paso a paso, sin necesidad de saber
programar. Está pensada como un **recorrido por estaciones**: en cada una enciendes o
generas algo y lo ves funcionando con tus propios ojos (en un panel de botones, en
gráficos en vivo y conversando con una IA).

Al terminar el recorrido habrás visto **todas** las funcionalidades del proyecto:
el panel de control, el ERP con pedidos reales, los webhooks, la sincronización con
marketplaces, los reintentos, la cola de errores (DLQ), los tableros de monitoreo
(Grafana/Prometheus), las trazas (Tempo) y el asistente de IA (MCP).

> **Para presentar:** cada estación trae **"Qué mostrar"** (lo que haces) y
> **"Qué decir"** (la idea de negocio detrás). Si solo quieres correrlo, ignora el
> "Qué decir" y sigue los pasos.

> **Nota sobre dos niveles:** casi todo funciona **100% en tu computador** (no necesitas
> internet ni cuentas). Solo la **Estación 8 (reportes en la nube)** requiere una cuenta
> de Google Cloud; está marcada como **opcional** para que nunca rompa la demo en vivo.

---

## 0. El proyecto en una frase

Una tienda vende en varios **marketplaces** (MercadoLibre, Paris). Cada venta debe
llegar al sistema central y sincronizarse de vuelta a cada marketplace, **sin perder
ningún pedido aunque algo falle**. Este proyecto hace exactamente eso, y además se
**monitorea solo** y permite que una **IA lo opere** con lenguaje natural.

Palabras que oirás (en simple):

- **Webhook** = un aviso automático: "¡entró una venta!".
- **Order sync** = enviar ese pedido al marketplace. A veces falla y se **reintenta**.
- **DLQ** = la "bandeja de pedidos atascados" (los que fallaron demasiadas veces).
- **Grafana** = los tableros con gráficos en vivo.
- **MCP** = el puente para que una IA consulte y opere el sistema.

---

## 1. Preparación (una sola vez, ~2 min)

Necesitas **dos** cosas abiertas:

1. **Docker Desktop** — el motor que corre el proyecto. Ábrelo y espera a que el ícono
   de la ballena esté quieto. **Si no está abierto, nada funcionará.**

2. **La Terminal** — la usas solo para **un comando** que abre el panel. Copia, pega y
   Enter:

   ```bash
   cd /Users/julio/Desktop/retail-order-sync-hub && make console
   ```

   En unos segundos se abre en el navegador el **Panel de control**
   (`http://localhost:8501`). Si no se abre solo, escribe esa dirección en el navegador.

> A partir de aquí **todo se hace con botones**. La Terminal puedes dejarla abierta y
> olvidarte de ella.

---

## 2. Estación 1 — El Panel de control

**Qué mostrar:** el panel recién abierto.

Tiene dos columnas:

- **Izquierda — Estado de servicios:** una lista con luces. **Verde = encendido**,
  **rojo = apagado**. Arriba un contador **"Servicios arriba: X / 12"**.
- **Derecha — Acciones:** los botones, agrupados en *Stack operacional*,
  *Observabilidad* y *Apagado*.

**Qué decir:** "Todo el sistema se levanta y opera desde aquí, sin tocar la terminal.
Cada luz es un componente real del sistema corriendo en contenedores."

---

## 3. Estación 2 — Encender el sistema

Pulsa estos botones **en orden**. Tras cada uno espera el mensaje **verde "OK"** antes
del siguiente (el texto que aparece es el registro de lo que se ejecutó, no tienes que
copiar nada).

| Orden | Botón | Qué enciende | Tarda |
|---|---|---|---|
| 1 | **Levantar stack** | ERP (Odoo), base de datos, colas y los "trabajadores" que sincronizan | ~1 min |
| 2 | **Migrar BD** | Crea las tablas de la base de datos | segundos |
| 3 | **Seed Odoo** | Carga datos de ejemplo: 3 productos, 2 clientes, 1 pedido | segundos |
| 4 | **Levantar observabilidad** | Enciende **Grafana + Prometheus + Tempo** (el monitoreo) | ~30 seg |

Ahora pulsa **"Refrescar estado"** (arriba a la izquierda): deberías ver casi todo en
**verde** y el contador cerca de **12/12**.

**Qué decir:** "En menos de dos minutos levantamos un sistema completo: ERP,
mensajería, sincronizadores y todo el monitoreo."

---

## 4. Estación 3 — Ver pedidos reales en el ERP (Odoo)

**Qué mostrar:** baja en el panel a **"Accesos rápidos"** y pulsa **Odoo**. Entra con
`admin` / `admin`. Busca el pedido de venta **ROSH-ORDER-0001**.

**Qué decir:** "Este es el sistema donde la empresa gestiona sus ventas. El dato de un
pedido nace aquí (o llega desde un marketplace) y de aquí parte la sincronización."

> Es el punto de partida del flujo: un pedido existe en el ERP y debe propagarse a los
> marketplaces de forma confiable.

---

## 5. Estación 4 — Los tableros en vivo (Grafana)

**Qué mostrar:** en "Accesos rápidos" pulsa **Grafana** (`admin` / `admin`).
Hay dos tableros; empieza por **Comex Ops**.

> ### Ajuste imprescindible (hazlo siempre)
> Los gráficos muestran lo que pasa **ahora**. Arriba a la derecha:
> 1. Rango de tiempo → **"Last 15 minutes"**.
> 2. Refresco automático → **10s**.
>
> Sin esto, los gráficos pueden verse vacíos aunque haya datos.

### Tablero "Comex Ops" — la operación del negocio

Recorre los 6 paneles (de momento estarán casi vacíos; se llenan en la Estación 5):

| Panel | Qué significa, en simple |
|---|---|
| **Webhooks recibidos / min** | Cuántos avisos de venta están entrando |
| **Order sync outcomes / min** | Resultado de cada sincronización: éxito, **retry** (reintento) o **dlq** (atascado) |
| **DLQ depth** | Cuántos pedidos están atascados ahora mismo |
| **Outbox pendiente** | Pedidos esperando ser enviados |
| **Tasa de error sync** | Qué porcentaje de envíos está fallando |
| **Latencia push (p50/p95/p99)** | Qué tan rápido viajan los pedidos al marketplace |

### Tablero "Pipeline Health" — la salud técnica

Cambia de tablero (menú de dashboards). Aquí se ve la "salud interna":

| Panel | Qué significa, en simple |
|---|---|
| **OTel Collector — spans / s** | El sistema de monitoreo recibiendo información |
| **OTel Collector — métricas exportadas / s** | Esa información llegando a los tableros |
| **HTTP outbound — latencia** | Qué tan rápido responden los marketplaces |
| **FastAPI — requests / s** | Tráfico que recibe el receptor de webhooks |
| **FastAPI — latencia p95** | Velocidad de respuesta del receptor |
| **Prometheus — scrape targets** | Qué componentes están siendo monitoreados (en verde) |

**Qué decir:** "El sistema se observa a sí mismo de punta a punta: desde el negocio
(ventas, errores) hasta la infraestructura (velocidad, tráfico)."

---

## 6. Estación 5 — Generar datos y verlos aparecer EN VIVO

Esta es la parte más vistosa. Los gráficos están vacíos **a propósito**: el sistema no
inventa tráfico, tú lo disparas y lo ves aparecer en segundos.

> **Truco de presentación:** deja **Grafana abierto en una ventana** y el **Panel de
> control en otra**, lado a lado. Pulsas un botón en el panel y narras cómo sube el
> gráfico en Grafana.

Vuelve al Panel de control (`http://localhost:8501`) y haz esto:

### 5a. Tráfico de webhooks (avisos de venta)

Pulsa **"Generar tráfico de webhooks"**. Envía 40 avisos reales al sistema.

- **Mira en Grafana:** sube el panel **"Webhooks recibidos / min"**.
- **Qué decir:** "Cada barra es un aviso de venta entrando y siendo registrado."

> **Detalle valioso (idempotencia):** el panel separa **new** vs **duplicate**. El
> sistema reconoce si un aviso ya llegó antes y **no lo procesa dos veces**. Eso evita
> pedidos duplicados aunque el marketplace reenvíe el mismo aviso.

### 5b. Resultados de sincronización: reintentos y atascos

Pulsa **"Generar sync outcomes"**. Encola pedidos a MercadoLibre que fallan a propósito.

- **Mira en Grafana:** en **"Order sync outcomes / min"** aparecen
  **mercadolibre / retry** y **mercadolibre / dlq**. También sube la **tasa de error**.
- **Qué decir:** "Cuando un envío falla, el sistema **reintenta solo** con esperas
  crecientes. Si tras varios intentos sigue fallando, lo manda a la **DLQ** para no
  perderlo ni bloquear al resto."

### 5c. Cola de errores (DLQ)

Pulsa **"Generar DLQ demo"**. Mete 10 pedidos directamente a la bandeja de atascados.

- **Mira en Grafana:** sube **"DLQ depth"**.
- **Qué decir:** "La DLQ es la red de seguridad: ningún pedido se pierde, queda aquí
  esperando ser revisado o reprocesado."

> ¿Quieres más volumen para la demo? Vuelve a pulsar cualquiera de estos botones: cada
> clic agrega más tráfico.

---

## 7. Estación 6 — El viaje de un pedido (Tempo, opcional)

**Qué mostrar:** en Grafana, menú lateral → **Explore** → fuente de datos **Tempo** →
busca trazas recientes y abre una.

**Qué decir:** "Aquí vemos el **viaje completo** de un pedido como una línea de tiempo:
cuándo entró el webhook, cuándo se intentó el envío, cuánto tardó cada paso. Sirve para
investigar exactamente dónde se demoró o falló algo."

> Esta estación es más técnica; puedes mostrarla por encima o saltarla según la audiencia.

---

## 8. Estación 7 — Operar el sistema con una IA (MCP)

El **MCP** conecta **Claude Desktop** (la app de escritorio de Claude) con el sistema.
En vez de mirar gráficos, le **preguntas** y la IA usa "herramientas" para responder con
datos reales — e incluso puede **actuar** (reintentar pedidos, vaciar la DLQ).

### Encenderlo

1. El proyecto debe estar arriba (Estaciones 2 y 5 hechas).
2. Cierra Claude Desktop por completo: menú **Claude → Quit** (`Cmd+Q`). No basta cerrar
   la ventana.
3. Vuelve a abrirlo.
4. En **Settings → Developer**, `retail-order-sync-hub` debe aparecer en verde
   (*running*). En el chat verás un ícono de herramientas.

### Qué puede hacer la IA (8 herramientas)

Cada herramienta necesita un **token** (una credencial) que define qué tiene permitido:

- **`dev-token`** → solo **consultar**.
- **`admin-token`** → consultar **y operar** (acciones que cambian cosas).

**Consultas:**

| Herramienta | Responde a... |
|---|---|
| `get_order_status` | el estado de un pedido |
| `trace_order` | la historia completa de un pedido (webhook → envío → resultado) |
| `get_dlq_depth` | cuántos pedidos hay atascados |
| `find_failed_orders` | qué pedidos fallaron en un período |
| `get_sla_metrics` | tiempos de sincronización por marketplace *(requiere GCP, ver Estación 8)* |

**Acciones:**

| Herramienta | Hace... |
|---|---|
| `replay_dlq_message` | reintenta un mensaje atascado en la DLQ |
| `retry_failed_sync` | reintenta sincronizar un pedido |
| `drain_dlq` | vacía la DLQ (tiene modo de simulación seguro) |

### Ejemplos para copiar y pegar (escríbelos en Claude Desktop)

**Consultas (con `dev-token`):**

```
¿Cuántos pedidos hay atascados en el DLQ? usa api_token=dev-token
```
```
Traza la orden 1 y muéstrame su historia completa. usa api_token=dev-token
```
```
Muéstrame los pedidos que fallaron en los últimos 7 días. usa api_token=dev-token
```

**Acciones (con `admin-token`):**

```
Haz un drain del DLQ en modo simulación (dry_run). usa api_token=admin-token
```
```
Reintenta la sincronización de la orden 3. usa api_token=admin-token
```

**Qué decir / el momento "wow":** primero genera atascos (Estación 5b/5c) y luego
pregunta *"¿cuántos pedidos hay atascados en el DLQ?"*. La IA responde con el número
real. Después pídele *"haz un drain en modo simulación"*: verás el control de la IA
sobre el sistema. **Si pides una acción con `dev-token`, el sistema la bloquea** — así se
demuestra el control de permisos. Toda acción queda registrada en una bitácora de
auditoría.

---

## 9. Estación 8 — Reportes en la nube (dbt + BigQuery)

> ## PARTE OPCIONAL — SEPARADA DE LA DEMO LOCAL (NO ejecutar en el vivo)
>
> **Todo lo anterior (Estaciones 1 a 7) corre 100% en tu computador y es lo que muestras
> en vivo.** Esta estación es **distinta**: vive en la **nube (Google Cloud)** y
> **requiere una cuenta de GCP ya configurada**.
>
> **Para el día de la demo en vivo: NO la ejecutes.** Si GCP no está listo, los comandos
> fallan. Aquí solo se **explica** qué hace y por qué importa, para poder **contarla** sin
> correrla. Nada de esta estación afecta a las Estaciones 1–7.

### Qué hace (para explicar, no para ejecutar en vivo)

El proyecto no se queda en operar: también **convierte los datos del día a día en
reportes para tomar decisiones**, usando un modelo por capas (bronce → plata → oro), el
estándar de la industria de datos:

- **Bronce:** los datos crudos tal como llegan (cada webhook, cada intento de envío).
- **Plata:** esos datos limpios, ordenados y normalizados.
- **Oro:** reportes listos para decidir:
  - **SLA por marketplace** — qué tan rápido se sincroniza cada uno.
  - **Causas de error en la DLQ** — por qué se atascan los pedidos.
  - **Throughput diario** — cuánto volumen se mueve por día.
  - **Tendencias de error** — si los problemas suben o bajan en el tiempo.

### Por qué importa

- **Cierra el círculo de datos:** los mismos eventos operativos (Estaciones 5–7) se
  transforman en **inteligencia de negocio**. No es solo "que funcione", es **aprender
  del sistema**.
- **Habla el idioma del negocio:** un gerente no mira reintentos uno por uno; mira
  "MercadoLibre tarda X, los errores bajaron Y%". Eso sale de la **capa oro**.
- **Escala a producción:** correr esto en **BigQuery** (la nube) demuestra que la
  arquitectura sirve con volúmenes reales, no solo en una laptop.
- **Conecta con la IA:** es lo que alimenta la herramienta MCP **`get_sla_metrics`**, de
  modo que la IA puede responder preguntas ejecutivas, no solo operativas.

### Cómo se ejecutaría (solo si GCP está configurado — NO en el vivo)

```bash
make dbt-run     # construye los reportes (capas plata y oro)
make dbt-test    # valida la calidad de los datos
make dbt-docs    # genera documentación navegable de los modelos
```

Recién entonces la herramienta MCP `get_sla_metrics` responde con datos reales:

```
Dame las métricas de latencia de MercadoLibre. usa api_token=dev-token
```

**Cómo contarla en vivo (sin ejecutarla):** "Además de operar en tiempo real, el sistema
alimenta una capa analítica en la nube que transforma cada evento en reportes ejecutivos
—SLA por marketplace, causas de error, tendencias— y esos mismos reportes los puede
consultar la IA. Esa parte vive en Google Cloud; hoy me enfoco en la demo local."

---

## 10. Apagar todo al terminar

En el panel:

1. **Bajar observabilidad** (sección Observabilidad) — apaga Grafana/Prometheus/Tempo.
2. **Bajar stack** (sección Apagado) — apaga el resto.

Esto libera memoria. La próxima vez retomas desde la Estación 2.

---

## 11. Guion express para el día de la demo (en vivo)

Recorrido recomendado, ~7 minutos:

1. Abre **Docker Desktop**; espera a que esté listo.
2. Terminal: `cd /Users/julio/Desktop/retail-order-sync-hub && make console`.
3. **Panel:** Levantar stack → Migrar BD → Seed Odoo → Levantar observabilidad
   (espera el "OK" de cada uno) → Refrescar estado (≈12/12 en verde).
4. **Odoo:** muestra el pedido real (Estación 3).
5. **Grafana → Comex Ops**, rango "Last 15 minutes", refresco 10s. Explica los paneles.
6. **Genera datos** (Panel, lado a lado con Grafana): Tráfico de webhooks → Sync outcomes
   → DLQ demo. Narra cómo suben los gráficos.
7. **Pipeline Health:** muestra que el sistema también se monitorea por dentro.
8. **Claude Desktop:** "¿cuántos pedidos hay atascados en el DLQ? usa api_token=dev-token"
   y luego un drain en modo simulación con `admin-token`.
9. (Opcional) Estación 8 si tienes GCP.
10. **Apagar:** Bajar observabilidad → Bajar stack.

---

## 12. Si algo falla

| Síntoma | Causa común | Solución |
|---|---|---|
| Un botón da error rojo | Docker no está corriendo | Abre Docker Desktop y espera a que esté listo |
| Grafana se ve vacío | Rango muy amplio o sin tráfico | Pon "Last 15 minutes" y genera datos (Estación 5) |
| No aparece un botón nuevo en el panel | El panel quedó abierto de antes | Refresca el navegador (F5) |
| No veo `mercadolibre/retry` ni `/dlq` | No generaste sync outcomes | Pulsa "Generar sync outcomes" y espera ~10s |
| Claude no muestra herramientas | No reiniciaste Claude Desktop | `Cmd+Q` y vuelve a abrir |
| Claude dice "sin permiso" / PermissionError | Usaste `dev-token` para una acción | Usa `api_token=admin-token` |
| `get_sla_metrics` falla | Requiere GCP/BigQuery | Es opcional (Estación 8); omítela en la demo local |
| El MCP aparece "failed" en rojo | Stack apagado o ruta de `uv` | Verifica que el stack esté arriba; revisa logs en Settings → Developer |

**Direcciones útiles (para abrir a mano si hace falta):**

- Panel de control: `http://localhost:8501`
- Grafana: `http://localhost:3000` (admin / admin)
- Prometheus: `http://localhost:9090`
- Odoo (ERP): `http://localhost:8069` (admin / admin)

---

¿Quieres el detalle técnico de cada componente? Está en el `README.md` y en la carpeta
`docs/`.
