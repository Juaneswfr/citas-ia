# Tasks: Supabase DB + Backend Endpoints

**Feature**: `001-db-and-endpoints` | **Branch**: master | **Fecha**: 2026-06-01  
**Input**: `specs/001-db-and-endpoints/` — plan.md, spec.md, data-model.md, contracts/, research.md

**Leyenda**: `- [x]` = completado · `- [ ]` = pendiente · `[P]` = paralelizable · `[USn]` = user story

---

## Phase 1: Setup (Infraestructura base)

**Purpose**: Inicialización del proyecto y estructura base.

- [x] T001 Verificar estructura de directorios del backend en `backend-lang/src/`
- [x] T002 Añadir dependencias CitasIA a `backend-lang/pyproject.toml` (pydantic-settings, supabase, cryptography, google-api-python-client, google-auth-oauthlib, httpx, PyJWT, python-dotenv)
- [x] T003 Ejecutar `uv sync` en `backend-lang/` para instalar las nuevas dependencias

---

## Phase 2: Foundational (Bloqueantes — deben completarse antes de cualquier User Story)

**Purpose**: Core compartido que todas las user stories necesitan.

**⚠️ CRÍTICO**: Ninguna user story puede avanzar hasta completar esta fase.

- [x] T004 [P] Implementar `Settings` + `get_settings()` con `@lru_cache` en `backend-lang/src/core/config.py`
- [x] T005 [P] Implementar `create_access_token()` + `decode_token()` + `get_current_user()` en `backend-lang/src/core/security.py`
- [x] T006 [P] Implementar `require_role()` y `require_workspace_access()` con jerarquía de roles en `backend-lang/src/core/security.py`
- [x] T007 [P] Implementar `get_supabase()` (service_role, cached) y `get_supabase_anon()` en `backend-lang/src/core/supabase_client.py`
- [x] T008 Aplicar migración 001 — DDL de 17 tablas con CHECK constraints en Supabase (`backend-lang/migrations/001_tables_and_extensions.sql`)
- [x] T009 Aplicar migración 002 — 12 índices (slug UNIQUE, workspace+user UNIQUE, etc.) en Supabase (`backend-lang/migrations/002_indexes.sql`)
- [x] T010 Aplicar migración 003 — RLS habilitado en 15 tablas + políticas SELECT por workspace en Supabase (`backend-lang/migrations/003_rls_policies.sql`)
- [x] T011 Registrar los 8 routers de CitasIA en `backend-lang/src/api/main.py` (auth, workspaces, services, appointments, channels, conversations, billing, webhooks)

**Checkpoint**: Infraestructura lista — implementación de user stories puede comenzar en paralelo.

---

## Phase 3: User Story 1 — Gestión de Workspace y Autenticación (P1) 🎯 MVP

**Goal**: El dueño puede crear su cuenta, iniciar sesión, crear workspace y administrar miembros del equipo con roles diferenciados.

**Independent Test**: `POST /auth/login` → 200 con JWT válido. `POST /workspaces` → 201. `POST /workspaces/{id}/members` → 201 con rol `manager`. JWT expirado → 401 sin detalle interno.

### Implementación US1

- [x] T012 [P] [US1] Definir `LoginRequest`, `TokenResponse`, `RefreshRequest` en `backend-lang/src/schemas/auth.py`
- [x] T013 [P] [US1] Definir `WorkspaceCreate/Update/Out`, `MemberInvite/Out` en `backend-lang/src/schemas/workspace.py`
- [x] T014 [US1] Implementar `POST /auth/login`, `POST /auth/refresh`, `GET /auth/me` en `backend-lang/src/api/routes/auth.py`
- [x] T015 [US1] Implementar CRUD de workspace + gestión de miembros en `backend-lang/src/api/routes/workspaces.py`
- [ ] T016 [US1] Completar `SUPABASE_URL`, `SUPABASE_ANON_KEY` y `SUPABASE_SERVICE_ROLE_KEY` en `backend-lang/.env` con valores reales del proyecto Supabase
- [ ] T017 [US1] Smoke test manual: `POST /auth/login` con cuenta Supabase válida → verificar JWT contiene `sub`, `email`, `role`, `workspace_id`

**Checkpoint**: Un dueño puede registrarse, crear workspace e invitar un manager.

---

## Phase 4: User Story 2 — Conexión de Canal WhatsApp y Google Calendar (P1)

**Goal**: El dueño puede conectar su número WhatsApp (coexistencia) y su Google Calendar para sincronizar disponibilidad y habilitar el agente.

**Independent Test**: Canal WA con `status: active`. Calendario conectado sin retornar `oauth_refresh_token_encrypted`. Webhook GET Meta → handshake OK. POST con firma inválida → 403.

### Implementación US2

- [x] T018 [P] [US2] Implementar `encrypt_token()`, `decrypt_token()`, `exchange_oauth_code()`, `build_calendar_client()` en `backend-lang/src/integrations/google_calendar.py`
- [x] T019 [P] [US2] Definir `ChannelCreate/Out` y `CalendarCreate/Out` en `backend-lang/src/schemas/channel.py`
- [x] T020 [P] [US2] Implementar `GET/POST /workspaces/{id}/channels` + `PATCH .../status` en `backend-lang/src/api/routes/channels.py`
- [x] T021 [US2] Implementar `GET/POST /workspaces/{id}/calendars` + `DELETE` (sin retornar token cifrado) en `backend-lang/src/api/routes/channels.py`
- [x] T022 [US2] Añadir ruta `GET /auth/google/callback` en `backend-lang/src/api/routes/auth.py` — recibe `?code=` de Google y llama `exchange_oauth_code()` para retornar el token cifrado al frontend
- [x] T023 [US2] Actualizar `GOOGLE_REDIRECT_URI` en `backend-lang/.env` al URL real del callback (`https://hilo.esjuanez.com/auth/google/callback`)
- [x] T024 [P] [US2] Añadir `WHATSAPP_API_TOKEN` y `WHATSAPP_PHONE_NUMBER_ID` como campos de `Settings` en `backend-lang/src/core/config.py`
- [x] T025 [US2] Crear `backend-lang/src/services/whatsapp_service.py` con `WhatsAppService.send_message(phone, text, phone_number_id)` que llama a Meta Graph API via httpx
- [ ] T026 [US2] Completar `WHATSAPP_APP_SECRET` en `backend-lang/.env` con el App Secret real de Meta Developer Portal

**Checkpoint**: Workspace con canal WA activo y calendario Google conectado — el agente tiene todos los canales para operar.

---

## Phase 5: User Story 3 — CRUD de Servicios y Agenda (P1)

**Goal**: El dueño puede crear, editar, activar y desactivar los servicios de su negocio.

**Independent Test**: `POST /services` → 201 con duración y precio. `PATCH is_active:false` → servicio desactivado. `POST` con rol `staff` → 403.

### Implementación US3

- [x] T027 [P] [US3] Definir `ServiceCreate/Update/Out` en `backend-lang/src/schemas/service.py`
- [x] T028 [US3] Implementar `GET/POST /workspaces/{id}/services` + `GET/PATCH/DELETE /services/{id}` (soft-delete) en `backend-lang/src/api/routes/services.py`
- [x] T029 [US3] Mejorar `create_event()` en `backend-lang/src/services/calendar_service.py`: lookup del nombre del servicio desde BD para usar en `event["summary"]` (actualmente muestra `service_id` crudo)

**Checkpoint**: Servicios activos disponibles para el agente. Staff no puede crear ni borrar servicios (403 verificado).

---

## Phase 6: User Story 4 — Ciclo completo de Citas (P1)

**Goal**: El sistema puede crear, confirmar, cancelar y reagendar citas con sincronización bidireccional con Google Calendar.

**Independent Test**: `POST /appointments` → 201 con `google_event_id`. `PATCH status:cancelled?confirmed=true` → evento eliminado de Calendar. Slot ocupado → 409. Sin `confirmed=true` → 422.

### Implementación US4

- [x] T030 [P] [US4] Implementar `AuditService.log()` (fire-and-forget, nunca lanza excepción) en `backend-lang/src/services/audit_service.py`
- [x] T031 [P] [US4] Implementar `CalendarService`: `check_availability()`, `create_event()`, `delete_event()`, `update_event()` en `backend-lang/src/services/calendar_service.py`
- [x] T032 [P] [US4] Definir `AppointmentCreate/Update/Out`, `AvailabilityBlockCreate/Out` en `backend-lang/src/schemas/appointment.py`
- [x] T033 [US4] Implementar `GET/POST /workspaces/{id}/appointments` con verificación de disponibilidad + `google_event_id` en `backend-lang/src/api/routes/appointments.py`
- [x] T034 [US4] Implementar `PATCH /appointments/{id}` con validación de transición de estado + `confirmed=true` para cancelaciones (Principio IX) en `backend-lang/src/api/routes/appointments.py`
- [x] T035 [US4] Implementar `GET/POST /workspaces/{id}/blocks` + `DELETE /blocks/{id}` con `confirmed=true` obligatorio en `backend-lang/src/api/routes/appointments.py`
- [x] T036 [US4] Implementar `CalendarService.sync_from_notification()` con `nextSyncToken` incremental en `backend-lang/src/services/calendar_service.py` — actualiza citas en BD cuando Google detecta cambios externos
- [x] T037 [US4] Crear `backend-lang/src/workers/reminder_worker.py` — worker asíncrono que envía mensajes WA 24h y 2h antes de cada cita confirmada usando `WhatsAppService.send_message()` (FR-011)
- [x] T038 [US4] Registrar scheduler del reminder worker en `backend-lang/src/api/main.py` mediante `lifespan` event (APScheduler o asyncio periodic task)

**Checkpoint**: Citas se crean y cancelan con sincronización bidireccional. Recordatorios enviados automáticamente por WhatsApp.

---

## Phase 7: User Story 5 — Conversaciones y Mensajes (P2)

**Goal**: El sistema registra cada conversación WhatsApp para trazabilidad del agente y revisión del dueño.

**Independent Test**: Mensaje WA inbound → conversación creada + mensaje con `direction:inbound`. Agente procesa y guarda `direction:outbound`. `GET /conversations/{id}/messages` → historial completo.

### Implementación US5

- [x] T039 [P] [US5] Implementar `ConversationService.find_or_create()`, `save_message()`, `_find_or_create_customer()` en `backend-lang/src/services/conversation_service.py`
- [x] T040 [P] [US5] Definir `CustomerOut/Update`, `ConversationOut`, `MessageOut` en `backend-lang/src/schemas/conversation.py`
- [x] T041 [P] [US5] Implementar `GET /customers`, `GET/PATCH /customers/{id}` en `backend-lang/src/api/routes/conversations.py`
- [x] T042 [US5] Implementar `GET /conversations` + `GET /conversations/{id}/messages` en `backend-lang/src/api/routes/conversations.py`
- [ ] T043 [US5] Reemplazar placeholder en `AgentService.run()` con llamada real al grafo LangGraph de citas en `backend-lang/src/services/agent_service.py` (pasar `context` estructurado + `conversation_id` como `thread_id`)
- [x] T044 [US5] Conectar salida del agente (`reply_text`) con `WhatsAppService.send_message()` en `backend-lang/src/services/agent_service.py` + guardar mensaje outbound via `ConversationService.save_message(direction="outbound")`

**Checkpoint**: Historial completo de conversaciones. Agente real responde por WhatsApp con LangGraph.

---

## Phase 8: Polish y Concerns Transversales

**Purpose**: Seguridad, performance y estabilidad para producción.

- [x] T045 [P] Añadir rate limiting 200 req/min por workspace en `POST /webhooks/whatsapp` — instalar `slowapi` y configurar en `backend-lang/src/api/main.py`
- [ ] T046 [P] Añadir `WHATSAPP_API_TOKEN` y `WHATSAPP_PHONE_NUMBER_ID` en `backend-lang/.env` con valores reales de Meta
- [ ] T047 Ejecutar flujo de onboarding completo del `quickstart.md` contra proyecto Supabase real y documentar resultado
- [x] T048 [P] Verificar que `AuditService.log()` cubre todas las acciones críticas: `appointment.create`, `appointment.cancel`, `service.update`, `channel.status` — audit logs añadidos en services.py y channels.py
- [x] T049 Completar `GOOGLE_REDIRECT_URI` en `backend-lang/.env` con URL de producción (`https://hilo.esjuanez.com/auth/google/callback`)

---

## Dependencias y Orden de Ejecución

### Dependencias entre fases

- **Fase 1 (Setup)**: Sin dependencias — comenzar inmediatamente
- **Fase 2 (Foundational)**: Depende de Fase 1 — **BLOQUEA todas las user stories**
- **Fases 3–7 (User Stories)**: Todas dependen de Fase 2
  - Pueden ejecutarse en paralelo (si hay capacidad) o secuencialmente por prioridad
- **Fase 8 (Polish)**: Depende de que las user stories deseadas estén completas

### Dependencias entre User Stories

| Story | Depende de | Bloquea |
|-------|-----------|---------|
| US1 (P1) | Fase 2 | US2, US3, US4, US5 |
| US2 (P1) | US1 (workspace) | US4, US5 |
| US3 (P1) | US1 | US4 |
| US4 (P1) | US2 + US3 | — |
| US5 (P2) | US2 (canal WA) | — |

### Dentro de cada User Story

- Schemas → Services → Endpoints → Integraciones externas → Workers

### Oportunidades de paralelismo

- T004–T007 (core layer): todas paralelas
- T012–T013 (schemas US1): paralelas
- T018–T020 (US2): paralelas
- T030–T032 (US4): paralelas
- T039–T042 (US5): paralelas
- T045, T046, T048 (polish): paralelas

---

## Ejecución Paralela — Ejemplo US4

```bash
# Paralelas (distintos archivos, sin dependencias entre sí):
Task T030: AuditService en backend-lang/src/services/audit_service.py
Task T031: CalendarService en backend-lang/src/services/calendar_service.py
Task T032: Schemas Appointment* en backend-lang/src/schemas/appointment.py

# Luego secuenciales (dependen de T030-T032):
Task T033: GET/POST /appointments con Calendar
Task T034: PATCH /appointments/{id} con cancelación
Task T035: GET/POST/DELETE /blocks

# Workers (no bloquean MVP):
Task T036: sync_from_notification (Calendar push)
Task T037: reminder_worker
Task T038: scheduler registration
```

---

## Estrategia de Implementación

### MVP Mínimo Operativo (próximas tareas críticas en orden)

```
1. T003 — uv sync (instalar deps)
2. T016 — completar .env con Supabase real
3. T022 — OAuth callback de Google
4. T023 — GOOGLE_REDIRECT_URI real
5. T024 — WHATSAPP_API_TOKEN en Settings
6. T025 — WhatsAppService.send_message()
7. T026 + T046 — WhatsApp secrets reales
8. T044 — conectar agente con outbound
9. T017 — smoke test end-to-end
```

### Entrega Incremental

1. Backend base ✅ → Verificar con Postman/curl
2. `.env` con valores reales ⬜ → Login y workspace funcionando
3. OAuth callback + WhatsApp outbound ⬜ → Canal activo completo
4. Agente LangGraph real ⬜ → Conversación end-to-end por WA
5. Reminder worker + rate limiting ⬜ → Listo para producción

---

## Resumen de Progreso

| Fase | Tareas | ✅ Done | ⬜ Pendiente |
|------|--------|---------|-------------|
| Fase 1 — Setup | 3 | 3 | 0 |
| Fase 2 — Foundational | 8 | 8 | 0 |
| Fase 3 — US1 Auth | 6 | 4 | 2 (T016 env, T017 smoke test) |
| Fase 4 — US2 Canales | 9 | 8 | 1 (T026 WhatsApp App Secret) |
| Fase 5 — US3 Servicios | 3 | 3 | 0 |
| Fase 6 — US4 Citas | 9 | 9 | 0 |
| Fase 7 — US5 Conversaciones | 6 | 5 | 1 (T043 LangGraph real) |
| Fase 8 — Polish | 5 | 4 | 1 (T046 WhatsApp tokens reales) |
| **Total** | **49** | **44** | **5** |

**Progreso general**: 90% completado (44/49 tareas)  
**Tareas pendientes** (requieren credenciales reales de Meta):
- T016: valores Supabase en .env (ya añadidos por usuario)
- T017: smoke test manual
- T026: WHATSAPP_APP_SECRET real
- T043: integrar LangGraph de citas (desarrollo futuro)
- T046: WHATSAPP_API_TOKEN + WHATSAPP_PHONE_NUMBER_ID reales
