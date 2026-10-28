# Cambios por agente

### [AGENTE: security] [FECHA: 2026-10-28 12:58 UTC]
**Cambios:**
- front/drizzle.config.ts: se quita la URL de PostgreSQL con credenciales como valor por defecto (FR-105). Ahora lee solo `process.env.DATABASE_URL` y lanza un error explícito si falta.
- Verificado: sin DATABASE_URL el config falla (exit 1, mensaje explícito); con valor ficticio carga y expone dbCredentials.url.
- git grep de credenciales en el working tree: 0 archivos. Historial: 1 commit (c1a5e31) la introdujo. La rotación NO se hizo (pregunta abierta 8 de la spec); la hace el usuario.

**Archivos modificados:** front/drizzle.config.ts, log.md, claude.md
**Commit:** ver git log (mensaje "fix(security): quita credencial por defecto de front/drizzle.config.ts (FR-105)")

**Actualizaciones a claude.md:**
- Se crea claude.md con la decisión: drizzle.config.ts sin credenciales por defecto.

<!-- integrado desde feat/003-t001 (T001) -->
# Cambios por agente

### [AGENTE: dba] [FECHA: 2026-10-28 13:55 UTC]
**Cambios:**
- T001 (kanban t_f215abc3), alcance de convergencia D-U1 opción a.
- `006_convergencia_remota.sql` (idempotente): kapso_webhook_events (003), CHECK kapso_customers_setup_status_check, UNIQUE(kapso_customer_id), índices únicos channels_phone_number_id_uq y channels_webhook_token_uq (sustituyen al parcial idx_channels_phone_number_id), defaults connection_type NULL y setup_status 'none', 11 políticas `*_select` de 001.
- `007_roles_rate_limits.sql`: DROP del CHECK de member_role por catálogo → UPDATE owner→workspace_owner → ADD CHECK ('workspace_owner','manager','staff','viewer'); tabla rate_limits (PK key, window_start) con RLS sin políticas. DOWN en comentario.
- Ensayo en PostgreSQL 17.10 efímero: 001..005 + 006 + 006 + 007, DOWN y re-UP: exit 0; tests de migraciones 5 passed, suite backend 88 passed.
- Backup de la remota (pg_dump 17.11) y ensayo sobre copia restaurada: con stub auth.uid() el gate pasa salvo la PK de kapso_customers; sin stub 006 falla (la remota no tiene esquema `auth`).
- **No se aplicó nada en la remota**: PK de kapso_customers pendiente de PM y ausencia de auth.uid() en la remota (ver claude.md).

**Archivos modificados:** backend-lang/migrations/006_convergencia_remota.sql, backend-lang/migrations/007_roles_rate_limits.sql, log.md, claude.md
**Commit:** ver `git log` (feat(db): T001 convergencia remota (006) y roles/rate_limits (007))

**Actualizaciones a claude.md:**
- Creado con las decisiones de T001, deudas aceptadas y estado del gate.

### [AGENTE: dba] [FECHA: 2026-10-28 18:38 UTC]
**Cambios:**
- T001 reanudada con D-U1/D-U5/D-U6: 006 sin políticas RLS (quitados los 11 DROP/CREATE POLICY), UNIQUE(kapso_customer_id) solo si no existe, se conserva idx_channels_phone_number_id. 007 sin `ENABLE ROW LEVEL SECURITY` en rate_limits.
- Ensayo PG 17.10 efímero: 001..005 + 006 + 006 + 007 exit 0; DOWN y re-UP exit 0; tests de migraciones 5 passed.
- Remota: comprobaciones de datos a–d = 0, sin FK a kapso_customers.id; backup pg_dump 17.11; ensayo en copia fiel PASS.
- **Aplicadas 006 y 007 en la remota** en una transacción; gate de catálogo post-aplicación PASS (1 fila owner → workspace_owner).

**Archivos modificados:** backend-lang/migrations/006_convergencia_remota.sql, backend-lang/migrations/007_roles_rate_limits.sql, log.md, claude.md, logs.md
**Commit:** ver `git log` (feat(db): T001 convergencia remota (006) y roles/rate_limits (007))

**Actualizaciones a claude.md:**
- Sin RLS (D-U6), PK surrogate aceptada (D-U5), estado del gate con la remota aplicada, riesgo de guards "owner" hasta T002.

### [AGENTE: dba] [FECHA: 2026-10-28 18:54 UTC]
**Cambios:**
- T009 (kanban t_37460f88): `008_auth_tokens_trial.sql` — users.email_verified_at, tabla auth_tokens (solo hash, sin RLS),
  CHECK de subscriptions.status con 'trial' (DROP por catálogo → ADD), plan semilla Trial (0 COP, one_time), backfill trial
  para workspaces sin suscripción, índice único de slug solo si falta (no-op: 001 ya lo tiene). DOWN comentado y probado.
- Test nuevo `test_migration_008_trial_and_auth_tokens` en tests/test_migrations_integration.py.
- Ensayo PG 17.10 efímero: 001..007 + 008 + 008, verificaciones 3a–3h PASS, DOWN + re-UP PASS; tests de migraciones 6 passed;
  suite backend 89 passed. **No se aplicó nada en la remota.**

**Archivos modificados:** backend-lang/migrations/008_auth_tokens_trial.sql, backend-lang/tests/test_migrations_integration.py, log.md, claude.md, logs.md
**Commit:** ver `git log` (feat(db): T009 cuenta — email_verified_at, auth_tokens, ...)

**Actualizaciones a claude.md:**
- Sección T009 con decisiones (008, slug ya UNIQUE, plan Trial one_time, backfill, auth_tokens solo hash, sin RLS) y deudas.

### [AGENTE: dba] [FECHA: 2026-10-28 20:00 UTC]
**Cambios:**
- T015 (kanban t_e8af0109): `009_workspace_settings.sql` — workspaces.settings JSONB NOT NULL DEFAULT '{}' con CHECK `workspaces_settings_is_object`
  (jsonb_typeof = 'object'); índice único `services_workspace_name_uq` sobre (workspace_id, lower(btrim(name))) en TODAS las filas;
  pre-check DO que aborta con EXCEPTION si hay duplicados (no modifica datos). DOWN comentado y probado.
- 2 tests nuevos `test_migration_009_*` en tests/test_migrations_integration.py.
- Ensayo PG 16.4 efímero: 001..008 + 009 + 009 PASS, DOWN == esquema 008 PASS, re-UP PASS, pre-check con duplicados PASS (datos intactos);
  suite 91 passed (con TEST_DATABASE_URL) / 83 passed, 8 skipped (sin). **No se aplicó nada en la remota.**

**Archivos modificados:** backend-lang/migrations/009_workspace_settings.sql, backend-lang/tests/test_migrations_integration.py, log.md, claude.md, logs.md
**Commit:** ver `git log` (feat(db): T015 workspaces.settings y unicidad de servicios)

**Actualizaciones a claude.md:**
- Sección T015 con decisiones (009, sin BEGIN/COMMIT, unicidad sobre todas las filas, pre-check sin borrado, settings objeto) y notas para T016.

### [AGENTE: dba] [FECHA: 2026-10-28 19:09 UTC]
**Cambios:**
- T023 (kanban t_03e1441b): `010_calendar_oauth.sql` — calendars: FK `calendars_connected_by_user_id_fkey` pasa a ON DELETE SET NULL
  (DROP por catálogo → ADD; columna sigue NULLABLE) + índice `calendars_connected_by_user_id_idx`; columnas `google_notification_channel_id`,
  `google_channel_token_hash` (CHECK SHA-256 hex `^[0-9a-f]{64}$`), `google_channel_expires_at`, `next_sync_token`; CHECK de par canal/hash;
  índice único parcial `calendars_google_channel_id_uq`. Tabla nueva `oauth_states` (nonce UUID PK, FKs CASCADE a workspaces/users,
  CHECKs de fechas, 3 índices), sin RLS. DOWN comentado y probado.
- 3 tests nuevos `test_migration_010_*` en tests/test_migrations_integration.py.
- Ensayo PG 17.10 efímero: 001..009 + 010 + 010 PASS (snapshot idéntico), DOWN == esquema 009 PASS, re-UP PASS; tests de migraciones 11 passed;
  suite 94 passed (con TEST_DATABASE_URL) / 83 passed, 11 skipped (sin); ruff exit 0. **No se aplicó nada en la remota.**

**Archivos modificados:** backend-lang/migrations/010_calendar_oauth.sql, backend-lang/tests/test_migrations_integration.py, log.md, claude.md, logs.md
**Commit:** ver `git log` (feat(db): T023 calendars push/sync y oauth_states)

**Actualizaciones a claude.md:**
- Sección T023 con decisiones (010, token de canal solo como hash, oauth_states sin RLS, FK SET NULL) y notas para T024–T026.

### [AGENTE: dba] [FECHA: 2026-10-28 19:15 UTC]
**Cambios:**
- T032 (kanban t_ac7ee21a): `011_conversations_dedup.sql` — conversations.last_inbound_at TIMESTAMPTZ NULL y pending_booking JSONB NULL
  (CHECK `conversations_pending_booking_is_object`), ambas sin DEFAULT; backfill idempotente de last_inbound_at desde el último inbound;
  pre-check DO que aborta (EXCEPTION con el conteo) si hay provider_message_id duplicados, sin borrar datos; índice único parcial
  `messages_provider_message_id_uq` (WHERE provider_message_id IS NOT NULL). DOWN comentado y probado.
- 6 tests nuevos `test_migration_011_*` (columnas, CHECK, índice/ON CONFLICT, backfill + idempotencia, pre-check con duplicados, DOWN == esquema 010 + re-UP).
- Ensayo PG 17.10 efímero: 001..011 + 011 PASS, DOWN + re-UP PASS; suite 100 passed (con TEST_DATABASE_URL) / 83 passed, 17 skipped (sin); ruff exit 0.
  **No se aplicó nada en la remota.**

**Archivos modificados:** backend-lang/migrations/011_conversations_dedup.sql, backend-lang/tests/test_migrations_integration.py, log.md, claude.md, logs.md
**Commit:** ver `git log` (feat(db): T032 índice único de provider_message_id, last_inbound_at y pending_booking)

**Actualizaciones a claude.md:**
- Sección T032 con decisiones (011, índice parcial, pre-check sin borrado, backfill) y notas para T033.
