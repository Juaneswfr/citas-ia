

27-10-2026
  Backend Python:
  - supabase==2.10.0 + postgrest → asyncpg==0.29.0
  - core/database.py nuevo — pool asyncpg con codecs UUID/JSONB
  - core/config.py — DATABASE_URL reemplaza las 3 vars de Supabase
  - api/main.py — pool se inicializa/cierra en lifespan
  - Todos los routes (auth, services, workspaces, appointments, channels, billing, conversations) — Supabase queries → asyncpg
   directo
  - Todos los services (audit, conversation, agent, calendar) + reminder_worker — mismo cambio
  - supabase_client.py eliminado

  Frontend:
  - @supabase/supabase-js desinstalado, drizzle-orm + pg + jose instalados
  - drizzle.config.ts + src/db/schema.ts (13 tablas) + src/db/client.ts nuevos
  - auth-context.tsx — JWT en localStorage, sin Supabase auth
  - _authenticated.tsx — verifica JWT localStorage en lugar de supabase.auth.getSession()
  - auth-middleware.ts — jwtVerify con jose, sin Supabase
  - auth-attacher.ts — lee de localStorage
  - auth/callback.tsx — redirige a /login (OAuth eliminado)
  - verify-email.tsx — sin Supabase
  - .env actualizado

  No migré / riesgos:
  - Las 13 tablas aún no existen en el nuevo Postgres — necesitas npx drizzle-kit migrate para crearlas
  - Los datos de Supabase aún no migraron — necesitas un pg_dump desde Supabase y un psql import al nuevo Postgres
  - Usuarios existentes no tienen password_hash — deberán resetear contraseña tras la migración
  - La columna reminder_24h_sent/reminder_2h_sent en appointments puede no existir en Supabase — verifica antes de migrar
  datos
## 2026-10-27 — Kapso outbound (t_24ff8dbb)
  - whatsapp_service.py: `send_text` (devuelve SendResult) y `send_message(provider=)`; provider "kapso" envía por KapsoProvider con KAPSO_API_KEY/KAPSO_BASE_URL; Meta sin cambios
  - whatsapp_provider.py: reintento acotado (máx 2, backoff ≤2s) en 429 y 5xx; 4xx sin reintento; logs de Kapso sin teléfono
  - agent_service.py: envío fallido → run en error + agent_alerts, sin guardar outbound; guarda provider_message_id (wamid)
  - tests/test_kapso_outbound.py nuevo
  - No migré: reminder_worker sigue enviando solo por Meta (no recibe provider del canal)

### [AGENTE: backend] [FECHA: 2026-10-27 18:00 UTC]
**Cambios (P5 agente de citas, t_d43e2fb2):**
- Nuevo `backend-lang/src/agents/citas/`: grafo LangGraph (agent ⇄ tools → finalize), herramientas `check_availability`, `create_appointment`, `cancel_appointment`, puertos (`ports.py`), repositorio asyncpg (`repository.py`), fábrica LLM (`llm.py`), errores tipados.
- `AgentService.run` ya no devuelve texto fijo: llama a `_run_agent` (LLM + asyncpg + CalendarService). Envío WhatsApp, outbound y manejo `envio_whatsapp_fallido` intactos. Sin `AGENT_LLM_API_KEY` → `LLMNotConfigured` → run en error + agent_alerts, sin respuesta.
- IDs workspace/customer/channel/conversation fijados desde la conversación (`CitasContext`); no están en el esquema de herramientas y args extra se rechazan. IDs de servicio/calendario/cita se validan en BD dentro del workspace; cancelar exige workspace_id y customer_id fijos.
- Escritura de cita: tx asyncpg → `pg_advisory_xact_lock(calendar)` → solape en BD (appointments + availability_blocks) → INSERT 'confirmed' → free/busy y create_event en Calendar → guardar google_event_id → commit. Calendar falla → rollback. La confirmación solo existe tras salir limpio de la tx; si una escritura falla, `finalize` descarta el texto del LLM y responde mensaje fijo de fallo. Cancelación: UPDATE + delete_event dentro de la tx; si Calendar falla, rollback.
- Cada herramienta se registra en `tool_calls`. Settings nuevos: AGENT_LLM_PROVIDER, AGENT_LLM_MODEL, AGENT_LLM_API_KEY (sin valores por defecto secretos). `_build_context` ahora trae `workspaces.timezone`.
- Tests: `tests/test_citas_agent.py` (nuevo); `tests/test_kapso_outbound.py` parchea `_run_agent`.

**Hallazgos para DBA (no se creó nada):** no hay constraint de no-solapamiento en `appointments`. Hoy la garantía es advisory lock + SELECT en la app (solo cubre escrituras del agente; el endpoint POST /appointments no lo usa). Se necesita `EXCLUDE USING gist (calendar_id WITH =, tstzrange(start_at,end_at) WITH &&) WHERE (status IN ('pending','confirmed'))` (requiere btree_gist) o equivalente.
**Pendientes:** horario laboral fijo 09:00-18:00 (no hay tabla de horarios); el endpoint appointments.py sigue creando en Calendar antes de insertar y sin tx (no se tocó).

**Archivos modificados:** backend-lang/src/agents/citas/*, src/services/agent_service.py, src/core/config.py, .env.example, tests/test_citas_agent.py, tests/test_kapso_outbound.py, logs.md, CLAUDE.md
**Commit:** ver `git log` (mensaje con [kanban: t_d43e2fb2])

**Actualizaciones a CLAUDE.md:**
- Se añade la sección "Agente de citas" con las decisiones de diseño.
