.constitution/front.md                 # Frontend React
.constitution/backend.md               # Backend Express o FastAPI
.constitution/database.md              # Base de datos / ORM / queries

# Zumit (agente: Hilo)

La plataforma se llama **Zumit**; el agente conversacional se llama **Hilo**. Los identificadores técnicos (dominio `hilo.esjuanez.com`, plantillas `hilo_*_v1`, `sent_via='hilo'`, carpetas `hilo`) conservan el nombre antiguo.

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

YA ESTAN CORRIENDO EN PRODUCCION https://hilo.esjuanez.com/

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

## Panel de plataforma (`/admin`)

Vista de toda la plataforma para el equipo de Hilo. Solo `super_admin` (guard a nivel de router en `api/routes/admin.py`; en el front, ítem «Plataforma» del menú).

- Resumen (negocios, usuarios, canales, citas y mensajes de 30 días, reparto por tipo y por suscripción, altas por semana), lista de negocios con filtros y ficha, lista de usuarios.
- Pestaña «Estado» (`GET /admin/health`, `services/platform_health.py`): prueba la clave de Anthropic (llamada de 1 token; detecta clave inválida y cuenta sin saldo) y la de Kapso (consulta cada número conectado), y resume las últimas 24 h: recibidos, enviados, chats sin respuesta y alertas del agente. El saldo de Kapso no se obtiene por API: se revisa en su panel. No detecta un mensaje que Kapso aceptó y Meta rechazó después.
- Acciones: corregir el tipo de un negocio, suspenderlo o reactivarlo (`workspaces.is_active`) y bloquear o desbloquear un usuario (`users.is_active`). Todas quedan en `audit_logs`.
- Negocio suspendido: su equipo no puede iniciar sesión (403 en `/auth/login`) y el agente no responde. **Las sesiones ya abiertas siguen vivas hasta que venza el JWT** (el refresh no consulta la BD).
- `is_active` ya no se puede cambiar desde `PATCH /workspaces/{id}`: un negocio no puede reactivarse solo.
- Es el único código que lee datos de todos los workspaces. Fuera de alcance por ahora: entrar como otro negocio, cambiar plan o estado de suscripción desde el panel (existe `PATCH /billing/workspaces/{id}/subscription/status`).

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

1. Configurar en Kapso Dashboard: WhatsApp → Configurations → Sandbox WhatsApp → Webhooks → URL: `https://hilo.esjuanez.com/webhooks/kapso/sandbox`
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

Migración más reciente: `020_google_signin.sql`. **001–017 están aplicadas en la BD** (016 y 017 el 2026-11-11); **018, 019 y 020 están pendientes**: el chat de Hilo necesita la 018, el aviso de cita cancelada la 019 y entrar con Google la 020.

Ojo con el runner (`core/migrations.py`): parte el archivo por `;` + salto de línea y envía cada trozo a la BD. Un comentario suelto al final del archivo llega como consulta vacía y lo hace fallar; los comentarios van antes de una sentencia.

Qué agregan las últimas:
- `015_payment_attachments.sql` — comprobantes adjuntos a movimientos (`movement_attachments`, se consulta al listar ventas y movimientos).
- `016_followups.sql` — seguimiento por WhatsApp (`followup_settings`, `followup_templates`, `followup_sends`, `customers.marketing_opt_out`, `appointments.confirmed_by_customer_at`). Sin ella el worker de seguimientos falla en cada pasada.
- `017_payment_receipts.sql` — comprobantes recibidos por WhatsApp (`payment_receipts`).
- `018_human_messages.sql` — mensajes de una persona del negocio (`messages.sender_type='human'`, `messages.sent_via`). Sin ella falla responder desde Hilo y guardar lo enviado desde el celular.
- `019_cancellation_template.sql` — admite `kind='cancellation'` en `followup_templates` y `followup_sends`. Sin ella la plantilla de cita cancelada no se puede registrar ni enviar: el aviso solo sale como texto libre dentro de la ventana de 24 h (la cancelación sí se guarda).
- `020_google_signin.sql` — `users.google_sub` (único) y `password_hash` opcional: las cuentas creadas con Google no tienen contraseña. Sin ella falla entrar o crear cuenta con Google.

---

## Crear cuenta o entrar con Google (con el calendario en el mismo paso)

- «Continuar con Google» (login y registro) pide en **un solo consentimiento** identidad (`openid email profile`) y calendario. `GET /auth/google/login/url` → Google → el mismo `/auth/google/callback` (misma URI de redirección que ya está registrada) → el `state` trae `kind=signin`.
- **Cuenta nueva**: crea usuario (sin contraseña, `users.google_sub`), negocio «Negocio de {nombre}» (zona Bogotá; el onboarding lo renombra), miembro `workspace_owner` **y el calendario sincronizado**, todo en una transacción.
- **Quien ya entró con Google** vuelve a entrar y se renueva el token de su calendario si sigue conectado (si lo eliminó no se recrea solo).
- **Un correo que ya existe con contraseña NO se enlaza solo** (`?google_error=exists`): hoy no hay verificación de correo, y enlazar dejaría a una víctima dentro de la cuenta que un atacante registró antes con su correo. Pendiente a futuro: enlazar desde Ajustes con la sesión iniciada.
- La sesión no viaja en la URL: el callback redirige a `/login#google_ticket=…` (fragmento: no llega a logs ni al Referer) con un ticket firmado de 2 min que `POST /auth/google/ticket` cambia por el JWT (vuelve a comprobar que la cuenta y el negocio sigan activos). El ticket no es de un solo uso: vale 2 min.
- Requiere la migración 020. En Google Cloud, la pantalla de consentimiento debe permitir los alcances `openid`, `email` y `profile` (el de calendario ya estaba).

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
- Cita `completed` → orden de venta automática (idempotente por `appointment_id`). Barbero = `calendars.member_id`.
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
- Meta aprueba las plantillas **por cuenta de WhatsApp (WABA)**: cada barbería las registra en la suya desde WhatsApp › Seguimiento automático › «Activar plantillas» (`followup_service.sync_templates`). Un seguimiento solo se envía cuando su plantilla está `approved`.
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
- Video → «por ahora no puedo ver videos». Audio y tipos desconocidos → «por ahora solo leo texto» (el audio no se transcribe: ver logs.md, opciones de transcripción). Sticker, ubicación y contacto → se guardan en el chat (`[sticker]`, `[ubicación]`, `[contacto]`) y **no se responde nada**. Ninguno llega al agente. El aviso fijo no se repite si el último mensaje enviado ya era ese (`_reply_once`).
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
