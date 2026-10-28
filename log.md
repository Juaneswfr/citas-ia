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

# Cambios por agente

### [AGENTE: security] [FECHA: 2026-10-28 18:57 UTC]
**Cambios:**
- T003 (kanban t_6bbc73a8). JWT con `sub`, `email`, `role` (users.role), `member_role` (rol de la membresía) y `workspace_id`; `require_role` usa `member_role` (super_admin por `role`), rol ausente/desconocido = sin permiso.
- Login determinista: membresía activa más antigua (`ORDER BY COALESCE(joined_at, created_at), id LIMIT 1`). Sin membresía y `users.role` != super_admin → 403 "tu cuenta no tiene negocio asignado" sin token; se quita el respaldo "viewer".
- `POST /auth/refresh` consulta la BD (no confía en el token viejo): BD caída → 503; inactivo o sin membresía → 401 "Sesión inválida".
- `require_workspace_access` valida membresía activa en BD en cada request: BD caída/pool None/timeout 5 s → 503; sin membresía → 403; super_admin con workspace inexistente → 404.
- Eventos de log: auth.login.success/failed, token.invalid, token.expired (sin password, token ni email).
- Verificación: compileall exit 0; ad-hoc con dobles del pool 20/20; pytest con PYTHONPATH del worktree: 83 passed, 5 skipped, 0 failed (ver corrección de tests abajo).

**Archivos modificados:** backend-lang/src/core/security.py, backend-lang/src/api/routes/auth.py, log.md, claude.md, logs.md
**Commit:** ver `git log` (feat(auth): T003 JWT con member_role, login determinista, 403 sin membresías, refresh/membresía contra BD fail-closed 503)

**Actualizaciones a claude.md:**
- Decisiones T003: member_role en JWT, 503 fail-closed, 401 en refresh sin membresía, 404/403 de workspace.

### [AGENTE: security] [FECHA: 2026-10-28 18:58 UTC]
**Cambios:**
- T003 (kanban t_6bbc73a8), corrección: tests con el contrato de JWT viejo adaptados al nuevo (member_role, UUID válidos, doble del pool que devuelve la membresía activa). Aserciones 401/403/404 intactas, sin skip/xfail ni tests nuevos.
- tests/test_channels_roles.py y tests/test_kapso_onboarding.py: 8 fallos → 0. Suite completa: 83 passed, 5 skipped, 0 failed (PYTHONPATH=backend-lang/src); compileall exit 0.
- Sin cambios en código de producción.

**Archivos modificados:** backend-lang/tests/test_channels_roles.py, backend-lang/tests/test_kapso_onboarding.py, log.md, claude.md, logs.md
**Commit:** ver `git log` (test(auth): T003 adapta tests de roles/kapso al contrato JWT con member_role)

**Actualizaciones a claude.md:**
- Nota: los tests de guards deben inyectar el pool (core.database._pool) con la membresía; los claims usan member_role.
