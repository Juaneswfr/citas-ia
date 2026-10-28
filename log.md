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

### [AGENTE: backend] [FECHA: 2026-10-28 19:15 UTC]
**Cambios:**
- T010 (kanban t_4082481c): registro transaccional. Nuevo `services/registration_service.py` (`register_owner`, errores tipados `EmailTaken`/`SlugExhausted`/`RegistrationUnavailable`); `auth.py:register` solo delega y traduce a HTTP.
- Una transacción por intento (user + workspace + membresía workspace_owner + suscripción `trial` con el plan semilla Trial de T009). Violación 23505 de workspaces slug → reintento `base`, `base-2`…`base-5`; agotado → 400 genérico. Violación de users.email (carrera) → 400 genérico. Fallo de BD/pool → 503 con rollback.
- `core/database.py` tocado POR NECESIDAD DE T010 (fuera de la lista de archivos): `get_db` usa `acquire(timeout=5)` (D10) y pool None/timeout/error de conexión → 503. `core/security.py` solo reusa la constante (`DB_ACQUIRE_TIMEOUT = database.ACQUIRE_TIMEOUT`).
- Tests `tests/test_t010_register.py` (9, con dobles). Suite backend: 106 passed, 6 skipped (antes 97/6). compileall exit 0. Sin PostgreSQL real disponible: la carrera real queda para T012/T058.

**Archivos modificados:** backend-lang/src/api/routes/auth.py, backend-lang/src/services/registration_service.py, backend-lang/src/core/database.py, backend-lang/src/core/security.py, backend-lang/tests/test_t010_register.py, log.md, claude.md, logs.md
**Commit:** ver `git log` (feat(auth): T010 registro transaccional ...)

**Actualizaciones a claude.md:**
- Sección T010 con decisiones y pendientes (FR-104, duración del trial, validación de slug).
