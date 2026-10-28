

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
## 2026-10-27 — Agente de citas real (t_d43e2fb2)
  - services/appointment_agent.py nuevo: Haiku (mismo modelo del dispatcher) + tools listar_servicios, consultar_disponibilidad, crear_cita; workspace/cliente/canal/calendario salen del contexto, nunca del modelo
  - crear_cita reutiliza api.routes.appointments.create_appointment (free/busy + evento Calendar + INSERT + auditoría); la confirmación al cliente la redacta el backend solo si hubo fila en BD
  - Máx 5 herramientas por mensaje, timeout 45s; LLM caído/timeout → fallback honesto + agent_runs en error + agent_alerts
  - agent_service.py: reemplaza el TODO; envío por WhatsAppService sin cambios
  - tests/test_appointment_agent.py nuevo
  - No migré: sin reglas de horario laboral (solo free/busy), sin cancelar/reprogramar
## 2026-10-28 — T001 convergencia remota y roles (t_f215abc3, dba)
  - 006_convergencia_remota.sql y 007_roles_rate_limits.sql sin RLS (D-U6); aplicadas en la remota en una transacción, gate PASS
  - member_role 'owner' → 'workspace_owner'; tabla rate_limits(key, window_start, hits)
  - Riesgo hasta T002: guards require_workspace_access("owner") ya no coinciden con el rol migrado
## 2026-10-28 — T002 guards owner → workspace_owner (t_36af8fc3, security)
  - workspaces.py, services.py y billing.py: require_workspace_access("workspace_owner"); riesgo anterior resuelto
  - pytest backend-lang: 83 passed, 5 skipped
