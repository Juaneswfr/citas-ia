.constitution/front.md                 # Frontend React
.constitution/backend.md               # Backend Express o FastAPI
.constitution/database.md              # Base de datos / ORM / queries

# CitasIA / Hilo

SaaS multi-tenant de citas por WhatsApp para barberías y negocios de servicios.
Backend FastAPI + LangGraph en `backend-lang/`, front TanStack Start en `front/`, datos en PostgreSQL (Supabase).

## Desarrollo local

```bash
# Backend
cd backend-lang
uv run fastapi dev ./src/api/main.py

# Frontend
cd front
npm run dev
```

No tocar los Dockerfiles — son la configuración actual de producción.

## Producción (VPS)

YA ESTAN CORRIENDO EN PRODUCCION https://hilo.esjuanez.com/

```bash
git pull && docker compose up --build -d
```

- Frontend: multi-stage Dockerfile (bun install + npm run build → Nitro SSR en node:20-alpine)
- Backend: Python 3.12 slim + uv, código montado como volumen
- Nginx: reverse proxy interno en puerto 7000, Apache del host maneja SSL

### Env files requeridos en el server

- `backend-lang/.env` — DATABASE_URL, JWT_SECRET, KAPSO_*, ANTHROPIC_API_KEY, etc.
- `front/.env` — DATABASE_URL, JWT_SECRET, VITE_API_URL, VITE_META_APP_ID, VITE_META_EMBEDDED_SIGNUP_CONFIG_ID

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
| `listar_barberos` | Lista barberos disponibles con su `calendar_id` (un calendario por miembro del equipo) |
| `listar_servicios` | Lista servicios activos del workspace con precio y duración |
| `consultar_disponibilidad` | Revisa Google Calendar del barbero elegido si horas candidatas están libres |
| `crear_cita` | Valida disponibilidad, inserta cita en BD, crea evento en Google Calendar del barbero |
| `listar_mis_citas` | Lista citas próximas del cliente en la conversación |
| `cancelar_cita` | Cancela una cita del cliente por su ID |

Flujo agente: `listar_barberos` → (si varios, preguntar cuál prefiere el cliente) → `listar_servicios` → `consultar_disponibilidad(calendar_id, ...)` → `crear_cita(calendar_id, ...)`.

Flujo sistema: WhatsApp → webhook → `ConversationService.find_or_create` → `AgentService.run` → `appointment_agent.run_agent` → respuesta por WhatsApp.

**Requisitos para que el agente funcione en un workspace:**
1. Al menos un servicio activo en la tabla `services`
2. Un Google Calendar conectado con `sync_status='active'` en la tabla `calendars`
3. Canal de WhatsApp activo (tabla `channels`) vinculado al workspace

Sin calendario conectado, el agente solo lista servicios pero no puede agendar.

### Calendarios ligados a miembros del equipo

Cada calendario puede estar ligado a un `workspace_member` vía `calendars.member_id` (FK → `workspace_members.id`).

- Un miembro = un calendario = un barbero/agente.
- El agente expone los barberos disponibles mediante la tool `listar_barberos`.
- Restricciones de unicidad en BD: `UNIQUE(workspace_id, google_calendar_id) WHERE member_id IS NULL` y `UNIQUE(workspace_id, member_id) WHERE member_id IS NOT NULL`.
- El flujo OAuth pasa `member_id` en el `state` JSON → el callback lo usa al insertar el calendario.

---

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

Migración más reciente: `013_calendar_member.sql` — agrega `member_id` a `calendars` y reemplaza el UNIQUE constraint con índices parciales.

---

## Decisiones vigentes

- Sin RLS: aislamiento entre workspaces depende de JWT + `require_workspace_access`
- PK surrogate en `kapso_customers`: PK(id) + UNIQUE(workspace_id)
- `rate_limits`: PK (key, window_start), hits DEFAULT 0
- T002 pendiente: guards `require_workspace_access("owner")` deben cambiar a `"workspace_owner"`
- Pendiente: rotar credencial DATABASE_URL que está en historial git
- `KAPSO_SANDBOX_PHONE_NUMBER_ID`: valor por defecto `597907523413541` en config, sobreescribible en `.env`
