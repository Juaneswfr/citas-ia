# Quickstart: Backend CitasIA

**Feature**: `001-db-and-endpoints` | **Última actualización**: 2026-06-01

## Requisitos previos

- Python 3.12+
- `uv` (gestor de paquetes) o `pip`
- Proyecto Supabase activo
- Cuenta de Meta Developer con WABA configurado
- Credenciales de OAuth de Google Cloud (Calendar API habilitada)

---

## 1. Clonar y configurar entorno

```bash
cd backend-lang
uv sync           # instala dependencias de pyproject.toml
# o: pip install -e ".[dev]"
```

---

## 2. Variables de entorno

Crear `backend-lang/.env` con:

```env
# Supabase
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_KEY=<service_role_key>
SUPABASE_ANON_KEY=<anon_key>

# JWT
JWT_SECRET=<string-aleatorio-largo>
JWT_ALGORITHM=HS256
JWT_EXPIRY_SECONDS=3600

# Google Calendar
GOOGLE_CLIENT_ID=<client_id>
GOOGLE_CLIENT_SECRET=<client_secret>
GOOGLE_REDIRECT_URI=https://tu-dominio.com/auth/google/callback
GOOGLE_ENCRYPTION_KEY=<fernet_key_base64>  # generar con: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Meta/WhatsApp
WHATSAPP_APP_SECRET=<app_secret_de_meta>
WHATSAPP_VERIFY_TOKEN=<token_de_verificacion_propio>
WHATSAPP_API_TOKEN=<access_token_permanente_de_meta>
WHATSAPP_API_VERSION=v19.0

# Agente
GRAPH_TIMEOUT=90

# Túnel (para endpoints heredados /chat)
TUNNEL_SECRET=<secret>
```

---

## 3. Aplicar migraciones Supabase

Las migraciones están en `backend-lang/migrations/`. Aplicar en orden:

```bash
# Via Supabase CLI (local dev)
supabase db push

# O directamente en Supabase Dashboard → SQL Editor:
# 1. 001_tables_and_extensions.sql
# 2. 002_indexes.sql
# 3. 003_rls_policies.sql
```

---

## 4. Levantar el backend localmente

```bash
cd backend-lang
uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

La API queda disponible en `http://localhost:8000`.  
Documentación interactiva: `http://localhost:8000/docs`

---

## 5. Flujo de onboarding completo

### 5.1 Login

```bash
POST /auth/login
{"email": "owner@negocio.com", "password": "..."}
# → {"access_token": "...", "expires_in": 3600}
```

### 5.2 Crear workspace

```bash
POST /workspaces
Authorization: Bearer <token>
{"slug": "barberia-juanes", "name": "Barbería Juanes", "plan": "free"}
# → WorkspaceOut con id del workspace
```

### 5.3 Conectar canal WhatsApp

```bash
POST /workspaces/{id}/channels
{"phone_number": "+573001234567", "display_name": "Barbería Juanes WA", 
 "waba_id": "...", "phone_number_id": "..."}
# → ChannelOut con status: "active"
```

### 5.4 Conectar Google Calendar (OAuth)

```bash
POST /workspaces/{id}/calendars
{"google_calendar_id": "primary", "oauth_code": "<code_from_google>"}
# → CalendarOut con sync_status: "synced"
```

### 5.5 Crear servicio

```bash
POST /workspaces/{id}/services
{"name": "Corte de cabello", "duration_minutes": 30, "price_cop": 25000, 
 "modality": "presencial"}
# → ServiceOut
```

### 5.6 Agendar cita

```bash
POST /workspaces/{id}/appointments
{"customer_id": "...", "service_id": "...", "calendar_id": "...",
 "start_at": "2026-06-10T10:00:00-05:00"}
# → AppointmentOut con status: "confirmed" y google_event_id
```

---

## 6. Configurar webhook de WhatsApp

1. En Meta Developer Portal → WhatsApp → Configuration → Webhook
2. URL: `https://tu-dominio.com/webhooks/whatsapp`
3. Verify Token: el valor de `WHATSAPP_VERIFY_TOKEN` en tu `.env`
4. Suscribirse a: `messages`, `message_deliveries`

El endpoint GET `/webhooks/whatsapp` responde automáticamente al handshake.

---

## 7. Estructura del proyecto

```
backend-lang/
├── migrations/          ← DDL SQL aplicado a Supabase
├── src/
│   ├── core/            ← config, security, supabase_client
│   ├── schemas/         ← Pydantic v2 models
│   ├── services/        ← lógica de negocio
│   ├── integrations/    ← Google Calendar OAuth
│   ├── api/
│   │   ├── main.py      ← FastAPI app entry point
│   │   └── routes/      ← endpoints por dominio
│   └── agents/
│       └── atenea/      ← LangGraph agent (coexiste)
└── pyproject.toml
```

---

## 8. Roles disponibles

| Rol | Permisos |
|-----|----------|
| `super_admin` | Acceso total, administración de billing |
| `workspace_owner` | CRUD completo dentro de su workspace |
| `owner` | Alias para workspace_owner en rutas de workspace |
| `manager` | Puede gestionar citas, bloqueos y servicios |
| `staff` | Lectura y creación de citas |
| `viewer` | Solo lectura |

---

## 9. Troubleshooting

**`google_encryption_key` inválido**: Generar con `Fernet.generate_key()` y copiar la string base64 completa.  
**Webhook 403**: Verificar que `WHATSAPP_APP_SECRET` coincide con el App Secret de Meta (no el token de acceso).  
**Cita no confirmada (503)**: Google Calendar no respondió. Revisar credenciales OAuth y estado del calendario.  
**RLS: permission denied**: El query usa `anon_key` en lugar de `service_role_key`. El backend SIEMPRE usa `service_role`.
