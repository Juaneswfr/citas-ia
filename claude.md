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

```bash
git pull && docker compose up --build -d
```

- Frontend: multi-stage Dockerfile (bun install + npm run build → Nitro SSR en node:20-alpine)
- Backend: Python 3.12 slim + uv, código montado como volumen
- Nginx: reverse proxy interno en puerto 7000, Apache del host maneja SSL

### Env files requeridos en el server

- `backend-lang/.env` — DATABASE_URL, JWT_SECRET, KAPSO_*, ANTHROPIC_API_KEY, etc.
- `front/.env` — DATABASE_URL, JWT_SECRET, VITE_API_URL, VITE_META_APP_ID, VITE_META_EMBEDDED_SIGNUP_CONFIG_ID

## Arquitectura del agente

El agente de citas (`backend-lang/src/services/appointment_agent.py`) usa Claude Haiku 4.5 con 3 tools:

| Tool | Función |
|------|---------|
| `listar_servicios` | Lista servicios activos del workspace con precio y duración |
| `consultar_disponibilidad` | Revisa Google Calendar si horas candidatas están libres |
| `crear_cita` | Valida disponibilidad, inserta cita en BD, crea evento en Google Calendar |

Flujo: WhatsApp → webhook → `ConversationService.find_or_create` → `AgentService.run` → `appointment_agent.run_agent` → respuesta por WhatsApp.

**Requisitos para que el agente funcione en un workspace:**
1. Al menos un servicio activo en la tabla `services`
2. Un Google Calendar conectado y con `sync_status='active'` en la tabla `calendars`
3. Canal de WhatsApp activo (tabla `channels`) vinculado al workspace

Sin calendario conectado, el agente solo lista servicios pero no puede agendar.

## WhatsApp vía Kapso

### Producción
Onboarding: `POST /workspaces/{wid}/kapso/onboarding-link` → Embedded Signup → webhook `phone_number.created` crea canal automáticamente → provisiona webhook por número en `/webhooks/kapso/n/{token}`.

### Sandbox (pruebas)
1. Configurar en Kapso Dashboard: WhatsApp → Configurations → Sandbox WhatsApp → Webhooks → URL: `https://hilo.esjuanez.com/webhooks/kapso/sandbox`
2. Copiar el webhook secret auto-generado por Kapso al `backend-lang/.env` como `KAPSO_SANDBOX_WEBHOOK_SECRET`
3. En la app: Settings → Sandbox de pruebas → ingresar número de WhatsApp → crear sesión → enviar código de activación
4. Enviar mensajes al número sandbox (+56 9 2040 3095) para probar el agente

Sesiones sandbox expiran en 24h. El `phone_number_id` del canal sandbox en la BD debe coincidir con el que Kapso envía en el payload del webhook.

## Estado actual del workspace "Cuenta demo"

- Usuario admin: `juanestebanramirezavila@gmail.com` (super_admin)
- Workspace: `Cuenta demo` (75704f27-7262-4226-9af6-7eabdd7e66ad)
- Servicios: 2 servicios genéricos ("Nuevo servicio") — renombrar con nombres reales
- Calendarios: ninguno conectado — **bloquea el agente para agendar citas**
- Canal sandbox: creado para +56920403095, phone_number_id pendiente de verificar contra payload real de Kapso

## Migraciones

Esquema canónico en `backend-lang/migrations/`, aplicado en orden 001..N. Sin Alembic — SQL directo.

## Decisiones vigentes

- Sin RLS: aislamiento entre workspaces depende de JWT + `require_workspace_access`
- PK surrogate en `kapso_customers`: PK(id) + UNIQUE(workspace_id)
- `rate_limits`: PK (key, window_start), hits DEFAULT 0
- T002 pendiente: guards `require_workspace_access("owner")` deben cambiar a `"workspace_owner"`
- Pendiente: rotar credencial DATABASE_URL que está en historial git
