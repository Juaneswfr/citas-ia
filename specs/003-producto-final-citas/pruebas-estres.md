# Plan de pruebas de estrés — CitasIA (producto final)

**Fecha:** 28-10-2026 · **Rama:** `master` · **HEAD leído:** `f0e97b0` · **Autor del plan:** arquitecto QA (Claude Code)
**Estado:** DISEÑO. Nada de este plan se ha ejecutado. Ningún resultado aquí es medido.

Convenciones:
- `SUPUESTO` = número o decisión que requiere confirmación del usuario antes de ejecutar.
- `no verificado` = afirmación que no se pudo comprobar leyendo el repo.
- `ESPERADO FAIL` = por lectura de código, el escenario muy probablemente falla hoy. Se mantiene en la campaña para tener la evidencia medida, no para adivinar.
- Las rutas `archivo:línea` son relativas a `backend-lang/` salvo que se indique otra cosa.

---

## 0. Hallazgos de la lectura que condicionan el plan

Esto sale de leer el código; todavía no se ha medido. Cada punto se asigna al escenario que lo valida.

| # | Hallazgo | Evidencia | Escenario |
|---|---|---|---|
| H1 | La ruta Meta `POST /webhooks/whatsapp` **no deduplica por `wamid`**: no hay clave de idempotencia ni índice único en `messages.provider_message_id`. | `src/api/routes/webhooks.py:134-167`, `migrations/001_initial_schema.sql:201` | E1 |
| H2 | La ruta Meta lee el cuerpo con `request.body()`, sin límite de 1 MB, **no devuelve 413**. Con firma inválida responde **403**, no 401. Kapso sí aplica el límite (`_read_body_limited`). | `webhooks.py:117`, `webhooks.py:122`, `webhooks.py:45-55` | E2 |
| H3 | Ruta Meta: `asyncio.create_task` **no guarda referencia fuerte** de la tarea (Kapso sí usa `_spawn`). El GC puede recolectar la tarea a mitad de camino. | `webhooks.py:128-129` vs `webhooks.py:39-42` | E1, E10 |
| H4 | Rate limit Meta `200/minute` con clave `X-Workspace-ID` **controlada por el emisor**, o IP si falta. Meta no envía ese header, así que todo el tráfico real desde unas pocas IPs de Meta comparte 200/min (~3,3 msg/s) **por proceso**. Además el contador vive en memoria de cada worker (`--workers 2`). | `webhooks.py:23-29,102`, `Dockerfile:21` | E1, E9 |
| H5 | Reserva = `check_availability` (free/busy de Google) → `create_event` → `INSERT`. **No hay restricción de exclusión ni lock** en `appointments` (solo `CHECK (end_at > start_at)` y un índice no único). Es una carrera TOCTOU. | `src/api/routes/appointments.py:100-141`, `migrations/001_initial_schema.sql:136-152,307` | E3 |
| H6 | `CalendarService` llama a `googleapiclient ... .execute()` **síncrono dentro de `async def`**: bloquea el event loop. No hay reintentos ni backoff para Calendar. | `src/services/calendar_service.py:53,85-89,104,117,156` | E5, E3, E8 |
| H7 | `crear_cita` mantiene **una conexión del pool abierta** mientras llama a Google (bloqueante). Pool `min=2,max=10` por proceso, `acquire()` **sin timeout**. | `src/services/appointment_agent.py:119-130`, `src/core/database.py:24` | E8 |
| H8 | `asyncio.wait_for(..., 45s)` del agente **no puede interrumpir** una llamada síncrona a Google que ya está en curso. | `appointment_agent.py:25,198` + H6 | E4, E5 |
| H9 | El worker de recordatorios corre en **cada worker de uvicorn** (2 procesos). Ambos seleccionan la misma cita y solo después marcan `sent` (no hay `UPDATE ... RETURNING` atómico): **duplicados**. | `src/api/main.py:43-44`, `Dockerfile:21`, `src/workers/reminder_worker.py:45-133` | E7 |
| H10 | La ventana de recordatorio es ±5 min (`_TOLERANCE_MINUTES=5`) y el ciclo corre cada 30 min. **Unos 2/3 de las citas nunca caen en la ventana**. | `reminder_worker.py:22,40-42,150` | E7 |
| H11 | Los recordatorios usan `send_message` **sin `provider`**: un canal Kapso sale por Meta Graph. Una cita se marca como enviada si `sent or customer_email`, es decir, aunque WhatsApp haya fallado. | `reminder_worker.py:107-111,129` | E6, E7 |
| H12 | Las columnas `reminder_24h_sent` / `reminder_2h_sent` **no aparecen en `migrations/`** (grep vacío). Contra la BD de migraciones, `run_reminders` fallaría con `UndefinedColumn`. Si existen en Supabase: **no verificado**. | `reminder_worker.py:43,48` | E7 (pre-requisito) |
| H13 | El envío Meta no tiene reintentos ante 429/5xx. El de Kapso sí (2 reintentos, tope de 2 s). | `src/services/whatsapp_service.py:73-90` vs `src/services/whatsapp_provider.py:80-88` | E6 |
| H14 | Si el proceso muere después del ACK 200, el mensaje Meta **se pierde** porque no hay outbox. En Kapso, si muere tras reclamar la clave, el evento se pierde (riesgo documentado en el código). | `webhooks.py:127-131`, `webhooks.py:208-210` | E11 |
| H15 | `/auth/login` **no tiene rate limit** (no hay `@limit` en `auth.py`) y usa bcrypt, que consume CPU. El `limiter` global de `main.py:32` no decora ninguna ruta. | `src/api/routes/auth.py:90-116`, `src/api/main.py:32,74` | E9 |
| H16 | `POST /webhooks/google-calendar` **no valida ningún token** (`X-Goog-Channel-Token`) y lanza una tarea de sync por cada request, sin referencia fuerte ni rate limit. | `webhooks.py:379-401` | E2, E9 |
| H17 | El URL de Meta Graph está **fijo en el código** (`https://graph.facebook.com/...`) y no se puede redirigir por variable. Kapso sí permite cambiarlo (`KAPSO_BASE_URL`). | `whatsapp_service.py:57-60`, `src/core/config.py:62` | Entorno (§4) |
| H18 | El agente **no es un grafo LangGraph**: es un bucle de tool-calling con `langchain` (`bind_tools` + `ainvoke`). El modelo se crea con `init_chat_model("anthropic:...")`. | `appointment_agent.py:23,40-42,152-187` | E4 |
| H19 | `agent_service.py` hace `from core.database import _pool` al importar el módulo. Si se importa antes de `create_pool`, queda ligado a `None`. Hoy se importa tarde (dentro de la función), así que funciona. Es frágil en el harness. | `src/services/agent_service.py:13`, `webhooks.py:137` | Harness |

---

## 1. Objetivos y SLO medibles

El repositorio no define números de SLO: los PRD solo piden "latencia", "error rate", "evitar doble reserva" y "reintentos con backoff" (`documentation/PRD Final — Integraciones y Operación.md:33,87,100-101`; `documentation/PRD de Backend Python.md:203`). Por eso todos los números son **SUPUESTO**, salvo los invariantes de cero, que son de negocio.

Perfil de carga de referencia **SUPUESTO**: 200 workspaces activos al lanzamiento, pico de 20 msg/s entrantes agregados (≈ 6 msg/min por workspace en hora punta), 2 000 citas/día. Hay que confirmarlo con el usuario: todos los N/M se derivan de aquí.

| ID | SLO | Valor | Tipo | Justificación |
|---|---|---|---|---|
| S1 | p95 del ACK de `POST /webhooks/whatsapp` y `/webhooks/kapso/n/{token}` con firma válida a 20 msg/s sostenidos | **p95 < 300 ms, p99 < 1 000 ms** | SUPUESTO | En el request solo se hace HMAC, parseo, `INSERT` de idempotencia (Kapso) y despacho a background. Meta exige ACK rápido (el código cita < 20 s, `webhooks.py:112`). 300 ms deja margen ante GC y pool. |
| S2 | Tasa de error 5xx en webhooks con firma válida | **< 0,1 %** | SUPUESTO | Cualquier 5xx provoca reintentos de Meta o Kapso y amplifica la carga. |
| S3 | Procesamiento duplicado del mismo `X-Idempotency-Key` (Kapso) o `wamid` (Meta) | **0** | Invariante | Un duplicado son dos respuestas al cliente y potencialmente dos citas. |
| S4 | p95 del rechazo por firma inválida (401/403) o cuerpo > 1 MB (413) en ráfaga de 200 req/s | **p95 < 50 ms**; RSS del proceso < +50 MB durante la ráfaga | SUPUESTO | El rechazo debe ser más barato que el procesamiento, si no la ráfaga es una DoS. 50 MB ≈ 50 cuerpos de 1 MB bufferizados a la vez. |
| S5 | Citas `confirmed` que se solapan en el mismo calendario tras N reservas concurrentes del mismo slot | **exactamente 1**; eventos huérfanos en el doble de Google = **0** | Invariante | PRD Final:33 "evitar doble reserva". |
| S6 | Corridas del agente (M conversaciones simultáneas, LLM simulado de 1,5 s por llamada) | p95 de punta a punta < **(llamadas LLM × 1,5 s) + 2 s**; `agent_runs.status='running'` tras drenar = **0**; corridas con error inyectado que tienen `agent_alerts` = **100 %** | SUPUESTO (latencia), invariante (resto) | Lo que añade el backend debe ser acotado. Ninguna corrida puede quedar colgada. |
| S7 | Webhook mientras Google responde lento (5 s) o con 429/5xx | El p95 del ACK sigue cumpliendo S1; `GET /` (health) p95 < 200 ms | SUPUESTO | Si Google lento degrada el ACK es que el event loop está bloqueado (H6). |
| S8 | Envío fallido a Meta o Kapso | `agent_runs.status='error'` + alerta = 100 %; outbound guardado sin entrega = **0**; inbound perdido = **0** | Invariante | Ya es requisito en `agent_service.py:85-87`. |
| S9 | Recordatorios | Cobertura = **100 %** de las citas `confirmed` reciben cada recordatorio; duplicados = **0**; desfase de envío ≤ **±15 min** sobre el objetivo (T-24h / T-2h) | SUPUESTO (±15 min), invariante (resto) | PRD Backend:170-171. 15 min es tolerable para un recordatorio de 24 h o 2 h. |
| S10 | Saturación del pool (concurrencia = 3× `max_size`) | Ningún request espera más de **5 s** por conexión (debe fallar rápido con 503, no colgarse); recuperación a S1 **< 30 s** después de bajar la carga | SUPUESTO | Hoy `acquire()` no tiene timeout (H7), así que el resultado esperado es que los requests se cuelguen. |
| S11 | Rate limit | Login: ≤ **10 intentos/min por IP** y luego 429; webhooks: 429 por encima del límite; sin secretos configurados → 503/404 (fail closed) | SUPUESTO (10/min) | Protección contra fuerza bruta. bcrypt hace cara cada petición. |
| S12 | Soak de 60 min a 50 % del pico (10 msg/s) | RSS: crecimiento < **10 %** entre el minuto 10 y el 60; conexiones de PG ≤ `max_size × workers`; `len(_bg_tasks)` vuelve a 0 al drenar; descriptores de archivo estables (±5 %) | SUPUESTO | Detecta fugas de tareas, de `httpx.AsyncClient` o de conexiones. |
| S13 | Reinicio del backend bajo carga | Citas duplicadas = **0**; mensajes inbound con ACK 200 que no quedan en `messages` = **0**; el servicio vuelve a S1 en < **60 s** | Invariante (0); SUPUESTO (60 s) | H14 indica que hoy se pierden mensajes. |

---

## 2. Escenarios

Formato fijo por escenario: **Objetivo · Entrada · Carga · Entorno simulado · Éxito/Falla · Riesgo validado · Predicción**.

Arnés común (se crea en la fase de implementación, **no existe todavía**; necesita autorización porque hoy está prohibido tocar `tests/`):
- `backend-lang/tests/stress/` con `conftest.py`. Reutiliza los dobles que ya existen: `FakeLLM` (`tests/test_appointment_agent.py:25`), el patrón `httpx.MockTransport` (`tests/test_kapso_outbound.py`) y el fixture de BD desechable de `tests/test_migrations_integration.py:17-29`.
- `backend-lang/tests/stress/run_server.py`: arranca uvicorn **en proceso** después de aplicar los dobles (ver §4.3). Así las pruebas HTTP con k6/locust nunca llegan a Meta, Google, Kapso ni Anthropic.

### E1 — Ráfaga de webhooks válidos + dedup
- **Objetivo:** cumplir S1/S2/S3 a ritmo de pico y comprobar que los reintentos con la misma clave o `wamid` no se procesan dos veces.
- **Entrada:** payloads Meta (`entry[].changes[].value.messages[]` con `from`, `text.body`, `id`=wamid y `metadata.phone_number_id` de un canal sembrado), firmados con el `WHATSAPP_APP_SECRET` de prueba. Payloads Kapso firmados con el secreto del canal sembrado (cifrado con `KAPSO_SECRETS_KEY` de prueba). Para dedup: el 20 % de los requests repite un `wamid` / `X-Idempotency-Key` ya enviado.
- **Carga:** rampa 1 → 20 msg/s en 2 min, 20 msg/s durante 5 min y pico de 50 msg/s durante 1 min. Hasta 200 VUs. Dos variantes: (a) un emisor (una IP), como Meta real; (b) 50 IPs/keys distintas.
- **Entorno:** server en proceso (§4.3), PG desechable, LLM falso (latencia 1 s), WhatsApp de salida y Google falsos.
- **Éxito:** S1, S2 y S3. Al drenar, `COUNT(messages inbound)` = número de wamid/keys únicos enviados.
- **Falla:** p95 > 300 ms, 5xx ≥ 0,1 %, cualquier wamid/key con más de una fila inbound o más de un `agent_run`.
- **Riesgo:** H1, H3, H4.
- **Predicción:** Kapso dedup pasa. **Meta dedup: ESPERADO FAIL (H1).** Variante (a): **ESPERADO 429 a partir de ~3,3 msg/s** por proceso (H4). Es un hallazgo de capacidad: Meta reintentaría.

### E2 — Firma inválida / cuerpo sobredimensionado en ráfaga
- **Objetivo:** S4. Rechazar rápido y sin consumir memoria ni BD.
- **Entrada:** cinco tipos de request mezclados: firma ausente, firma incorrecta, firma con caracteres no ASCII, cuerpo de 1 MB + 1 B con `Content-Length` real, y cuerpo de 5 MB enviado en chunks sin `Content-Length`. Se envían a `/webhooks/whatsapp`, `/webhooks/kapso`, `/webhooks/kapso/n/{token}` y a `/webhooks/google-calendar`, este último sin token.
- **Carga:** 200 req/s durante 2 min y 10 conexiones lentas (slowloris, 1 B/s) en paralelo. En simultáneo, 5 msg/s válidos para medir el impacto sobre el tráfico legítimo.
- **Entorno:** el mismo que E1.
- **Éxito:** 401 (Kapso) / 403 (Meta) / 413 en p95 < 50 ms; el tráfico válido sigue cumpliendo S1; delta de RSS < 50 MB; 0 filas nuevas en `messages`/`kapso_webhook_events` por los requests inválidos.
- **Falla:** 5xx, cualquier fila escrita o tráfico legítimo fuera de S1.
- **Riesgo:** H2, H16.
- **Predicción:** Kapso pasa (ya tiene tests unitarios). **Meta 413: ESPERADO FAIL (H2)**: bufferiza todo el cuerpo antes de verificar la firma. **Google Calendar: ESPERADO FAIL de seguridad (H16)**: acepta cualquier request y lanza tareas de sync.

### E3 — Carrera de reserva del mismo slot
- **Objetivo:** S5. Exactamente una cita confirmada.
- **Entrada:** 1 workspace, 1 servicio de 30 min, 1 calendario activo y N clientes distintos con su conversación.
- **Carga:** N = 2, 10 y 50 llamadas concurrentes (`asyncio.gather` con una barrera `asyncio.Event` para que salgan a la vez) a `create_appointment` (`src/api/routes/appointments.py`), tanto directo como por la tool `crear_cita`. 20 repeticiones por cada N (las carreras son probabilísticas).
- **Entorno:** PG desechable **real** (la carrera vive en la BD). Doble de Google con estado: `freebusy` responde según los eventos ya insertados en el doble y `events.insert` añade un evento con 50 ms de latencia simulada. **No se usa `FakeDB`.**
- **Éxito:** por repetición, `SELECT count(*) FROM appointments WHERE calendar_id=$1 AND status='confirmed' AND tstzrange(start_at,end_at) && tstzrange($2,$3)` = 1, y eventos en el doble = 1. El resto recibe 409 y el agente responde `NOT_BOOKED`, nunca una confirmación.
- **Falla:** conteo > 1 en cualquier repetición, o eventos en el doble > citas (huérfanos).
- **Riesgo:** H5 (TOCTOU) y H6 (con el bloqueo síncrono la carrera queda serializada por accidente; el doble debe usar `await asyncio.sleep` para **no** ocultarla).
- **Predicción:** **ESPERADO FAIL (H5)**. Esto bloquea el lanzamiento (§6).

### E4 — Concurrencia del agente
- **Objetivo:** S6. Aislamiento entre conversaciones y ninguna corrida colgada.
- **Entrada:** M conversaciones en K workspaces (M = 10, 50, 100; K = 10) con un guion `FakeLLM` de 3 pasos: `listar_servicios` → `consultar_disponibilidad` → `crear_cita` en slots **distintos**.
- **Carga:** M corridas simultáneas de `AgentService.run`. Latencia del LLM falso de 1,5 s por `ainvoke`. Errores inyectados: el 10 % lanza excepción, el 5 % excede `TIMEOUT_S` (se parchea a 3 s para la prueba) y el 5 % pide más de 5 tools.
- **Entorno:** PG desechable, `FakeLLM` (`_get_llm` parcheado), Google falso asíncrono, WhatsApp de salida falso que registra `(to, text, phone_number_id)`.
- **Éxito:** S6; cada mensaje saliente va al `customer_phone` de **su** conversación (0 cruces); `workspace_id` de cada cita = el de su contexto; corridas con error → `status='error'` + 1 alerta; las de timeout no confirman.
- **Falla:** cruce de conversación o workspace, una corrida en `running` tras drenar o una confirmación sin cita en BD.
- **Riesgo:** estado compartido entre corridas, H8 y H19. Nota: el PRD pide un grafo LangGraph (`documentation/PRD del Agente LangGraph.md`), pero hoy es un bucle de tools (H18). El escenario prueba lo que existe.
- **Predicción:** debería pasar con el Google falso asíncrono. Con el Google falso **síncrono** (fiel a H6) se espera que el p95 crezca linealmente con M.

### E5 — Google Calendar lento o con 429/5xx
- **Objetivo:** S7. Google degradado no puede tumbar los webhooks; hay reintento con backoff y no se duplican eventos.
- **Entrada:** el tráfico de E1 a 10 msg/s, donde el 30 % de las conversaciones llega a `consultar_disponibilidad` / `crear_cita`.
- **Carga:** cuatro fases de 3 min con el doble de Google configurado como (a) latencia de 5 s, (b) 429 con `Retry-After: 2`, (c) 503, (d) timeout de 30 s.
- **Entorno:** doble de `build_calendar_client` que imita la interfaz `googleapiclient` (`.freebusy().query().execute()`, `.events().insert().execute()`). **El `execute()` del doble es síncrono y usa `time.sleep`**, para reproducir fielmente H6. Variante de control con `run_in_executor` para cuantificar la mejora si se corrige.
- **Éxito:** S1 y S7 se cumplen durante las 4 fases; cada fallo de Calendar → la cita no se registra (503), no hay confirmación y queda alerta; reintentos ≤ 3 con backoff creciente; en el doble, `events.insert` exitosos = citas en BD.
- **Falla:** ACK p95 > 300 ms, health p95 > 200 ms, una confirmación sin evento o un evento sin cita.
- **Riesgo:** H6, H7, H8; PRD Final:87 ("Reintentos con backoff").
- **Predicción:** **ESPERADO FAIL** en (a) y (d) por bloqueo del loop (H6). Los reintentos y el backoff no existen.

### E6 — Meta/Kapso caído o con 429 en el envío
- **Objetivo:** S8.
- **Entrada:** el tráfico de E1 a 10 msg/s, con un 50 % de canales `provider='kapso'` y un 50 % Meta.
- **Carga:** fases de 3 min: Kapso 429 con `Retry-After`, Kapso 500 persistente, Kapso timeout, conexión rehusada; Meta 429, Meta 500 y Meta timeout.
- **Entorno:** Kapso → stub HTTP local mediante `KAPSO_BASE_URL=http://127.0.0.1:<puerto_stub>`. Meta → `WhatsAppService.send_message` parcheado con un transporte simulado (H17 impide redirigir por URL). Bloqueo de egress como red de seguridad (§4.3).
- **Éxito:** S8. Inbound guardado = enviados únicos. Por cada fallo: `agent_runs.status='error'` y 1 alerta; 0 `messages` outbound para envíos fallidos; el stub de Kapso no recibe más de `1 + max_retries` intentos por mensaje.
- **Falla:** un outbound guardado sin entrega, un inbound perdido, reintentos sin tope o un 5xx en el ACK.
- **Riesgo:** H11, H13 y el contrato `agent_service.py:85-87`.
- **Predicción:** el camino del agente pasa (ya hay tests unitarios). Meta no reintenta (H13): es un hallazgo, no un fallo del SLO. Los recordatorios por canal Kapso salen por Meta (H11): **ESPERADO FAIL** de correctitud.

### E7 — Recordatorios masivos
- **Objetivo:** S9.
- **Entrada:** N = 200 workspaces con canal activo y M = 2 000 citas `confirmed` repartidas uniformemente en [ahora+23h, ahora+25h] y [ahora+1h, ahora+3h]. El 10 % de los clientes tiene email.
- **Carga:** (a) `run_reminders()` invocado como lo haría el scheduler: cada 30 min de reloj simulado, durante 2 h simuladas (se congela `datetime.now` del módulo); (b) **dos instancias concurrentes** de `run_reminders()` sobre la misma BD, que simulan `--workers 2`.
- **Entorno:** PG desechable + migraciones. Pre-requisito: las columnas `reminder_24h_sent` / `reminder_2h_sent` (H12) deben existir; si no, se registra como fallo de esquema y E7 queda **bloqueado**. WhatsApp falso registra cada envío y `EmailService` está parcheado (sin Resend real).
- **Éxito:** cada cita recibe exactamente 1 recordatorio 24h y 1 de 2h, dentro de ±15 min del objetivo; 0 duplicados en (b); un ciclo de 2 000 citas termina en < 5 min (SUPUESTO).
- **Falla:** cualquier cita sin recordatorio, cualquier duplicado, envío por el proveedor equivocado (H11) o cita marcada como enviada sin envío.
- **Riesgo:** H9, H10, H11, H12.
- **Predicción:** **ESPERADO FAIL** en cobertura (H10, ~33 %) y duplicados (H9). Bloquea el lanzamiento.

### E8 — Saturación del pool de PostgreSQL
- **Objetivo:** S10.
- **Entrada:** mezcla de 70 % webhook Kapso (1 `acquire` en request y varios en background) y 30 % `GET /appointments` autenticado (JWT de prueba).
- **Carga:** concurrencia de 10, 30 y 60 VUs (1×, 3× y 6× `max_size=10`) durante 3 min cada una y 2 min de enfriamiento a 2 VUs. Variante: fijar `max_connections=20` en PG para provocar un rechazo del servidor.
- **Entorno:** server en proceso con **1 worker** (para atribuir el pool) y luego con 2. PG desechable. Google falso con 2 s de latencia síncrona para reproducir H7.
- **Éxito:** S10. Métricas: `pg_stat_activity` por `application_name`, tiempo de espera de `acquire` (instrumentado en el arnés), 5xx y latencia de recuperación.
- **Falla:** requests colgados > 5 s sin respuesta, conexiones que no vuelven o no se recupera en 30 s.
- **Riesgo:** H7 y la ausencia de timeout en `acquire()` (`database.py:24`).
- **Predicción:** **ESPERADO FAIL** (cuelgues en lugar de 503).

### E9 — Rate limit de auth y webhooks (fail closed)
- **Objetivo:** S11.
- **Entrada:** `POST /auth/login` con un usuario sembrado y contraseña incorrecta; webhooks con firma válida por encima de su límite; arranques con secretos vacíos.
- **Carga:** login: 50 req/s durante 1 min desde una IP y desde 20 IPs. Webhook Meta: 300 req/min con y sin `X-Workspace-ID` rotativo. Kapso: 400 req/min por IP.
- **Entorno:** server en proceso, 1 y 2 workers.
- **Éxito:** login → 429 después del umbral; Meta/Kapso → 429 por encima de su límite, **y rotar `X-Workspace-ID` no evita el límite**; con `WHATSAPP_APP_SECRET` vacío → 503; con `KAPSO_ENABLED=true` sin secretos → no arranca; con 2 workers el límite efectivo es ≤ 1,1× el nominal.
- **Falla:** login sin 429, bypass por header, límite efectivo multiplicado por el número de workers o un 200 con secretos vacíos.
- **Riesgo:** H4 y H15.
- **Predicción:** **ESPERADO FAIL**: login sin límite (H15), bypass por `X-Workspace-ID` (H4) y límite ×2 con 2 workers.

### E10 — Soak
- **Objetivo:** S12.
- **Entrada:** la mezcla de E1 (Meta + Kapso) + 5 % de requests del panel + recordatorios activos.
- **Carga:** 10 msg/s constantes durante **60 min** (mínimo aceptable: 30 min).
- **Entorno:** el de E1, con 2 workers como en producción (`Dockerfile:21`).
- **Éxito:** S12. Muestreo cada 30 s de: RSS por PID (`ps -o rss`), número de descriptores (`ls /proc/<pid>/fd | wc -l`), conexiones en `pg_stat_activity`, `len(webhooks._bg_tasks)` y `len(asyncio.all_tasks())` (vía un endpoint de diagnóstico que **solo existe en el arnés**) y p95 por ventana de 5 min.
- **Falla:** pendiente de RSS > 10 % entre el minuto 10 y el 60, fds o conexiones crecientes, o un p95 que se degrada más de un 30 % entre la primera y la última ventana.
- **Riesgo:** H3, un `httpx.AsyncClient` nuevo por envío (`whatsapp_service.py:74`, `whatsapp_provider.py:79`) y fugas de tareas.
- **Predicción:** no se puede predecir con fiabilidad leyendo el código.

### E11 — Caída y recuperación bajo carga
- **Objetivo:** S13.
- **Entrada:** la mezcla de E1 a 10 msg/s + E3 (N = 10) disparado en el segundo 30.
- **Carga:** `SIGTERM` al proceso uvicorn en t = 60 s, rearranque inmediato; luego `SIGKILL` en t = 180 s y rearranque. Duración total de 5 min.
- **Entorno:** server en proceso supervisado por el script de la prueba. PG desechable persistente entre reinicios. Los emisores de Meta y Kapso simulados **reintentan** lo que no recibió 2xx, igual que los reales.
- **Éxito:** S13. Se reconcilia `enviados con 2xx` contra `messages inbound` y contra `agent_runs`. 0 citas duplicadas, 0 eventos huérfanos, 0 `agent_runs` en `running` 2 min después del rearranque y 0 claves en `kapso_webhook_events` sin procesar.
- **Falla:** cualquier mensaje con 2xx que no esté en `messages`, una cita duplicada o un run colgado.
- **Riesgo:** H14 y el `lifespan` (`main.py:46-55`): el apagado no espera a `_bg_tasks`.
- **Predicción:** **ESPERADO FAIL** en pérdida de mensajes (H14) y runs `running` huérfanos.

---

## 3. Herramientas recomendadas (instalación a nivel usuario, sin root)

| Herramienta | Uso | Por qué | Instalación sin root |
|---|---|---|---|
| **k6** | E1, E2, E8, E9, E10 (HTTP) | Binario único, umbrales declarativos (`thresholds`) que dan exit code ≠ 0 si se viola un SLO, firma HMAC con `k6/crypto` y salida JSON parseable. | Descargar el tarball de la release oficial de GitHub (`grafana/k6`), extraerlo y copiar `k6` a `~/.local/bin/`. No hace falta paquete del sistema. Verificar con `k6 version`. |
| **pytest + pytest-asyncio** (ya están en `[dependency-groups].dev`, `pyproject.toml`) | E3, E4, E5, E6, E7 y la reconciliación de E11 | La carrera y la lógica de reintentos se prueban mejor en proceso, con barreras de `asyncio` y aserciones sobre PG real. | `uv sync --group dev` dentro de `backend-lang/` (se instala en `.venv`, sin root). |
| **httpx.MockTransport** (ya disponible) | Doble de Kapso/Meta en proceso | Es el patrón que ya usan `tests/test_kapso_outbound.py` y `tests/test_kapso.py`. No añade dependencias. | Nada que instalar. |
| **Stub HTTP local de Kapso** (FastAPI + uvicorn, ya instalados) | E6, E10, E11 | Permite probar el server real por `KAPSO_BASE_URL` con 429/5xx/timeout programables. | `backend-lang/tests/stress/kapso_stub.py` (a crear). |
| **Doble de Google** | E3, E5 | Imita `googleapiclient` (`freebusy().query().execute()`, `events().insert().execute()`) con estado, latencia e inyección de errores. Se inyecta parcheando `integrations.google_calendar.build_calendar_client`. | Código del arnés, sin dependencias. |
| **FakeLLM** (existe en `tests/test_appointment_agent.py:25`) | E1, E4–E11 | Evita llamar a Anthropic. Se extiende con latencia y errores configurables. | Nada que instalar. |
| **locust** (alternativa a k6) | Solo si se prefiere Python para la lógica de dedup y reconciliación | Escenarios en Python, pero exige más CPU por VU que k6. | `uv tool install locust` (va a `~/.local/bin`). |
| **Docker** (`/usr/bin/docker` existe) | PG desechable | Versión de PG fija y destrucción limpia. Si el usuario no está en el grupo `docker` no se puede usar sin root: **no verificado**. | Ya instalado. Alternativa sin Docker en §4.1. |

No se recomienda Toxiproxy ni chaos tooling: los fallos de los dependientes se inyectan en los dobles, que es más barato y determinista.

---

## 4. Entorno

### 4.1 PostgreSQL desechable
- **Versión:** el `Dockerfile` del backend no incluye PostgreSQL (`backend-lang/Dockerfile:5` es `python:3.12-slim`) y `docker-compose.yml` no tiene servicio de BD. Producción es Supabase y su versión de PG está **no verificada**. **SUPUESTO:** PostgreSQL 15 (versión común en Supabase). El usuario debe confirmarlo mirando *Project Settings → Infrastructure* de Supabase.
- **Levantar (opción A, Docker):**
  ```bash
  docker run -d --name citas-stress-pg --rm -e POSTGRES_USER=stress -e POSTGRES_PASSWORD=stress \
    -e POSTGRES_DB=citas_stress -p 127.0.0.1:55432:5432 --tmpfs /var/lib/postgresql/data \
    postgres:15 -c max_connections=100
  ```
  `--tmpfs` + `--rm` hacen que al parar no quede nada. El puerto solo escucha en loopback.
- **Levantar (opción B, sin Docker ni root):** `micromamba create -p ~/.local/pg15 -c conda-forge postgresql=15`, luego `initdb -D /tmp/citas-stress-pg` y `pg_ctl -D /tmp/citas-stress-pg -o "-p 55432 -k /tmp" start`. Destruir con `pg_ctl ... stop` y `rm -rf /tmp/citas-stress-pg`.
- **Esquema:** igual que `tests/test_migrations_integration.py:21-27`: se recrean `public` y `auth`, se simula `auth.uid()` (estado actual del test; RLS retirado por D-U6, el arnés no verifica RLS) y se aplican `migrations/001..005`. **Gap:** las columnas de recordatorio no están en las migraciones (H12). E7 necesita una migración de prueba o la confirmación del esquema real.
- **Destruir:** `docker stop citas-stress-pg` (con `--rm` se borra el contenedor y el tmpfs).
- **Guardia de seguridad:** el arnés debe abortar si `TEST_DATABASE_URL` no apunta a `127.0.0.1`/`localhost` o si el nombre de BD no contiene `stress` o `test`. Así nunca se recrean schemas en Supabase.

### 4.2 Variables de prueba (solo nombres; los valores los genera el arnés al arrancar y son descartables)

| Variable | Valor en pruebas |
|---|---|
| `TEST_DATABASE_URL`, `DATABASE_URL` | Ambas apuntan a la BD desechable de §4.1 |
| `JWT_SECRET` | Aleatorio por corrida (`secrets.token_urlsafe`) |
| `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN` | Aleatorios por corrida |
| `WHATSAPP_API_TOKEN` | Literal ficticio (`test-not-a-token`) |
| `WHATSAPP_PHONE_NUMBER_ID` | Ficticio |
| `KAPSO_ENABLED` | `true` en E1/E2/E6, `false` en su variante |
| `KAPSO_API_KEY`, `KAPSO_WEBHOOK_SECRET_PROJECT` | Ficticios |
| `KAPSO_SECRETS_KEY` | `Fernet.generate_key()` por corrida |
| `KAPSO_BASE_URL` | `http://127.0.0.1:<puerto_stub>` |
| `GOOGLE_ENCRYPTION_KEY` | `Fernet.generate_key()`; `GOOGLE_CLIENT_ID/SECRET` vacíos |
| `RESEND_API_KEY`, `SENTRY_DSN`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` | **Vacías o sin definir** |
| `HTTPS_PROXY`, `HTTP_PROXY` | `http://127.0.0.1:9` (puerto muerto). `NO_PROXY=127.0.0.1,localhost` |

**Riesgo de `.env`:** `config.py:89` carga `.env` y `.env.local`, y `main.py:1-2` llama a `load_dotenv()`. `backend-lang/.env` existe y puede tener credenciales reales. El arnés **debe** arrancar con `cwd` fuera de `backend-lang/` o con las variables exportadas antes (pydantic-settings da prioridad al entorno sobre `.env`, y `load_dotenv` no sobreescribe por defecto). Además debe verificar al arrancar que `get_settings().database_url == TEST_DATABASE_URL`, y abortar si no coincide.

### 4.3 Garantía de "cero tráfico real"
Hay tres capas, porque el URL de Meta está fijo en el código (H17):
1. **Parches en proceso** (`run_server.py`, antes de `uvicorn.run`): `appointment_agent._get_llm` → FakeLLM; `integrations.google_calendar.build_calendar_client` → doble de Google; `WhatsAppService.send_message` / `send_template` → transporte simulado; `EmailService.send_appointment_reminder` → registro en memoria.
2. **Proxy muerto** (`HTTPS_PROXY=http://127.0.0.1:9`): httpx respeta las variables de proxy (`trust_env=True` por defecto) y httplib2 (googleapiclient) las lee del entorno. Cualquier fuga falla con `ConnectError` en lugar de salir a internet. Que httplib2 respete el proxy en la versión instalada está **no verificado**; por eso existe la capa 1.
3. **Preflight obligatorio:** antes de cada escenario se ejecuta `python -c "import httpx; httpx.get('https://graph.facebook.com', timeout=3)"` con el mismo entorno, **y debe fallar**. Si responde, la campaña se aborta.

---

## 5. Mapa de cobertura actual (`backend-lang/tests/`)

Ningún test actual mide carga, concurrencia ni latencia. Toda la cobertura es funcional y de un solo request. `test_agent_whatsapp_delivery.py` y `test_whatsapp_security.py`, citados en `documentation/QA - Kapso onboarding y booking.md:12`, **no existen** hoy en `tests/`.

| Escenario | Cobertura parcial existente | Qué falta |
|---|---|---|
| E1 | `test_kapso.py::test_same_idempotency_key_processed_once`, `test_kapso_number_webhooks.py::test_route_same_idempotency_key_processed_once`, `test_migrations_integration.py::test_idempotency_upsert_second_attempt_exists`, `test_kapso_number_webhooks.py::test_route_valid_signature_processes`, `test_kapso.py::test_valid_signature_accepted` | Ráfaga, latencia, dedup concurrente (dos requests con la misma clave a la vez contra PG real) y **todo el dedup por wamid de Meta (no implementado)** |
| E2 | `test_kapso.py::test_invalid_signature_rejected`, `::test_missing_signature_rejected`, `::test_non_ascii_signature_401_not_500`, `::test_body_over_1mb_413_before_signature`, `::test_signature_with_wrong_secret_rejected`, `::test_meta_signature_header_not_accepted`, `::test_meta_non_ascii_signature_rejected_not_500`; `test_kapso_number_webhooks.py::test_route_invalid_signature_401`, `::test_route_body_over_1mb_413`, `::test_route_non_ascii_signature_401` | Ráfaga, slowloris, memoria, 413 de Meta (no implementado) y autenticación de `/webhooks/google-calendar` |
| E3 | `test_appointment_agent.py::test_fallo_en_bd_no_confirma` (solo que no confirme si falla la BD) | **Nada** sobre carrera ni solapamiento |
| E4 | `test_appointment_agent.py::test_lista_y_crea_cita_envia_confirmacion`, `::test_limite_de_5_herramientas`, `::test_workspace_id_no_sobrescribible`, `::test_llm_no_disponible_fallback_y_alerta` (una conversación, `FakeDB`) | Concurrencia, aislamiento entre conversaciones y PG real |
| E5 | — | **Nada** (Calendar sin tests ni reintentos) |
| E6 | `test_kapso_outbound.py::test_kapso_429_then_ok`, `::test_kapso_500_exhausted_is_failure`, `::test_kapso_400_no_retry`, `::test_kapso_without_key_not_sent`, `::test_run_send_failure_marks_error_and_no_outbound`, `::test_run_send_ok_saves_wamid`; `test_kapso.py::test_provider_timeout`, `::test_provider_429_retries_then_succeeds`, `::test_provider_429_bounded_retries`, `::test_provider_rejection_not_delivered`, `::test_failed_processing_releases_key_and_retry_processes`; `test_kapso_number_webhooks.py::test_route_failed_processing_releases_key_and_retry_processes` | Carga, Meta 429/5xx y proveedor de los recordatorios |
| E7 | — | **Nada** (`reminder_worker` sin tests) |
| E8 | — | **Nada** |
| E9 | `test_kapso.py::test_rate_limit_429`, `test_kapso_number_webhooks.py::test_route_rate_limit_429`; fail closed: `test_kapso.py::test_meta_empty_secret_503_even_with_empty_key_signature`, `::test_config_requires_secrets_when_enabled`, `::test_disabled_returns_404`, `test_kapso_number_webhooks.py::test_route_disabled_404`, `test_kapso_onboarding.py::test_route_disabled_is_404_even_without_auth` | Rate limit de login (no implementado), bypass por `X-Workspace-ID` y límite con varios workers |
| E10 | — | **Nada** |
| E11 | Parcial lógico: `test_kapso_number_webhooks.py::test_kapso_failure_releases_claim_and_leaks_nothing` (liberar la clave si falla) | Reinicio real del proceso y reconciliación |

Nombres verificados con grep de `def test_` sobre `backend-lang/tests/*.py` en `f0e97b0`. Estado pass/fail: **no verificado** en esta corrida (no se ejecutaron tests, por instrucción).

---

## 6. Criterios de aceptación de la campaña

**Campaña PASS** = todos los escenarios BLOQUEANTE cumplen sus SLO en 3 corridas consecutivas (E3: 20 repeticiones por N), con evidencia completa (§7).

| Gate | Escenarios | Si falla |
|---|---|---|
| **BLOQUEANTE** (no hay lanzamiento) | E3 (doble reserva), E7 (recordatorios faltantes o duplicados), E11 (pérdida de mensajes / duplicados al reiniciar), E1-dedup (S3), E2 (413/401 en Meta y Kapso), E6 (S8: outbound falso o inbound perdido), E9-login (S11) | Se detiene el lanzamiento. Se abre corrección y se repite la campaña completa del escenario y de sus dependientes. |
| **BLOQUEANTE con umbral** | E1 latencia (S1/S2), E5 (S7), E8 (S10) | Bloquea si el SLO confirmado por el usuario no se cumple. Si el usuario baja el pico SUPUESTO (§1), se re-evalúa con el nuevo número. |
| **PILOTO** (permite un piloto de 1–3 workspaces, no la apertura general) | E4, E10, E9-webhooks (bypass del header / multi-worker) | Se permite el piloto con monitoreo y se corrige antes de abrir a más workspaces. |

Reglas:
- Un escenario marcado `ESPERADO FAIL` que **pasa** también se investiga: puede que el doble esté ocultando el problema (p. ej. un Google síncrono serializando E3).
- Si un preflight de §4.3 falla, la corrida se **invalida** (no cuenta ni como pass ni como fail).
- Los resultados de una corrida que tocó un servicio externo real se descartan y se reporta el incidente.

---

## 7. Orden de ejecución y responsable

**Ejecuta:** Claude Code (agente reviewer/QA). **No** Hermes. Ningún paso se ejecuta hasta que el usuario apruebe este plan, los SUPUESTOS de §1 y la creación de `backend-lang/tests/stress/`.

| Paso | Qué | Motivo del orden |
|---|---|---|
| 0 | Preflight: PG desechable arriba, guardia de URL (§4.1), proxy muerto verificado (§4.3), `get_settings().database_url` = BD de prueba, baseline de `pytest -q` | Sin un entorno seguro no se corre nada |
| 1 | E2 | El más barato. Valida que el arnés firma bien y rechaza mal |
| 2 | E9 | Conocer los límites antes de dimensionar la carga |
| 3 | E1 | Baseline de latencia del ACK |
| 4 | E3 | Bloqueante de negocio. No necesita HTTP |
| 5 | E4 | Agente en concurrencia, en proceso |
| 6 | E6 | Fallos de salida sobre la base de E1 y E4 |
| 7 | E5 | Fallos de Google sobre la base de E1 y E4 |
| 8 | E8 | Necesita E1 y E5 para interpretar el efecto del bloqueo del loop |
| 9 | E7 | Independiente, pero depende del esquema (H12) |
| 10 | E11 | Necesita todo lo anterior para reconciliar |
| 11 | E10 | El más largo, al final, con el sistema ya caracterizado |

Comandos previstos (los paths `tests/stress/*` **no existen todavía**):
```bash
# Paso 0
docker run -d --name citas-stress-pg --rm ... postgres:15            # ver §4.1
cd /opt/data/proyectos/citas-ia/backend-lang
PYTHONPATH=src uv run --group dev pytest -q; echo "exit=$?"
TEST_DATABASE_URL=... PYTHONPATH=src uv run --group dev pytest -q tests/test_migrations_integration.py; echo "exit=$?"
# Escenarios en proceso (E3, E4, E5, E6, E7)
TEST_DATABASE_URL=... PYTHONPATH=src uv run --group dev pytest -q tests/stress/test_e3_race.py -p no:cacheprovider; echo "exit=$?"
# Escenarios HTTP (E1, E2, E8, E9, E10)
PYTHONPATH=src uv run --group dev python tests/stress/run_server.py --workers 1 --port 18000 &
k6 run --summary-export=stress-out/e1.json tests/stress/k6/e1_burst.js; echo "exit=$?"
# Destrucción
docker stop citas-stress-pg; echo "exit=$?"
```

**Formato obligatorio del reporte** (`specs/003-producto-final-citas/pruebas-estres-resultados.md`, una sección por escenario):
1. HEAD exacto (`git rev-parse HEAD`) y `git status --short`.
2. Versiones: `python --version`, `uv --version`, `k6 version`, `SELECT version()` de PG.
3. Preflight: comando, salida literal y exit code (debe ser ≠ 0 para el egress).
4. Por escenario: **comando exacto**, **salida literal** (sin resumir; si pasa de 200 líneas, adjuntarla en `stress-out/` y citar la ruta), **exit code**, tabla SLO → valor medido → PASS/FAIL y consultas SQL de reconciliación con su resultado literal.
5. Hallazgos H1–H19: confirmado / refutado / no ejecutado, con evidencia.
6. Destrucción del entorno: comando y exit code.
7. Variables: **solo nombres**. Prohibido imprimir valores, aunque sean de prueba. Las salidas se filtran por los nombres de §4.2 antes de pegarlas.

---

## Pendiente de confirmación del usuario

1. El perfil de carga (§1): 200 workspaces, 20 msg/s de pico y 2 000 citas/día.
2. Los valores SUPUESTO de S1, S4, S6, S9 (±15 min), S10, S11 (10/min), S12 y S13.
3. La versión de PostgreSQL de Supabase (SUPUESTO: 15).
4. Si existen `reminder_24h_sent` / `reminder_2h_sent` en la BD real (H12).
5. La autorización para crear `backend-lang/tests/stress/` (arnés, dobles y scripts k6).
6. Si `docker` se puede usar sin root en la máquina de ejecución (no verificado).
