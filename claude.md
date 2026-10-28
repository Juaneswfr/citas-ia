# Implementación y decisiones de diseño

Citas-IA: backend FastAPI + LangGraph en backend-lang, front TanStack Start en front, datos en Supabase/PostgreSQL.

- Decisión (FR-105): front/drizzle.config.ts lee solo DATABASE_URL y falla si falta; no hay credencial por defecto.
- Pendiente (pregunta abierta 8): rotar la credencial que sigue en el historial git.

<!-- integrado desde feat/003-t001 (T001) -->
# Implementación y decisiones de diseño

CitasIA / Hilo: SaaS multi-tenant de citas por WhatsApp. Backend FastAPI + LangGraph en `backend-lang/`; esquema canónico en
`backend-lang/migrations/` (plan D14), aplicado en orden 001..N. Front en `front/`.

## T001 — Convergencia remota (006) y roles/rate_limits (007)

### Decisiones
- **Convergencia (D-U1 opción a):** la BD remota (creada por Alembic) no se reconstruye ni se borran datos. `006` agrega lo que falta
  frente a 001..005 y es idempotente (aplicada dos veces en efímero: exit 0; en una BD creada desde 001..005 no cambia nada).
  Contenido: `kapso_webhook_events` (003 exacta), CHECK `kapso_customers_setup_status_check`, UNIQUE(kapso_customer_id) solo si no
  existe (DO block), índices únicos `channels_phone_number_id_uq` y `channels_webhook_token_uq`, defaults como 004.
- **Sin RLS (D-U6):** 006 y 007 no crean ni borran políticas ni habilitan RLS (`grep POLICY|ROW LEVEL` = 0). `rate_limits` sin RLS.
  Riesgo aceptado: el aislamiento entre workspaces depende solo de la aplicación (JWT, require_workspace_access).
- **PK surrogate de kapso_customers (D-U5):** se conserva PK(id) + UNIQUE(workspace_id) en la remota; no se migra a PK(workspace_id).
- **idx_channels_phone_number_id** (parcial, no único, de Alembic): se conserva; la unicidad la cubre `channels_phone_number_id_uq`.
- **Defaults:** `channels.connection_type` sin default (antes 'coexistence' en remota) y `kapso_customers.setup_status` 'none'
  (antes 'pending'). Los INSERT de `api/routes/channels.py` no fijan connection_type: en la remota guardarán NULL, como el canónico.
- **member_role (007):** orden obligatorio DROP del CHECK (buscado por catálogo) → UPDATE owner→workspace_owner → ADD del CHECK nuevo.
  El DOWN (comentado al final de 007) hace lo inverso y borra rate_limits; probado en efímero (DOWN + re-UP exit 0).
- **rate_limits (D15):** PK (key, window_start), índice por window_start. `hits` DEFAULT 0: el upsert
  `INSERT (key, window_start) ... ON CONFLICT DO UPDATE SET hits = hits + 1` devuelve 0 y luego 1; para contar desde 1 hay que
  insertar `hits = 1` en VALUES (lo debe tener en cuenta T004).

### Deudas aceptadas (no se tocan en T001)
- Columnas extra de Alembic: appointments.reminder_sent, reminder_1h_sent, reminder_24h_sent, users.password_hash, kapso_customers.id.
- `gen_random_uuid()` en la remota vs `uuid_generate_v4()` en el canónico: equivalentes (la remota no tiene uuid-ossp).
- Tabla `alembic_version` (b1a2c3d4e5f6): no se actualiza; las migraciones SQL directas no la usan.
- PK surrogate de kapso_customers (D-U5).
- Las 11 políticas `*_select` de 001 no existen en la remota (sin esquema `auth`); fuera del gate por D-U6.

### Estado del gate (2026-10-28 18:38 UTC)
- Efímero limpio PG 17.10, 001..005 + 006 + 006 + 007: criterios 12/12, PASS. Tests de migraciones: 5 passed.
- Copia fiel (pg_dump 17.11 de la remota restaurado sin stubs) + 006 + 007 en una transacción: PASS; solo diferencias permitidas.
- **Remota (PG 17.11): aplicada** en una transacción (006 + 007, COMMIT) y verificada por catálogo en solo lectura: PASS, catálogo
  idéntico a la copia ensayada. Backup previo: `scratch/t001/remote_backup_20261028T183712Z.dump` (sha256 51368880…910b).
- Pendiente inmediato: T002 (los guards `require_workspace_access("owner")` en workspaces.py, services.py y billing.py ya no
  coinciden con el rol migrado `workspace_owner` hasta que T002 los cambie).

## T003 — JWT con member_role y guard contra BD (t_6bbc73a8, security)
- **JWT:** `role` = users.role (p.ej. super_admin o null); `member_role` = rol de la membresía del workspace emitido. La jerarquía de `require_role` usa `member_role`; super_admin va por `role`. Rol desconocido o ausente → sin permiso.
- **503 fail-closed:** cualquier fallo de BD (pool None, timeout de acquire de 5 s, error asyncpg/OSError) en `require_workspace_access` y `/auth/refresh` responde 503, nunca 401 ni 2xx, para que el front distinga BD caída de sesión inválida.
- **Refresh:** ignora rol/workspace del token viejo; usuario inactivo o sin membresía activa (y no super_admin) → 401 "Sesión inválida" (el front cierra sesión).
- **Workspace:** sin membresía activa → 403 sin revelar si el workspace existe; super_admin con workspace inexistente → 404. `workspace_id` que no es UUID se trata como inexistente (403/404).
- **Login:** membresía activa más antigua; sin membresía y no super_admin → 403 "tu cuenta no tiene negocio asignado", sin token.
- **Pendiente (fuera de alcance):** guards `"owner"` en services.py:155,160 y billing.py:61 (T002); tests con contrato JWT viejo en test_channels_roles.py y test_kapso_onboarding.py (T006); `register` guarda users.role='workspace_owner'; no hay endpoint de logout.
