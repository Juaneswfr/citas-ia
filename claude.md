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

## T009 — Cuenta: 008_auth_tokens_trial.sql (dba, 2026-10-28)

### Decisiones
- **Nombre 008** (no 007: 007 ya es `007_roles_rate_limits.sql` de T001). Sin BEGIN/COMMIT, idempotente.
- **Sin RLS** en auth_tokens ni en ningún cambio (D-U6).
- **workspaces.slug ya es UNIQUE desde 001** (`workspaces_slug_key`): 008 solo comprueba por catálogo (pg_index, `indnatts=1`
  e `indkey[0]` = attnum de slug; `indkey` es int2vector base 0, comparar como array no funciona) y crea `workspaces_slug_uq`
  solo si falta. En la BD canónica es no-op. `idx_workspaces_slug` (no único) se conserva.
- **Plan Trial:** name='Trial', price_cop=0, billing_interval='one_time', is_active=TRUE; INSERT ... WHERE NOT EXISTS.
- **Backfill (único mecanismo, US-013(b)):** subscriptions 'trial' con el plan Trial para cada workspace sin fila;
  current_period_start NULL (FR-106: fallback a workspaces.created_at). Filas existentes intactas.
- **subscriptions.status:** DROP por catálogo de los CHECK que mencionan status → ADD `subscriptions_status_check` con 'trial'.
- **users.email_verified_at** TIMESTAMPTZ NULL. CHECK de users.role sin cambios.
- **auth_tokens:** solo `token_hash` (SHA-256 hex, UNIQUE), nunca el token en claro; un solo uso vía `used_at`;
  ON DELETE CASCADE desde users; índice (user_id, purpose).
- **DOWN** (comentado al final de 008, probado): cambia datos a propósito trial→pending_payment; el plan Trial se borra
  solo si no está referenciado, si no queda is_active=FALSE.

### Deudas / abiertas
- La duración del trial (14 días) no tiene columna en billing_plans; la administra super_admin (FR-106) — falta decidir dónde vive.
- 008 **no aplicada en la remota**: solo validada en PG 17.10 efímero; la aplicación remota la autoriza el usuario.

## T010 — Registro transaccional (backend, 2026-10-28)

### Decisiones
- **Capas:** `auth.py:register` valida/delega; `services/registration_service.py:register_owner(db, NewAccount, hash_password)` tiene el SQL y la lógica; errores tipados `EmailTaken`, `SlugExhausted`, `RegistrationUnavailable`.
- **Transacción por intento** (user + workspace + `workspace_members` workspace_owner + `subscriptions` status `trial` con el plan semilla `Trial`). Si falta el plan Trial → rollback y 503. `current_period_*` quedan NULL como en T009.
- **Email repetido (D16):** 400 genérico "No se pudo crear la cuenta. El email puede estar en uso."; enumeración aceptada. El precheck es solo un atajo; la garantía es la violación 23505 de `users.email` en el INSERT (carrera → 400, nunca 500). Una 23505 de constraint desconocida también da 400 con log (nunca 500).
- **Slug:** 23505 sobre constraint con "slug" → rollback del intento y reintento `base`, `base-2` … hasta 5 intentos; agotado → mismo 400 genérico. Sin validación de patrón nueva (no cambia el contrato).
- **503 + rollback:** `get_db` usa `acquire(timeout=5)` (D10); pool None, timeout o error de conexión → 503 genérico. Fallos de BD dentro del registro → 503; el rollback deshace toda la transacción. `database.py` se tocó solo para esto.
- Logs: errores 5xx con stack trace; sin password, hash ni email en logs (solo constraint y tipo de error).

### Pendientes
- **FR-104** (rate limit de registro, 5/hora/IP): no implementado; lo asigna T012.
- Duración del trial (14 días, FR-106): sin columna en `billing_plans`; decisión abierta.
- Carrera real con dos conexiones y PostgreSQL: solo probada con dobles; real en T012/T058.
- Seguridad debe validar: enumeración D16, mensajes genéricos, ausencia de SQL en respuestas, hash bcrypt, carrera por constraint.
