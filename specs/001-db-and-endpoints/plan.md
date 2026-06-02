# Implementation Plan: Supabase DB + Backend Endpoints

**Branch**: `001-db-and-endpoints` | **Date**: 2026-06-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/001-db-and-endpoints/spec.md`

## Summary

Crear el esquema completo de base de datos en Supabase (13 tablas, índices, RLS) y todos los
endpoints FastAPI del backend de CitasIA, organizados por dominio. El backend extiende el
proyecto `backend-lang` existente con nuevas capas: `core/`, `schemas/`, `services/`,
`integrations/`, y `api/routes/`. La integración con Meta WABA directo (Embedded Signup)
y Google Calendar OAuth requiere cifrado de tokens en reposo y verificación de firmas en
webhooks. El agente LangGraph opera exclusivamente a través de tools controladas del backend.

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: FastAPI 0.136+, LangGraph 1.2+, supabase-py, Pydantic v2, httpx, cryptography (Fernet), google-api-python-client, pydantic-settings
**Storage**: Supabase + PostgreSQL — 13 tablas aplicadas, RLS activo
**Testing**: pytest + pytest-asyncio (integration tests contra Supabase test project)
**Target Platform**: Linux server (Docker), expuesto con Uvicorn/Gunicorn
**Project Type**: web-service (FastAPI REST API + LangGraph conversational agent)
**Performance Goals**: p95 <2s en consultas de disponibilidad; ACK webhook WhatsApp <5s; ≤200 conversaciones simultáneas/workspace
**Constraints**: Webhook Meta MUST responder en <20s (límite de Meta); tokens OAuth cifrados con Fernet; rate limiting 200 req/min en `/webhooks/whatsapp`
**Scale/Scope**: MVP target 10–50 workspaces activos; ≤200 conv simultáneas/workspace

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principio | Estado | Evidencia |
|-----------|--------|-----------|
| I. WhatsApp-First | ✅ PASS | Canal principal definido; panel es herramienta secundaria |
| II. Backend Centro de Control | ✅ PASS | Toda lógica en `services/`; agente nunca accede a BD directamente |
| III. Agente Determinístico | ✅ PASS | Agent recibe contexto estructurado; usa tools del backend |
| IV. Multi-Tenant Aislado | ✅ PASS | 13 tablas con `workspace_id`; RLS activado en todas |
| V. Observabilidad Completa | ✅ PASS | `audit_logs`, `agent_runs`, `tool_calls`, `agent_alerts` creadas |
| VI. Calendario Fuente de Verdad | ✅ PASS | `check_availability` antes de crear cita; `google_event_id` en `appointments` |
| VII. Seguridad por Defecto | ✅ PASS | JWT en todos los endpoints; HMAC-SHA256 en webhooks; Fernet para OAuth tokens |
| VIII. Operación Resiliente | ✅ PASS | Calendar falla → cita NO confirmada (Principio VIII en `appointments.py`) |
| IX. Confirmación Explícita | ✅ PASS | `confirmed=true` query param obligatorio en cancelaciones y bloqueos |
| X. SOLID + Responsabilidad Única | ✅ PASS | Capas separadas: schemas / services / routes / integrations |
| XI. Seguridad de Endpoints | ✅ PASS | `require_role()` + `require_workspace_access()` en cada ruta |
| XII. Documentación Básica | ✅ PASS | Docstrings en servicios; `Field(description=...)` en schemas; summaries en routers |

**→ GATE PASSED. Sin violaciones. Proceder a Phase 0.**

## Project Structure

### Documentation (this feature)

```text
specs/001-db-and-endpoints/
├── plan.md              ← este archivo
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   ├── auth.md
│   ├── workspaces.md
│   ├── services.md
│   ├── appointments.md
│   ├── channels.md
│   ├── conversations.md
│   ├── billing.md
│   └── webhooks.md
└── checklists/
    └── requirements.md
```

### Source Code (backend-lang)

```text
backend-lang/
├── migrations/
│   ├── 001_tables_and_extensions.sql  ✅ aplicado
│   ├── 002_indexes.sql                ✅ aplicado
│   └── 003_rls_policies.sql           ✅ aplicado
└── src/
    ├── core/
    │   ├── config.py          ✅ Settings + get_settings()
    │   ├── security.py        ✅ JWT, require_role(), require_workspace_access()
    │   └── supabase_client.py ✅ get_supabase() + get_supabase_anon()
    ├── schemas/
    │   ├── auth.py            ✅ LoginRequest, TokenResponse
    │   ├── workspace.py       ✅ WorkspaceCreate/Update/Out, MemberInvite/Out
    │   ├── service.py         ✅ ServiceCreate/Update/Out
    │   ├── appointment.py     ✅ AppointmentCreate/Update/Out, AvailabilityBlock*
    │   ├── channel.py         ✅ ChannelCreate/Out, CalendarCreate/Out
    │   └── conversation.py    ✅ CustomerOut/Update, ConversationOut, MessageOut
    ├── services/
    │   ├── audit_service.py       ✅ AuditService.log()
    │   ├── calendar_service.py    ✅ check_availability, create/delete/update_event
    │   ├── conversation_service.py ✅ find_or_create, save_message
    │   └── agent_service.py       ✅ AgentService.run() + _build_context()
    ├── integrations/
    │   └── google_calendar.py  ✅ OAuth exchange + Fernet encrypt/decrypt
    ├── api/
    │   ├── main.py            ✅ FastAPI app + routers registrados
    │   └── routes/
    │       ├── auth.py         ✅ /auth/login, /refresh, /me
    │       ├── workspaces.py   ✅ CRUD workspace + miembros
    │       ├── services.py     ✅ CRUD servicios
    │       ├── appointments.py ✅ CRUD citas + bloques
    │       ├── channels.py     ✅ Canales WhatsApp + Calendarios Google
    │       ├── conversations.py ✅ Clientes + conversaciones + mensajes
    │       ├── billing.py      ✅ Planes + suscripciones
    │       └── webhooks.py     ✅ Meta WABA + Google Calendar
    └── agents/
        └── atenea/            (existente — coexiste con nuevos módulos)
```

**Structure Decision**: Web application (backend only) extendiendo proyecto existente.
La capa LangGraph (Atenea) coexiste en `agents/`. Los nuevos módulos de citas se integran
en `api/routes/`, `services/`, `schemas/`, `integrations/` y `core/`.

## Complexity Tracking

> No hay violaciones de constitución que justificar.
