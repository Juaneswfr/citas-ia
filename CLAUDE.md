.constitution/front.md                 # Frontend React
.constitution/backend.md               # Backend Express o FastAPI
.constitution/database.md              # Base de datos / ORM / queries

# Zumit (agente: Hilo)

La plataforma se llama **Zumit**; el agente conversacional se llama **Hilo**. Los identificadores técnicos (plantillas `hilo_*_v1`, `sent_via='hilo'`, carpetas `hilo`) conservan el nombre antiguo.

SaaS multi-tenant de citas por WhatsApp para cualquier negocio que atienda con cita: barberías, salones, spas, consultorios, veterinarias, etc. (ver «Tipos de negocio»).
Backend FastAPI + LangGraph en `backend-lang/`, front TanStack Start en `front/`, datos en PostgreSQL (servidor propio, sin Supabase).

## Desarrollo local

```bash
# Backend
cd backend-lang
uv run fastapi dev ./src/api/main.py --port 9001   # http://localhost:9001

# Frontend
cd front
npm run dev                                         # http://localhost:8001
```

Puertos locales: front **8001** (fijado en el script `dev` de `front/package.json`), backend **9001** (va en el comando; `front/.env.development` apunta `VITE_API_URL` ahí). Producción no cambia (3000/8000 dentro de Docker).

No tocar los Dockerfiles — son la configuración actual de producción.

## Producción (VPS)

YA ESTAN CORRIENDO EN PRODUCCION https://zumit.app/ (el dominio antiguo `hilo.esjuanez.com` sigue como alias en nginx solo durante la migración; retirarlo de `server_name` cuando Google, Meta y Kapso ya apunten a zumit.app)

```bash
git pull && docker compose up --build -d
```

- Frontend: multi-stage Dockerfile (bun install + npm run build → Nitro SSR en node:20-alpine)
- Backend: Python 3.12 slim + uv, código montado como volumen
- Nginx: reverse proxy interno en puerto 7000, Apache del host maneja SSL. Resuelve `frontend` y `backend` en cada petición (variables en `proxy_pass`, no bloques `upstream`), así sobrevive a que esos contenedores cambien de IP. Un cambio en `nginx/nginx.conf` no se aplica con `up -d`: hay que correr `docker compose restart nginx`.

### Env files requeridos en el server

- `backend-lang/.env` — DATABASE_URL, JWT_SECRET, KAPSO_*, ANTHROPIC_API_KEY, etc.
- `front/.env` — DATABASE_URL, JWT_SECRET, VITE_API_URL, VITE_META_APP_ID, VITE_META_EMBEDDED_SIGNUP_CONFIG_ID
- `UPLOADS_DIR` (opcional): ya la fija `docker-compose.yml` a `/app/uploads`; en local por defecto es `backend-lang/uploads`.

---

## Regla de corrección proactiva

Cuando en cualquier sesión se encuentre código que viola la constitución o las decisiones documentadas aquí, **corregirlo en el mismo contexto** sin esperar que el usuario lo pida, siempre que:
- El scope del arreglo sea menor que la tarea principal, y
- No rompa comportamiento en producción.

Documentar el arreglo en el log de cambios al final de la sesión.

---

## Base de datos — patrón establecido

Cumple `database.md`. El backend usa **SQLAlchemy 2.0 async** con driver asyncpg.

- Engine: `create_async_engine("postgresql+asyncpg://...")` en `core/database.py`
- Sesión: `AsyncSession` vía `async_sessionmaker` → `get_db()` como dependencia FastAPI
- Queries: `text()` para SQL existente; ORM para código nuevo simple
- Writes: `await db.commit()` tras cada mutación (o `async with db.begin():` para transacciones)
- Migraciones: SQL directo en `backend-lang/migrations/` — `core/migrations.py` y `migrate.py` mantienen asyncpg (son herramientas de dev, no runtime)
- `models.py`: solo para referencia/Alembic autogenerate, no lo usa el runtime

Patrón de query:
```python
# Lectura
rows = (await db.execute(text("SELECT ... WHERE x = :x"), {"x": val})).mappings().fetchall()
row  = (await db.execute(text("SELECT ... WHERE x = :x"), {"x": val})).mappings().fetchone()
val  = (await db.execute(text("SELECT ... WHERE x = :x"), {"x": val})).scalar_one_or_none()
# Escritura
await db.execute(text("UPDATE ..."), {...})
await db.commit()
```

Para servicios fuera del contexto FastAPI (background tasks):
```python
from core.database import AsyncSessionLocal
async with AsyncSessionLocal() as session:
    rows = (await session.execute(text("..."), {...})).mappings().fetchall()
    await session.commit()  # solo si hay writes
```

---

## Arquitectura del agente

El agente de citas (`backend-lang/src/services/appointment_agent.py`) usa Claude Haiku 4.5 con estas tools:

| Tool | Función |
|------|---------|
| `listar_profesionales` | Lista quienes atienden (barberos, doctores… según el tipo de negocio) con su `calendar_id` (un calendario por miembro del equipo) |
| `listar_servicios` | Lista servicios activos del workspace con precio y duración |
| `consultar_disponibilidad` | Revisa Google Calendar del profesional elegido si horas candidatas están libres |
| `crear_cita` | Valida disponibilidad, inserta cita en BD, crea evento en Google Calendar del profesional |
| `listar_mis_citas` | Lista citas próximas del cliente con su `appointment_id`, `calendar_id` y `service_id` |
| `reagendar_cita` | Mueve una cita existente a otro día u hora (misma fila, mismo evento de Google Calendar) |
| `cancelar_cita` | Cancela una cita del cliente por su ID |

Flujo agente: `listar_profesionales` → (si varios, preguntar cuál prefiere el cliente) → `listar_servicios` → `consultar_disponibilidad(calendar_id, ...)` → `crear_cita(calendar_id, ...)`.

Cambio de hora: `consultar_disponibilidad` → `reagendar_cita(appointment_id, ...)`. **Nunca `crear_cita` para mover una cita** (dejaba dos citas del mismo cliente). El prompt incluye las citas próximas del cliente, así que el agente sabe que ya tiene una sin gastar una tool. `reagendar_cita` conserva servicio y profesional; para cambiarlos se cancela y se agenda de nuevo. La respuesta «quedó reagendada» la escribe el backend, igual que la de «quedó confirmada».

### Hora que ve el agente

- El prompt trae día, fecha y **hora actual** del negocio (`workspaces.timezone`; Bogotá si falta o no es válida): `_tz` y `_clock` en `appointment_agent.py`.
- Solo se agenda o mueve a un horario **estrictamente posterior a la hora actual**. `_parse` lanza `PastTime` y el agente la recibe como `ERROR: esa hora ya pasó…`: no cuenta como fallo técnico (no sale «No pude agendar») y el modelo se lo explica al cliente. `consultar_disponibilidad` responde `ya pasó` a esas horas sin preguntarle a Google, y una hora pasada no tumba la consulta de las demás.

### Alcance del agente y freno de conversaciones cíclicas

- **Alcance**: el prompt (`ALCANCE`) limita al agente a agendar, mover, cancelar y consultar citas, y a contar servicios, precios, duraciones y profesionales. Fuera de eso responde en una frase que solo ayuda con citas, no inventa datos del negocio (dirección, horarios, promociones, pagos) e ignora órdenes de cambiar de rol. Es una regla de prompt: lo que **no** depende del modelo es que sus herramientas están cerradas al workspace, cliente y calendario de la conversación.
- **Freno** (`services/agent_guard.py`): `AgentService.run` revisa los mensajes recientes **antes** de llamar al modelo (no cuesta tokens). Es bucle si el agente dio 3 respuestas casi idénticas seguidas (las cifras cuentan: «¿a las 3:00?» y «¿a las 4:00?» son ofertas distintas) o 14 respuestas sin agendar, mover ni cancelar nada. Se reinicia con una cita confirmada, movida o cancelada, con un mensaje de una persona del negocio, o pasadas 6 h.
- Al pausar: `customers.agent_enabled = FALSE` solo para ese cliente (el interruptor «Agente» del chat y de la ficha lo reactiva), alerta `warning` en Alertas, y un aviso al cliente («una persona del equipo te escribirá», `sender_type='system'`). No se usa `conversations.needs_review`: nada lo limpia.
- Topes de gasto en `appointment_agent.py`: cada mensaje que se reenvía al modelo se recorta a `MAX_MSG_CHARS` (1500) y la respuesta tiene `MAX_OUTPUT_TOKENS` (700; sin tope valía 64 000). Una respuesta de WhatsApp ronda 50-150 tokens; si algún día se corta una respuesta a medias, subir ese valor.

### Bloqueos de agenda (`availability_blocks`)

Horarios de un calendario (un profesional) en los que no se reciben citas. Se crean en Agenda › «Bloquear» (rol `manager` o superior; «Todo el equipo» crea uno por calendario) y se ven rayados en la vista de día y de semana; un clic abre la ficha para quitarlos.

- Los respetan, todos vía `services/availability_blocks.find_overlap`: `consultar_disponibilidad` (responde «ocupado», **sin el motivo**), `create_appointment` (panel y agente, 409) y `appointment_service.reschedule`.
- Viven solo en la BD de Hilo: no se crea ningún evento en Google Calendar. Lo que el negocio crea directo en Google Calendar sí lo ve free/busy (el agente no ofrece esa hora), pero no se dibuja en la agenda de Hilo.
- Bloquear **no cancela** las citas ya agendadas: la respuesta de crear trae `appointments_in_range` y el panel avisa para que el equipo las mueva.
- Rutas: `GET/POST /workspaces/{id}/blocks` y `DELETE …/blocks/{bid}` (crear y borrar exigen `confirmed=true` y rol `manager`). El calendario del bloqueo debe ser del negocio.
- Front: `lib/blocks.ts` parte cada bloqueo por día y junta los idénticos de varios calendarios en un solo tramo (quitarlo borra todos).

### Mover y cancelar citas (`services/appointment_service.py`)

Una sola implementación para el agente y el panel:

- `reschedule`: valida free/busy sin contar el horario actual de la propia cita, mueve el evento con `CalendarService.update_event` (si Google falla, la BD no cambia), borra el recordatorio ya enviado (`followup_sends`) para que salga con la hora nueva y limpia `confirmed_by_customer_at`. El estado no cambia.
- `cancel`: borra el evento del calendario **de la cita** y guarda `cancelled_by` con el usuario del panel, o `NULL` si cancela el cliente (es FK a `users`).
- Panel: `POST /workspaces/{id}/appointments/{aid}/cancel?confirmed=true`, rol `staff` o superior: cualquier miembro del equipo cancela cualquier cita del negocio (botón «Cancelar cita» en el detalle de la agenda). El `PATCH` sigue siendo de `manager` y delega en el mismo servicio.
- Aviso al cliente al cancelar desde el panel (`notify_cancelled`): plantilla `cancellation` si está aprobada; si no, texto libre solo con la ventana de 24 h abierta; si nada sale, la respuesta trae `customer_notified=false` y el panel le dice al equipo que avise por su cuenta. La cancelación nunca se revierte por un aviso fallido. Cuando cancela el cliente por el agente no hay aviso aparte.

Flujo sistema: WhatsApp → webhook → `ConversationService.find_or_create` → `AgentService.run` → `appointment_agent.run_agent` → respuesta por WhatsApp.

**Requisitos para que el agente funcione en un workspace:**
1. Al menos un servicio activo en la tabla `services`
2. Un Google Calendar conectado con `sync_status='active'` en la tabla `calendars`
3. Canal de WhatsApp activo (tabla `channels`) vinculado al workspace

Sin calendario conectado, el agente solo lista servicios pero no puede agendar.

### Calendarios ligados a miembros del equipo

Cada calendario puede estar ligado a un `workspace_member` vía `calendars.member_id` (FK → `workspace_members.id`).

- Un miembro = un calendario = una persona que atiende.
- El agente expone a quienes atienden mediante la tool `listar_profesionales`.
- Restricciones de unicidad en BD: `UNIQUE(workspace_id, google_calendar_id) WHERE member_id IS NULL` y `UNIQUE(workspace_id, member_id) WHERE member_id IS NOT NULL`.
- **El `state` del OAuth va firmado** (`core/oauth_state.py`, HMAC con `JWT_SECRET`, vence a los 15 min): el callback no trae sesión, así que el `state` es lo único que dice a qué negocio y persona pertenece el calendario; sin firma alguien podía colgar su calendario en otro negocio.
- `GET /auth/google/calendar/url` exige sesión (`staff`+) y decide la persona en el servidor: sin `member_id` es la de quien está logueado. Conectar el de otra persona exige `manager`+; la persona debe ser del mismo negocio. El onboarding, Ajustes y Equipo quedan ligados a un miembro sin cambios en el front.
- Ajustes › Google Calendar: no hay «Sin asignar»; el selector solo ofrece a quien aún no tiene calendario activo. Reconectar renueva la misma fila.
- **Eliminar una conexión** (`DELETE /calendars/{id}`, solo `workspace_owner`): sin citas ni bloqueos que la referencien se borra la fila; con historial se desconecta (`sync_status='disconnected'`) **y se descarta el token**, y la lista deja de mostrarla. Volver a conectar a esa persona revive la misma fila. Un calendario desconectado no se usa para mover/cancelar citas existentes ni para crear nuevas (409).

---

## Tipos de negocio (industrias)

`workspaces.business_type` decide el vocabulario de toda la plataforma. El modelo de datos es el mismo para todas las industrias; solo cambian las palabras y las advertencias del agente.

- Catálogo y única fuente de verdad en el backend: `backend-lang/src/core/business_types.py` (`barberia`, `salon`, `manicure`, `spa`, `estetica`, `tatuajes`, `consultorio`, `odontologia`, `psicologia`, `fisioterapia`, `veterinaria`, `fitness`, `otro`). Cada perfil define cómo se llama quien atiende (barbero, estilista, doctor…) y, en salud y veterinaria, una nota que prohíbe al agente dar diagnósticos.
- Espejo en el front: `front/src/lib/business-types.ts` (iconos y servicios sugeridos del onboarding). `tests/test_business_types.py` falla si los `id` no coinciden.
- **Agregar una industria**: una línea en cada archivo. No requiere migración.
- `business_type` se valida contra el catálogo en `WorkspaceCreate`/`WorkspaceUpdate`. Vacío o desconocido = perfil genérico («profesional»).
- Agente: el prompt se arma con `appointment_agent.build_system_prompt` y las tools tienen nombres neutros. No escribir «barbero» fijo en prompts ni etiquetas.
- Front: usar `useBusinessTerms()` (`hooks/use-workspace.ts`) para cualquier etiqueta que nombre a quien atiende.
- Sigue siendo de barbería/salón: alquiler de silla y propinas en Finanzas (los demás negocios simplemente no los usan) y el texto de ejemplo de las plantillas de WhatsApp.

## Zumit Manager — panel de plataforma (`/zmanager`)

Vista de toda la plataforma para el equipo de Zumit. **Antes era `/admin`; ese prefijo ya no existe** (ni en el front ni en la API: `/api/zmanager/...`). Solo `super_admin`.

- **Interfaz aparte**: layout propio (`routes/zmanager.tsx`, fuera de `_authenticated`) con su menú lateral (`components/zmanager/`) y una ruta por sección: `/zmanager` (Resumen), `/cobros`, `/facturacion`, `/planes`, `/costos`, `/negocios`, `/usuarios`, `/estado`, `/configuracion`. Las pantallas son los componentes de `components/admin/`. Agregar una sección = un archivo en `routes/zmanager/`, una entrada en `ZMANAGER_NAV` (`lib/zmanager.ts`) y correr el generador de rutas (`routeTree.gen.ts`).
- **El backend responde 404 (no 403) a cualquiera que no sea super_admin**, incluido «sin token» y «token vencido» (`core/security.require_platform_admin`): un 403 confirmaría que la ruta existe. Es la barrera real; la del front es comodidad. En el front, sin sesión de super_admin se ve la misma pantalla «no encontrada» de cualquier dirección inexistente (`notFound()`, sin redirigir a /login). La ruta es `ssr: false`: el servidor entrega solo el cascarón.
- **No indexable ni cacheable**: `X-Robots-Tag: noindex…`, `Cache-Control: no-store` y `Referrer-Policy: no-referrer` desde `front/src/server.ts` y desde nginx (`location /zmanager` y `/api/zmanager/`), más `<meta robots>`. **No se lista en `robots.txt` a propósito** (es público y publicaría la ruta) y ningún enlace público apunta a ella. Cambiar `nginx.conf` pide `docker compose restart nginx`.
- **Límite honesto**: el prefijo no es un secreto (el JS del front es público). Lo que protege los datos es el JWT de super_admin que valida el backend.

- Resumen (negocios, usuarios, canales, citas y mensajes de 30 días, reparto por tipo y por suscripción, altas por semana), lista de negocios con filtros y ficha, lista de usuarios.
- Pestaña «Estado» (`GET /zmanager/health`, `services/platform_health.py`): prueba la clave de Anthropic (llamada de 1 token; detecta clave inválida y cuenta sin saldo) y la de Kapso (consulta cada número conectado), y resume las últimas 24 h: recibidos, enviados, chats sin respuesta y alertas del agente. El saldo de Kapso no se obtiene por API: se revisa en su panel. No detecta un mensaje que Kapso aceptó y Meta rechazó después.
- Acciones: corregir el tipo de un negocio, suspenderlo o reactivarlo (`workspaces.is_active`) y bloquear o desbloquear un usuario (`users.is_active`). Todas quedan en `audit_logs`.
- Negocio suspendido: su equipo no puede iniciar sesión (403 en `/auth/login`) y el agente no responde. **Las sesiones ya abiertas siguen vivas hasta que venza el JWT** (el refresh no consulta la BD).
- `is_active` ya no se puede cambiar desde `PATCH /workspaces/{id}`: un negocio no puede reactivarse solo.
- Es el único código que lee datos de todos los workspaces. Fuera de alcance por ahora: entrar como otro negocio, cambiar plan o estado de suscripción desde el panel (existe `PATCH /billing/workspaces/{id}/subscription/status`).

## Planes, suscripciones y facturación (cobro manual)

Fuente de las reglas: `documentation/zumit-plan-de-pagos-y-sus.md`. **No hay pasarela de pago**: el super_admin confirma cada pago y activa o cambia los planes desde Zumit Manager › Facturación.

- **Planes** (`billing_plans.code`): `emprendedor` (250 citas, 3 profesionales, 120.000; lanzamiento 50.000) y `equipo` (550 citas, 6 profesionales, 285.000; lanzamiento 120.000). Profesional adicional 40.000, cita adicional 500. Los parámetros editables (prueba, descuento, margen de 20 citas, gracia de 5 días, retención de 30) viven en `platform_settings`.
- **Un negocio sin fila en `subscriptions` está «sin plan asignado»: no tiene límites y el agente responde igual.** Es lo que pasa con los negocios anteriores a la 022 hasta que se les asigne uno. Nada se bloquea por defecto.
- **Estados** (`subscriptions.status`): `trial` (7 días, sin tarjeta, plan Emprendedor) → `active` → `past_due` (5 días de gracia, sigue atendiendo) → `paused` (el agente no responde; el panel sigue abierto; datos 30 días). `cancelled` al terminar el ciclo pagado. El estado real lo calcula `billing_service.effective_status`, no el worker: el agente deja de atender aunque el worker no haya corrido.
- **Qué cuenta como cita**: la que crea el asistente (`appointments.created_by IS NULL`: el panel siempre guarda a quien la creó; no hay columna aparte, así el INSERT de citas no depende de la 022). No cuentan las del panel ni reagendar; cancelar no la devuelve. Pasado el cupo + 20 de margen, `crear_cita` devuelve un error controlado y **el backend escribe el aviso al cliente** («el negocio te atenderá directamente»); el agente sigue pudiendo mover, cancelar y consultar.
- **Ciclo**: cada `cycle_anchor_day` (el día de la activación; si el mes no lo tiene, el último día), sin desplazar el ancla. `cycle_bounds` devuelve siempre un fin **posterior a hoy**: una cancelación pedida se cierra comparando con el fin del último ciclo *facturado* (`MAX(period_end)`), no con el del ciclo en curso.
- **Descuento**: `discount_cycles_remaining` se descuenta al **emitir** cada factura, y solo si se creó una nueva (idempotente por negocio y periodo). Cambiar de plan lo conserva. Se reclama una vez por número de WhatsApp (`offer_claims.claim_key`); un número que ya lo usó paga el valor real.
- **Worker** `workers/billing_worker.py` (cada hora, con candado): pausa pruebas, genera el cobro 3 días antes, marca vencidas, pausa tras la gracia y avisa por correo (Resend) y en Alertas. **No envía WhatsApp** y **nunca borra datos**: solo registra `purge_due`. Cada paso es idempotente (los avisos se deduplican con `billing_events`, tipo `notice_*`).
- **Seguimientos y plan**: `followup_service.send_followup` no envía los automáticos si el plan no está en servicio (`safe_is_serving`); el aviso de cita cancelada no se frena porque lo dispara el equipo.
- **Profesional adicional**: `billing_worker.bill_extra_professionals` cobra prorrateado el que se agrega a mitad de ciclo; el cobro del ciclo incluye los extra completos. Lo facturado se mide con las líneas `professional` del ciclo en curso.
- **Pedir más citas** (`POST /billing/workspaces/{id}/request-appointments?confirmed=true`, solo `workspace_owner`; botón «Pedir más citas» en la franja de saldo y en Ajustes): el dueño elige un bloque de 50/100/200/300 y `subscription_service.request_extra_appointments` **acredita la recarga ya** (`appointments_topup`, $500 por cita, vence al cierre del ciclo) y crea **el saldo pendiente** (factura `proration` con una línea `appointments`, vence en 7 días o al cierre si llega antes). Topes: solo plan `active` (ni prueba ni mora), solo esos bloques y **una solicitud sin pagar a la vez**; si vence sin pago rige la mora de siempre (aviso, gracia, pausa). El super_admin la ve como cualquier cobro pendiente y confirma el pago. Es decisión de producto: el servicio no espera al pago.
- **Saldo visible** (`GET /billing/workspaces/{id}/usage`, `viewer`+): citas del asistente y profesionales sin precios ni facturas; lo pinta `PlanUsage` bajo la barra superior para todo el equipo.
- **Falla «abierto»**: nunca debe tumbar el agente ni la creación de citas. En el agente se usa siempre `safe_entitlements` (SAVEPOINT), no `get_entitlements`.
- **Medición**: `agent_usage` guarda llamadas y tokens por negocio y día (el costo en USD es una estimación con la tarifa de Haiku de `billing_service.py`); `billing_events` es la línea de tiempo de cada negocio y la base del embudo. La tasa del dólar (`fx_rates`) y las tarifas de Meta (`meta_template_rates`) se cargan a mano en **Zumit Manager › Costos**; sin ellas el margen se muestra en dólares, nunca como un cero falso.
- **Rutas**: dueño `GET /billing/workspaces/{id}/summary|profile|plan-change-preview`, `PUT …/profile`, `POST …/cancel`; super_admin `/zmanager/billing/*`. Todo lo que cambia estado exige `confirmed=true` y queda en `audit_logs`.
- Front: tarjeta «Plan y facturación» en Ajustes (solo `workspace_owner`; el backend responde 403 al resto), `PlanBanner` en la barra superior y sección «Facturación» de Zumit Manager (`components/admin/BillingTab.tsx`).
- **Cuenta de cobro** (`services/billing_documents.py`, `services/cuenta_cobro.py`): el único documento de cobro (no hay factura electrónica). El consecutivo `CC-0001` sale de una secuencia de Postgres (`billing_document_seq`): no se repite ni se reutiliza aunque se anule. **El número se confirma antes de enviar el correo**: la secuencia no se revierte, y si el envío fallara y se deshiciera la transacción quedaría un hueco. El PDF **no se guarda**: se genera al vuelo (`fpdf2`, fuentes base latin-1; comillas y rayas tipográficas se convierten, emojis pasan a `?`). Exige los datos de quien cobra (`platform_issuer`, Zumit Manager › Configuración) y los de cobro del negocio (`billing_profiles`, los da el dueño o el equipo los completa en su ficha). El texto legal sobre el IVA y la forma de pago son campos libres que define la contadora: el sistema no asume nada. Envío por Resend con el PDF adjunto (`EmailService._send(..., attachments)`); `billing_invoices.last_sent_*` guarda a quién y cuándo.
- **Cartera** (`services/billing_cartera.py`): «saldo» = lo pendiente o vencido; **no hay abonos parciales** (un pago cierra la factura entera). Próximos cobros: si la factura del siguiente ciclo ya existe se muestra la real; si no, se estima con las mismas líneas que usará (`subscription_service._invoice_lines`), respetando una bajada de plan agendada o una cancelación pedida.
- **Costo por negocio** (`integrations/langsmith_costs.py`, `services/billing_costs.py`): el agente ya manda `workspace_id` y la etiqueta `citas` a LangSmith; el worker trae el costo real de hoy y ayer **cada hora** y lo guarda en `agent_usage.ls_*` (LangSmith conserva los trazos poco tiempo —14 días en el plan base—, lo que no se copia se pierde). Cada fila dice su fuente: `langsmith`, `estimate` (tokens × tarifa de Haiku de `billing_service.py`) o `mixed`. **Costo por cita** = (IA + WhatsApp) del periodo ÷ citas del asistente (`created_by IS NULL`) del mismo periodo; incluye lo gastado en conversaciones que no terminaron en cita y NO incluye los costos fijos. Las llamadas que LangSmith no pudo tasar se estiman por tokens y se cuentan en `langsmith_sync_log.without_cost`. **Lee con `client.runs.query` (API nueva de LangSmith, `langsmith>=0.10.15`, asíncrona; `list_runs` deja de funcionar el 2027-01-31). Forma comprobada contra LangSmith real el 2026-11-26 (solo lectura).**: la primera sincronización y «Probar conexión» (Costos) lo confirman.
- **SQL y fechas**: un parámetro numérico que se resta o suma a una fecha lleva `CAST(:d AS INTEGER)` (o va dentro de `make_interval`). Sin el `CAST`, Postgres infiere el parámetro como fecha y la consulta falla con «operator does not exist: date > integer». Los tests con BD falsa **no ejecutan el SQL** y no lo ven; `tests/test_sql_params.py` vigila ese patrón en el código de facturación.
- **Costo total y margen por negocio** (Zumit Manager › Costos; **única fuente**: `billing_costs.costs`, ya no hay otro cálculo de margen en Facturación). Costo = IA + WhatsApp + costos fijos; ingreso = lo cobrado repartido por los días de cada ciclo (`accrue`), no el pago del mes, para que el margen no dependa de en qué fecha cayó un pago. Los negocios que no pagan (pruebas, pausados) aparecen con su costo y se suman aparte en `trial_cost_cop`.
- **WhatsApp es siempre una ESTIMACIÓN**: no se guarda ningún dato real de lo que Meta cobra (solo llegan los eventos de Kapso «recibido» y «enviado», sin estados de entrega ni precio por mensaje, y el saldo de Kapso no tiene API). Se calcula con las plantillas enviadas (`followup_sends`, `via='template'`) × la tarifa cargada. **Cada categoría tiene su tarifa y son independientes** (`meta_template_rates.category`: `utility` y `marketing`; la categoría de cada tipo de seguimiento sale de su plantilla, `followup_templates.TEMPLATES[kind].category`): si falta una, solo el costo de esa categoría queda sin calcular (`rates_missing`) y la otra se calcula igual. **Marketing se cobra siempre; utilidad no se cobra si el cliente escribió en las 24 h previas** al envío (ventana de servicio abierta, regla de Meta desde julio de 2025; se comprueba con un mensaje entrante en `messages`). Las tarifas de Colombia las carga el dueño: no hay valores por defecto.
- **Costos fijos** (`platform_settings.fixed_costs_cop_month`, 0 por defecto; sin migración: la clave se crea al guardarla y `get_settings` la completa con `DEFAULTS`): se reparten en partes iguales entre los negocios que pagan (`active` y `past_due`), proporcional a los días del periodo. No modela la tarifa por mensaje de Kapso, que se desconoce.
- **Planes** (`services/billing_plans.py`, Zumit Manager › Planes): tablero con las estadísticas de cada plan (negocios por estado, ingreso, ticket promedio, descuento regalado, uso del cupo, prueba→pago a 90 días, cancelaciones, margen) y series para los gráficos (activaciones por semana, de lunes a domingo). El margen sale de `billing_costs.costs` (una sola fuente). Edición de un plan = **vista previa** (`POST /plans/{id}/preview`, no cambia nada) y luego `PUT /plans/{id}?confirmed=true` (audita antes y después en `audit_logs`). **Qué pasa al editar**: un precio nuevo rige en el *próximo* cobro de cada negocio y lo ya facturado no cambia; el fundador con `frozen_price_cop` no se ve afectado (salvo por el precio de lanzamiento mientras le queden ciclos con descuento); un límite menor rige *ya* (el cupo se calcula en vivo con el plan) y la vista previa lista a los negocios que ya lo pasaron; subir precios pide avisar 30 días antes (§13 del documento de planes). **Reglas**: el `code` no se edita (lo usa el resto del sistema), el plan donde empieza la prueba (`emprendedor`) no se desactiva, un plan con negocios vivos tampoco, `launch_price_cop` ≤ `price_cop`, y al cambiar los barberos se mantiene `max_calendars` igual (columna heredada). No se crean planes nuevos desde la pantalla (los códigos están en el código y en los esquemas). **Renombrar un plan**: el sistema se guía por el `code` (`emprendedor`, `equipo`), no por el nombre, así que renombrar es seguro: los márgenes se agrupan por `plan_id`, los eventos guardan el código, y re-aplicar la migración 022 o el seeder no devuelve el nombre viejo (`ON CONFLICT (code) DO NOTHING`). Un nombre no puede repetirse (sin distinguir mayúsculas). Los textos de las pantallas muestran el nombre leído de la base (`usePlans`, `pending_plan_name`), nunca el código. **Lo que NO sigue al cambio**: lo ya emitido (la línea «Plan X» de una cuenta de cobro se escribe al generar la factura y queda así, como un documento ya enviado; los avisos y alertas viejos igual), y los términos y condiciones, que nombran los planes. **La landing sí los sigue**: `GET /billing/pricing` (público, caché de 1 min, nunca falla hacia afuera: si la lectura falla devuelve `{"plans": []}`) trae nombres, precios, precio de lanzamiento, límites, días de prueba, ciclos de descuento, cupo de fundadores y citas adicionales; `hooks/use-pricing.ts` + `components/landing/pricing-data.ts` (sin React, con `FALLBACK_PRICING` = los precios de siempre, así el HTML del servidor y un fallo de la API muestran lo mismo) arman las tarjetas de `Pricing.tsx` y el «N días» de `Cta.tsx`. Sin precio de lanzamiento la tarjeta no muestra descuento ni ahorro. **Siguen escritos a mano a propósito**: el lema de cada plan (`TAGLINES`, por código), cuál es el «Más elegido» y cuál trae liquidaciones/informe (`FEATURED_CODE`/`TEAM_CODE` = `equipo`) y los bloques de citas adicionales (`ADDON_BLOCKS` en `subscription_service.py`).
- **Dashboard** (antes «Resumen»; `/zmanager`) = los totales de la plataforma (`OverviewTab`) + el análisis semana a semana. **`/zmanager/analisis` ya no existe**: el análisis es la sección «Semana a semana» del Dashboard (`components/zmanager/analisis/`, `GET /zmanager/billing/insights?weeks=`, `services/billing_insights.py`): semanas de lunes a domingo en hora de Bogotá, con 8, 12 o 26 semanas. Cinco gráficos + KPIs + las 5 citas de mayor valor + CSV. **(1) Ingreso contra costo**: ingreso = facturas pagadas repartidas por días (`billing_costs.accrue`); costo = IA (`agent_usage`, LangSmith o estimación) + WhatsApp (estimación) + `fixed_costs_cop_month × 7/30` por semana (a diferencia de Costos, aquí los fijos NO se reparten entre negocios: son del total). Sin tasa del dólar el costo es `null` (el gráfico lo dice, no pinta ceros). **(2) Citas agendadas** por la semana en que se CREAN (`created_at`), no en que se atienden; «del asistente» = `created_by IS NULL`; el total histórico sale de la tabla entera. **(3) Costo por cita** de cada barbería sale de `useCosts` (misma fuente que Costos, sin endpoint nuevo), con una línea en $500 (`EXTRA_APPOINTMENT_COP`, lo que se cobra por una cita adicional; está escrito a mano en el front como `ADDON_PRICE_PER_APPOINTMENT`). **(4) Plantillas** cobrables contra gratis: el conteo es exacto, el costo no (utilidad dentro de la ventana de 24 h es gratis, marketing siempre se cobra). **(5) Cuándo termina el descuento**: por mes (el actual y 5 más), negocios `active`/`past_due` que llegan al precio completo y cuánto suben sus cobros; el descuento se gasta al EMITIR cada factura, así que si la del ciclo siguiente ya salió el precio completo llega un ciclo después (`first_full_price_cycle`). No cuenta al fundador con valor congelado ni a planes sin lanzamiento (su precio no sube). **(6) Las citas que más costaron de IA** (migración 024): cada ejecución del agente guarda sus tokens y costo estimado en `agent_runs` (`AgentService._save_run_usage`, falla abierto) y manda `agent_run_id` a LangSmith, cuya sincronización horaria (`langsmith_costs.aggregate_by_run` → `billing_costs._save_run_costs`, en SAVEPOINT) guarda el costo real en `agent_runs.ls_*`. El costo de una cita = suma de las ejecuciones de la conversación de ese cliente desde la cita anterior del asistente hasta la que la creó (`billing_insights.ai_cost_per_appointment`), con el costo real de LangSmith cuando ya está y la estimación por tokens si no (`source`: `langsmith`/`estimate`/`mixed`). **Solo se mide desde que se aplica la 024**: las citas anteriores no tienen ejecuciones medidas y NO cuentan como gratis (`without_measure`). Las columnas son NULL a propósito. Sin la 024 el análisis devuelve `ai_per_appointment: {available: false}` y todo lo demás sigue. LangSmith conserva los trazos 14 días: lo que la sincronización no copia en ese plazo queda solo con la estimación. **La relación `agent_run_id` ↔ llamadas de LangSmith no se probó contra LangSmith real** (el `select` ya incluía `extra`, donde viajan los metadatos). **Citas de mayor precio** (el precio de la cita, NO el costo de IA) = `price_cop + home_service_price_cop` de las `pending|confirmed|completed`. Lógica pura sin React en `analysis-data.ts`.
- **Gráficos de Zumit Manager** (`components/zmanager/charts/`, `recharts` 2.15 como el tablero de métricas de Ovilo, con los colores de Zumit): degradés de un solo tono definidos una vez por pantalla (`GradientDefs`), tooltip con el valor primero, tarjeta con leyenda (siempre con dos o más series) y vista en tabla equivalente, número que se cuenta hacia arriba, y «reducir movimiento» del sistema lo apaga. **Paleta validada** con `validate_palette` de la guía de visualización: planes = ciruela `#9A3A63` (Emprendedor) y turquesa profundo `#00959E` (Equipo), estados = `#2E9B63` / `#3A6FD6` / `#C48A12` / `#CC4B37`. El borgoña de marca (`#2C0F20`) y los colores de estado de la app **no pasaban** (luminosidad y cromaticidad: se leen casi grises), por eso los gráficos usan estas versiones más saturadas. El ámbar queda a 2,93:1 del fondo: su relevo es el tooltip, la leyenda con nombre y la tabla. **Diferencias con Ovilo, a propósito**: nada de dos ejes Y en un gráfico (inventa correlaciones; se compara una métrica a la vez con chips) y cuadrícula de línea sólida, no punteada. El color sigue al plan (por su `code`), nunca a su posición. La lógica de datos está aparte, sin React (`scale.ts`, `plans-data.ts`, `plan-form.ts`): el front no tiene corredor de pruebas, así que se comprobó con scripts fuera del repo.
- Los tests quitan siempre las claves de LangSmith del entorno (`tests/conftest.py`): `api.main` hace `load_dotenv()` y ningún test debe leer ni mandar trazos a LangSmith.
- Pendiente: pasarela, WhatsApp de Zumit hacia sus clientes, atar la prueba al número de WhatsApp, línea de mensajes de Meta en la factura (hoy es un ajuste manual), pricing en la landing, abonos parciales y exportar los datos del negocio durante los 30 días de retención.

## Móvil (base para PWA)

El panel se usa como app en el teléfono. Corte único en **880px**.

- Navegación: `BottomTabs` (Inicio, Agenda, Chats, Clientes + «Más») y `MobileMenu` (hoja con todo `visibleNav(role)`, contadores y cerrar sesión). Una sección nueva en `lib/nav.ts` aparece sola en «Más».
- Lo que cambia entre móvil y escritorio se decide **por CSS** (`@media (max-width: 879px)`), no por JS. `useIsMobile()` (`hooks/use-is-mobile.ts`) solo cuando cambia el comportamiento (lista ↔ detalle en Clientes y Mensajes). Nunca `window.innerWidth` suelto.
- Reglas globales en `front/src/styles.css`, sección «Móvil»: campos a 16px (evita el zoom de iOS), botones de mínimo 40px, clase `page` para el padding de cada pantalla.
- Altos con `dvh`, no `vh`. Barras fijas con `env(safe-area-inset-*)`.
- Un elemento con `position: fixed` (panel, modal) no puede vivir dentro de algo con `transform` o animación de `transform` que quede aplicada: por eso `.page-enter` usa `backwards`.
- Pendiente para la PWA: manifest, iconos y service worker.

## Animaciones e interacción

Una sola capa de movimiento en `front/src/styles.css` (sección «Movimiento»), con los tokens `--dur-*` y `--ease-*`:

- `page-enter` (entrada de página), `tab-enter` (cambio de pestaña), `stagger` (hijos escalonados), `card--interactive` (tarjeta que se eleva), `skeleton` (carga).
- Todo botón cede al presionarlo y los campos animan borde y foco, vía `:where()` (especificidad 0: cualquier regla de componente gana).
- Entradas con `--ease-out`, estados con `--ease-std`, nada por encima de `--dur-4`. `prefers-reduced-motion` lo apaga todo.
- No agregar librerías de animación ni `animation:` inline: usar estas clases.

## WhatsApp vía Kapso

### Producción
Onboarding: `POST /workspaces/{wid}/kapso/onboarding-link` → Embedded Signup → webhook `phone_number.created` crea canal automáticamente → provisiona webhook por número en `/webhooks/kapso/n/{token}`.

### Sandbox (pruebas)

Número sandbox Kapso: **+56 9 2040 3095** — `phone_number_id = 597907523413541` (fijo, no cambia).

1. Configurar en Kapso Dashboard: WhatsApp → Configurations → Sandbox WhatsApp → Webhooks → URL: `https://zumit.app/webhooks/kapso/sandbox`
2. Copiar el webhook secret auto-generado por Kapso al `backend-lang/.env` como `KAPSO_SANDBOX_WEBHOOK_SECRET`
3. En la app: Settings → Sandbox de pruebas → ingresar número de WhatsApp → crear sesión → enviar código de activación
4. Enviar mensajes al número sandbox para probar el agente

Sesiones sandbox expiran en 24h. Al crear sesión via frontend, el backend activa automáticamente el canal sandbox (`status = 'active'`). Al recargar la página, el frontend restaura la sesión vigente llamando `GET /kapso/sandbox-sessions`.

El canal sandbox (tabla `channels`) debe tener `phone_number_id = 597907523413541` y `status = 'active'` para que el webhook enrute los mensajes.

---

## Estado actual del workspace "Cuenta demo"

- Usuario admin: `juanestebanramirezavila@gmail.com` (super_admin)
- Workspace: `Cuenta demo` (75704f27-7262-4226-9af6-7eabdd7e66ad)
- Canal sandbox: `phone_number_id = 597907523413541`, canal id `9ab278a2-27ae-4f1f-a852-8113556241a7`

---

## Migraciones

Esquema canónico en `backend-lang/migrations/`, aplicado en orden 001..N.

```bash
cd backend-lang
uv run python migrate.py           # aplica pendientes
uv run python migrate.py --status  # ver estado
```

Migración más reciente: `025_rename_plan_emprendedor.sql`. **001–017 están aplicadas en la BD** (016 y 017 el 2026-11-11); **018 a 025 están pendientes** (la 022 ya se aplicó en el servidor; la 025 renombra el plan Arranque a Emprendedor y es obligatoria antes de desplegar este código): el chat de Hilo necesita la 018, el aviso de cita cancelada la 019, entrar con Google la 020, entrar con Facebook la 021, los planes y límites la 022 y la cuenta de cobro y los costos de LangSmith la 023.

Ojo con el runner (`core/migrations.py`): parte el archivo por `;` + salto de línea y envía cada trozo a la BD. Un comentario suelto al final del archivo llega como consulta vacía y lo hace fallar; los comentarios van antes de una sentencia.

Qué agregan las últimas:
- `015_payment_attachments.sql` — comprobantes adjuntos a movimientos (`movement_attachments`, se consulta al listar ventas y movimientos).
- `016_followups.sql` — seguimiento por WhatsApp (`followup_settings`, `followup_templates`, `followup_sends`, `customers.marketing_opt_out`, `appointments.confirmed_by_customer_at`). Sin ella el worker de seguimientos falla en cada pasada.
- `017_payment_receipts.sql` — comprobantes recibidos por WhatsApp (`payment_receipts`).
- `018_human_messages.sql` — mensajes de una persona del negocio (`messages.sender_type='human'`, `messages.sent_via`). Sin ella falla responder desde Hilo y guardar lo enviado desde el celular.
- `019_cancellation_template.sql` — admite `kind='cancellation'` en `followup_templates` y `followup_sends`. Sin ella la plantilla de cita cancelada no se puede registrar ni enviar: el aviso solo sale como texto libre dentro de la ventana de 24 h (la cancelación sí se guarda).
- `020_google_signin.sql` — `users.google_sub` (único) y `password_hash` opcional: las cuentas creadas con Google no tienen contraseña. Sin ella falla entrar o crear cuenta con Google.
- `021_facebook_signin.sql` — `users.facebook_sub` (único). Sin ella falla entrar o crear cuenta con Facebook.
- `023_billing_documents.sql` — datos de quien cobra (`platform_issuer`), consecutivo de cuentas de cobro, estado de envío en `billing_invoices` y costo de LangSmith (`agent_usage.ls_*`, `langsmith_sync_log`). Sin ella solo fallan Cobros, Costos y Configuración de Zumit Manager; lo demás no depende de ella.
- `028_audio_usage.sql` — consumo de la transcripción de audios por negocio y día (`audio_usage`). Sin ella el audio se transcribe igual y Costos no lo suma (falla abierto, deja una línea en el log).
- `024_agent_run_cost.sql` — tokens y costo (estimado y de LangSmith) por ejecución del agente en `agent_runs`. Sin ella solo falta el gráfico «Las citas que más costaron de IA»; el agente y lo demás no dependen de ella (guarda con `_save_run_usage`, que no lanza).
- `022_billing.sql` — planes Emprendedor y Equipo, suscripciones con prueba y ciclo, facturas, eventos, consumo de IA. **Sin ella el producto sigue funcionando como antes**: el registro crea la prueba en un SAVEPOINT y falla en silencio, y el agente usa `billing_service.safe_entitlements` (si la lectura del plan falla, atiende sin límites y deja el error en el log). Lo que no funciona hasta aplicarla: la pestaña Facturación del panel de plataforma y Ajustes › Plan y facturación.

---

## Crear cuenta o entrar con Google (con el calendario en el mismo paso)

- «Continuar con Google» (login y registro) pide en **un solo consentimiento** identidad (`openid email profile`) y calendario. `GET /auth/google/login/url` → Google → el mismo `/auth/google/callback` (misma URI de redirección que ya está registrada) → el `state` trae `kind=signin`.
- **Cuenta nueva**: crea usuario (sin contraseña, `users.google_sub`), negocio «Negocio de {nombre}» (zona Bogotá; el onboarding lo renombra), miembro `workspace_owner` **y el calendario sincronizado**, todo en una transacción.
- **Quien ya entró con Google** vuelve a entrar y se renueva el token de su calendario si sigue conectado (si lo eliminó no se recrea solo).
- **Un correo que ya existe con contraseña se vincula, pero pidiendo la contraseña** (`_oauth_signin`): no hay verificación de correo, y vincular sin más dejaría a una víctima dentro de la cuenta que un atacante registró antes con su correo. El callback no entra ni toca nada: redirige a `/login#link_ticket=…` (ticket firmado `kind=link`, 10 min, con `uid`, `provider`, `sub` y el token de calendario ya cifrado). El front pide la contraseña y llama `POST /auth/oauth/link`, que la valida con bcrypt, guarda `google_sub` (solo si estaba NULL; no pisa otro `sub`) y crea o renueva el calendario (no recrea uno desconectado). Tope: 8 intentos por cuenta y 20 por IP cada 10 min (`core/throttle.py`, en memoria). Cuenta sin contraseña de otro proveedor → `exists_other`. Funciona igual para Facebook.
- **Recuperar contraseña** (`POST /auth/forgot-password` y `/auth/reset-password`, sin migración): el correo (Resend, `EmailService.send_password_reset`) trae `/login#reset_token=…`, un token firmado `kind=reset` de 1 h que lleva la huella (`_pw_fingerprint`) de la contraseña actual: al cambiarla el mismo enlace deja de servir. `forgot-password` responde siempre `{ok:true}` (no revela quién tiene cuenta), manda máx. 3 correos por correo y 10 por IP cada 15 min, y envía en segundo plano. Quien entró solo con Google puede así elegir una contraseña. No cierra sesiones ya abiertas (el JWT vive hasta que venza).
- **Correos** (`services/email_layout.py`, toda la plantilla vive ahí; `email_service.py` solo trae el texto de cada correo): mismo lenguaje de la landing (borgoña `#2C0F20`, blanco cálido, turquesa solo en resaltador y botón en píldora, Nunito). Tablas y estilos en línea (Gmail/Outlook), logo `https://zumit.app/images/logo.png` con URL absoluta fija (un correo no puede cargar localhost), versión en texto automática (`plain_text`) y preheader. Todo dato de una persona pasa por `esc()`; `details()` ya escapa. Un correo nuevo = `base_template(contenido, title=, highlight=, eyebrow=, preheader=)` con `paragraph/details/button/callout`. Cada plantilla tiene un `*_html()` estático para probarla sin enviar. Los avisos de cobro usan `notice_email`.
- **Un 401 de contraseña no es «sesión expirada»**: `apiFetch(..., { authError: true })` (login, ticket, vincular, olvidé, restablecer) muestra el mensaje del backend y no llama al handler de cierre de sesión. Los campos de contraseña usan `components/auth/PasswordInput.tsx` (ojito).
- **Facebook está oculto** en login y registro (`SHOW_FACEBOOK_LOGIN = false` en `front/src/lib/features.ts`) hasta que Meta verifique el negocio y habilite el permiso `email`. El backend sigue completo.
- La sesión no viaja en la URL: el callback redirige a `/login#auth_ticket=…` (fragmento: no llega a logs ni al Referer; los errores van en `?auth_error=…`) con un ticket firmado de 2 min que `POST /auth/google/ticket` cambia por el JWT (vuelve a comprobar que la cuenta y el negocio sigan activos). El ticket no es de un solo uso: vale 2 min.
- Requiere la migración 020. En Google Cloud, la pantalla de consentimiento debe permitir los alcances `openid`, `email` y `profile` (el de calendario ya estaba).

## Crear cuenta o entrar con Facebook

- «Continuar con Facebook» (login y registro) usa **la misma app de Meta** del Embedded Signup (`META_APP_ID` + `WHATSAPP_APP_SECRET`) con el producto «Facebook Login». Código en `integrations/facebook_login.py`; rutas `GET /auth/facebook/login/url` y `GET /auth/facebook/callback` (nginx tiene un `location` propio para el callback, como el de Google: tras cambiarlo, `docker compose restart nginx`).
- Flujo manual de Meta: diálogo OAuth con `state` firmado (`kind=signin_fb`) → intercambio **GET** del código por token (el `client_secret` solo vive en el servidor, `redirect_uri` idéntico al del diálogo) → `/me?fields=id,name,email`. Alcances `public_profile,email`: acceso estándar, **sin App Review**.
- Misma lógica que Google (`_oauth_signin` en `routes/auth.py`): cuenta nueva = usuario sin contraseña (`users.facebook_sub`) + negocio «Negocio de {nombre}» + dueño, **sin calendario** (Facebook no lo da; se conecta en el onboarding). Un correo ya registrado (contraseña u otro proveedor) **no se enlaza solo** (`?auth_error=exists`). Sin correo (la persona lo negó o la cuenta no tiene) → `?auth_error=no_email`; si cancela, `denied`. El regreso reutiliza el ticket y `POST /auth/google/ticket`.
- `GRAPH_VERSION` (hoy `v25.0`) está en `facebook_login.py`: Meta retira cada versión ~2 años después; revisar la tabla de versiones antes de que caduque (v25.0: jul-2028).
- Variable nueva en `backend-lang/.env`: `FACEBOOK_REDIRECT_URI=https://zumit.app/auth/facebook/callback` (debe estar en «URI de redireccionamiento de OAuth válidos» de Facebook Login). Requiere la migración 021.
- En el panel de Meta: app en modo Live, URL de la política de privacidad (`/politicas-de-privacidad`, que ya explica cómo pedir la eliminación de datos) y esa misma URL como instrucciones de eliminación de datos. Meta no obliga a un callback automático si hay instrucciones.

## Buscador, historial y dashboard

- **No asistió**: desde el detalle de la cita (Agenda, Historial, Clientes), `manager`+, solo si está `pending|confirmed` y su hora ya empezó (el backend valida con 422). Cuenta como pérdida igual que `cancelled`. **Cancelar** pide un motivo (`CancelDialog`, `cancellation_reason` ≤255).
- **Alertas** también muestra «Para hacer hoy» (derivado de `dashboard/insights`, no son filas de `agent_alerts`) y el contador de la barra lo suma.

- **Buscador global** (icono en la barra superior; `Ctrl/⌘+K`): `GET /workspaces/{id}/search?q=` (`staff`+) devuelve hasta 6 citas, clientes y servicios, acotados al negocio, con `%`, `_` y `\` del usuario escapados y teléfonos con formato (`300 111` encuentra `573001112233`). Cada resultado abre su pantalla con `?client=`, `?service=` o `?date=&cita=` (la página aplica el parámetro y lo limpia).
- **Historial de citas** (`/historial`, `GET /workspaces/{id}/appointment-history`): filtros por texto, estado, rango de días (en la zona del negocio), profesional, servicio y cliente; paginado de 25; los contadores muestran el reparto por estado de todo el filtro y filtran al pulsarlos; exportar CSV (`…/export`, `manager`+, hasta 5 000 filas, celdas a salvo de fórmulas de Excel). El dinero (cobrado en completadas) solo se devuelve a `manager`+. Se abre ya filtrado con `?customer=`, `?status=`, `?to=`, `?order=`. La ruta no es `/appointments/history` porque `/appointments/{id}` la capturaría.
- **Dashboard** (`GET /workspaces/{id}/dashboard/insights`, `viewer`+): un endpoint arma las gráficas (citas de 14 días, cómo terminaron en 30, servicios, mapa de horas de 60 días, clientes nuevos/recurrentes, ingresos cobrados de 30 días) y «Para hacer hoy» (comprobantes por revisar, citas pasadas sin completar, por cobrar, citas de mañana sin confirmar, clientes que dejaron de venir). Todo corta por día en la zona del negocio. **Dinero, por cobrar y ingresos por servicio solo para `manager`+**: para el resto el backend ni siquiera los consulta. Gráficas en SVG propio (`components/dashboard/charts.tsx`), sin librerías; las frases de interpretación salen de `lib/dashboard-insights.ts`.
- «Ingresos cobrados» (movimientos de ingreso no anulados) **no es** la tarjeta «Valor de las citas del mes» (suma de citas no canceladas, futuras incluidas); por eso se renombró esta última.
- Un solo color por estado en todo el producto: completada verde (`sage`), por atender/confirmada azul (`steel`), cancelada y no asistió naranja/ocre (`clay`/`mustard`). Etiquetas en `lib/appointment-status.ts`.

## Finanzas (módulo contable simple)

Modelo de caja, sin partida doble. Detalle en `backend-lang/src/services/accounting_*.py` y `front/src/components/finanzas/`.

- Fuente de verdad: tabla `movements` (ingresos/gastos, se anulan con `voided_at`, nunca se borran). Cuentas por cobrar/pagar = total de la orden − movimientos no anulados.
- Cita `completed` → orden de venta automática (idempotente por `appointment_id`). Profesional = `calendars.member_id`.
- Comisión: regla por miembro en `member_compensation` (`commission_bps`, 5000 = 50 %); se **congela en cada línea** al vender. Propinas: de quien atendió, no son ingreso del negocio.
- Liquidaciones (`commission_payouts`): borrador reserva las líneas; al pagar genera el gasto (comisión + base) y, si hay alquiler de silla, el ingreso.
- Rutas `/workspaces/{id}/accounting/*`: solo `manager` o superior.
- Fuera de alcance: IVA/DIAN, factura electrónica, inventario, comisión escalonada, prestaciones sociales.
- Fechas: todo corte por día usa `workspaces.timezone` (el servidor corre en UTC; de noche en Colombia ya es «mañana» en UTC). Usar `TODAY_SQL` / `local_date()` de `accounting_common.py`, nunca `CURRENT_DATE`.
- Comprobantes de pago: archivos JPG/PNG/WebP/PDF (máx. 5 MB, 5 por movimiento) adjuntos a cada movimiento (`movement_attachments`). Se guardan en disco bajo `UPLOADS_DIR` (en producción `/app/uploads`, volumen `./uploads` del host en `docker-compose.yml`; **respaldar esa carpeta**). El tipo se decide por la firma del archivo, en disco solo `uuid.ext`, la descarga exige JWT.
- Agenda: al hacer clic en una cita (vista semanal) se abre el detalle con servicio, «Marcar completada» y «Cobrar» (con comprobante opcional). Solo owner/manager.
- Backfill de citas ya completadas: `cd backend-lang && uv run python backfill_sales.py [--mark-paid]`.

---

## Seguimiento por WhatsApp (plantillas)

Cuatro seguimientos automáticos: recordatorio de cita, post-visita, cobro pendiente y reactivación. Una quinta plantilla, `cancellation` (`hilo_cita_cancelada_v1`), no la envía el worker ni tiene interruptor: sale cuando el negocio cancela una cita desde el panel. Se registra y aprueba igual que las demás; los negocios ya conectados deben pulsar otra vez «Activar plantillas».

- Texto **fijo**, definido en `backend-lang/src/services/followup_templates.py`. Para cambiar un texto hay que subir el sufijo `_vN` del nombre: Meta no deja editar una plantilla ya enviada a revisión.
- Meta aprueba las plantillas **por cuenta de WhatsApp (WABA)**: cada negocio las registra en la suya desde WhatsApp › Seguimiento automático › «Activar plantillas» (`followup_service.sync_templates`). Un seguimiento solo se envía cuando su plantilla está `approved`.
- Worker: `workers/followup_worker.py` (sustituye a `reminder_worker.py`), cada 10 min, solo entre 8:00 y 20:00 hora del negocio, con candado en BD para que un solo proceso envíe. `followup_sends` garantiza un envío por cita/venta.
- «Activar plantillas» y «Actualizar estado» consultan primero el número en Kapso (`followup_service._verify_connection`): si ya no existe o Meta lo reporta desconectado, responden 409 y no se crea nada. De paso guardan la cuenta de WhatsApp y si el número está en coexistencia (`channels.coexistence_enabled`, `connection_type`). El worker no hace esa consulta en cada envío.
- Sin ningún número conectado, la pantalla de seguimiento queda deshabilitada (`connected=false` en `GET /followups/templates`) con enlace a Ajustes.
- Cobros de Meta: el enlace de conexión usa `meta_billing_mode: "partner_managed"`, así que Kapso paga a Meta y lo descuenta de los créditos del proyecto. El saldo se recarga y se consulta en Kapso; Hilo no lleva billetera ni consumo.
- Número sandbox y canales que no son Kapso: no admiten plantillas; el seguimiento sale como texto libre (solo llega dentro de la ventana de 24 h).
- Botones: «Confirmar» marca `appointments.confirmed_by_customer_at`; «Cancelar» y «Agendar» pasan al agente como texto; «No más mensajes» activa `customers.marketing_opt_out`.
- Rutas `/workspaces/{id}/followups/*`: solo `manager` o superior.

## Chat de Mensajes (responder desde Hilo y coexistencia)

- Una conversación por cliente; sigue al número por el que llegó el último mensaje (`ConversationService.find_or_create` actualiza `channel_id`). Se responde siempre desde ese número.
- Responder desde Hilo: `POST /workspaces/{id}/conversations/{cid}/messages` (`services/chat_service.py`, rol `staff` o superior). Se guarda con `sender_type='human'`, `sent_via='hilo'`.
- Ventana de 24 h de WhatsApp: solo se puede enviar texto libre hasta 24 h después del último mensaje del cliente (`last_inbound_at` en `ConversationOut`). Fuera de la ventana el backend responde 409 y el front deshabilita la caja. No hay envío de plantillas desde el chat.
- Coexistencia: lo que el negocio escribe desde la app de WhatsApp Business llega por el evento `whatsapp.message.sent` con `message.kapso.origin = "business_app"` y se guarda con `sent_via='business_app'`. Nunca pasa por el agente. Lo enviado por la API (`origin` distinto) se ignora porque ya está guardado.
- Eventos del webhook por número: `NUMBER_WEBHOOK_EVENTS` en `kapso_onboarding.py`. Al agregar uno, correr `uv run python sync_kapso_webhooks.py` para los números ya conectados.
- El chat se actualiza por sondeo (5 s los mensajes, 15 s la lista); no hay websockets.
- El agente **no** se pausa solo cuando una persona responde: se apaga por cliente (`customers.agent_enabled`) o global.
- Pausar el agente con un cliente también se hace desde el chat: interruptor «Agente» en el encabezado (`components/mensajes/AgentToggle.tsx`), el mismo `customers.agent_enabled` de la ficha del cliente. La lista marca «Agente en pausa» en esas conversaciones. Pausado, el equipo sigue pudiendo escribirle.

## Mensajes entrantes y comprobantes de pago

`services/inbound_message_service.py` decide qué hacer con cada mensaje de Kapso según su tipo (el webhook solo verifica la firma y delega):

- Texto → agente de citas. Botón de plantilla → acción directa o agente.
- Imagen o documento → `receipt_service.ingest`: descarga por Kapso (máx. 5 MB), tipo por la firma del archivo, lectura con Claude Haiku (`services/receipt_ocr.py`, mismo `MODEL` del agente) y fila `pending` en `payment_receipts`. Un PDF se guarda sin leer.
- Audio (nota de voz) → `services/audio_transcription.py` lo transcribe con **Gemini 3.5 Transcribe** (`gemini-3.5-transcribe`, Interactions API `POST /v1beta/interactions`, audio en base64 dentro de la petición, con la misma `GOOGLE_API_KEY` del agente) y el texto entra al agente como si el cliente lo hubiera escrito; el chat guarda `🎤 <texto>`. Tope 5 MB; si no se puede (muy pesado, formato no admitido como AMR, ininteligible) el cliente recibe un aviso y el agente no corre. Sin la clave se comporta como antes («solo leo texto»). Cada audio registra su consumo en `audio_usage` (migración 028; la duración se lee del propio ogg/opus) y su costo **estimado** (tokens × tarifa de Google) se suma al costo de IA de Zumit Manager › Costos (`ai.audio` lo muestra aparte); las tarifas son constantes `USD_*` de `audio_transcription.py`, a confirmar en la página de precios de Google.
- Video → «por ahora no puedo ver videos». Tipos desconocidos → «por ahora solo leo texto». Sticker, ubicación y contacto → se guardan en el chat (`[sticker]`, `[ubicación]`, `[contacto]`) y **no se responde nada**. Ninguno llega al agente. El aviso fijo no se repite si el último mensaje enviado ya era ese (`_reply_once`).
- **Nada se cobra solo.** Un manager revisa en Finanzas › Comprobantes: aprobar registra el cobro en la venta elegida (`sales_service.register_payment`) y adjunta el archivo al movimiento; rechazar exige `confirmed=true`.
- El lector de imágenes **no** es una tool del agente: el agente de citas sigue recibiendo solo texto y no puede registrar pagos.
- Los archivos viven en `UPLOADS_DIR/<workspace>/receipts/` (misma carpeta a respaldar).
- Fuera de alcance: abonos antes de que la cita esté completada (no hay venta a la cual aplicarlos) y canales de Meta directo.

---

## Decisiones vigentes

- Sin RLS: aislamiento entre workspaces depende de JWT + `require_workspace_access`
- PK surrogate en `kapso_customers`: PK(id) + UNIQUE(workspace_id)
- `rate_limits`: PK (key, window_start), hits DEFAULT 0
- El rol `owner` no existe: usar siempre `workspace_owner` (guards y `member_role`). `tests/test_owner_guards.py` lo vigila.
- Pendiente: rotar credencial DATABASE_URL que está en historial git
- Los filtros por día (`from_date`/`to_date`) de citas y bloqueos cortan en `workspaces.timezone`, no en UTC (el servidor corre en UTC y una cita de las 19:00 en Bogotá ya es «mañana» en UTC). Ver `_FROM_DAY` / `_AFTER_TO_DAY` en `routes/appointments.py`.
- Dashboard: «Citas de hoy» cuenta solo citas en pie (no `cancelled`, `noshow` ni `rescheduled`); «atendida» es solo `completed`. Usar `rawStatus`, no el `status` de UI, que mezcla estado y hora.
- `KAPSO_SANDBOX_PHONE_NUMBER_ID`: valor por defecto `597907523413541` en config, sobreescribible en `.env`
