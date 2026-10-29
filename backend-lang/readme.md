# Backend — CitasIA / Hilo

FastAPI + LangGraph. Agente de citas por WhatsApp.

## Setup

```bash
# Instalar uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Instalar dependencias
uv sync

# Correr en desarrollo
uv run fastapi dev ./src/api/main.py
```

## Estructura

```
src/
├── api/
│   ├── main.py              # App FastAPI + lifespan
│   └── routes/
│       ├── auth.py           # Login, register (JWT)
│       ├── appointments.py   # CRUD citas
│       ├── channels.py       # Canales WhatsApp + calendarios
│       ├── kapso.py          # Onboarding Kapso + sandbox sessions
│       ├── webhooks.py       # Webhooks: Kapso, WhatsApp, Google Calendar
│       ├── services.py       # Servicios del workspace
│       └── workspaces.py     # CRUD workspaces
├── core/
│   ├── config.py             # Settings (env vars)
│   ├── database.py           # Pool asyncpg
│   ├── models.py             # User, Workspace (roles)
│   └── security.py           # JWT, require_workspace_access
├── services/
│   ├── agent_service.py      # Orquesta ejecución del agente
│   ├── appointment_agent.py  # Agente de citas (3 tools: listar, disponibilidad, crear)
│   ├── calendar_service.py   # Google Calendar sync
│   ├── conversation_service.py
│   ├── kapso_onboarding.py   # KapsoPlatformClient + KapsoSandboxClient
│   └── whatsapp_service.py   # Envío de mensajes (Kapso/Meta)
├── agents/atenea/            # Agente multi-módulo (supply chain, no usado en barbería)
└── schemas/                  # Pydantic schemas
```

## Variables de entorno requeridas

```bash
# Base
DATABASE_URL=postgresql://...
JWT_SECRET=...

# Kapso (WhatsApp)
KAPSO_ENABLED=true
KAPSO_API_KEY=...
KAPSO_WEBHOOK_SECRET_PROJECT=...
KAPSO_SECRETS_KEY=...                    # Fernet key: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
KAPSO_SANDBOX_WEBHOOK_SECRET=...         # Auto-generado por Kapso al configurar webhook sandbox

# LLM
ANTHROPIC_API_KEY=...                    # Para el agente de citas (Claude Haiku 4.5)

# Google Calendar (opcional)
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=...
GOOGLE_ENCRYPTION_KEY=...
```

## Webhooks

| Endpoint | Origen | Función |
|----------|--------|---------|
| `POST /webhooks/kapso` | Kapso proyecto | Eventos: phone_number.created/deleted |
| `POST /webhooks/kapso/n/{token}` | Kapso por número | Mensajes entrantes (producción) |
| `POST /webhooks/kapso/sandbox` | Kapso sandbox | Mensajes entrantes (pruebas) |
| `GET /webhooks/whatsapp` | Meta | Verificación handshake |
| `POST /webhooks/whatsapp` | Meta | Mensajes directos (sin Kapso) |
| `POST /webhooks/google-calendar` | Google | Notificaciones de cambio |

## Flujo del agente de citas

```
Mensaje WhatsApp entrante
  → webhook verifica firma HMAC
  → ConversationService.find_or_create (identifica workspace por phone_number_id del canal)
  → AgentService.run (registra agent_run, construye contexto)
  → appointment_agent.run_agent (Claude Haiku 4.5 + 3 tools)
  → WhatsAppService.send_text (respuesta al cliente)
```

El agente necesita por workspace: servicios activos + Google Calendar conectado.

## Tests

```bash
uv run pytest
```
