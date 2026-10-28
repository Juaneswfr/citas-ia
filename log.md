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

### [AGENTE: security] [FECHA: 2026-10-28 UTC]
**Cambios:**
- T002 (t_36af8fc3): `require_workspace_access("owner")` → `("workspace_owner")` en workspaces.py (invite_member, remove_member), services.py (deactivate_service, 2 usos) y billing.py (get_subscription). Textos: "Requiere rol workspace_owner." y cabecera de services.py.
- Motivo: ROLE_HIERARCHY no contiene "owner"; el guard era inalcanzable salvo super_admin. security.py/auth.py sin tocar (T003/T004).
- Verificación: grep sin literales "owner" sueltos en los 3 archivos; `PYTHONPATH=src .venv/bin/pytest -q` en backend-lang: 83 passed, 5 skipped, 0 failed.

**Archivos modificados:** backend-lang/src/api/routes/workspaces.py, services.py, billing.py, log.md, claude.md, logs.md
**Commit:** ver `git log` (feat(auth): T002 reemplazar rol owner por workspace_owner ...)

**Actualizaciones a claude.md:**
- Riesgo de guards "owner" resuelto; pendiente T003/T004.

### [AGENTE: security] [FECHA: 2026-10-28 UTC]
**Cambios:**
- T004 (t_e4ed4773): `PATCH /workspaces/{id}` sigue con guard `manager`, pero `is_active` explícito solo lo admiten `super_admin` y `workspace_owner` (403 "Permisos insuficientes para esta operación." si no). `MemberInvite.member_role` documenta `workspace_owner`.
- CORS explícito (FR-009): `CORS_ALLOWED_ORIGINS` (coma-separada, default = origen de `FRONTEND_URL`); `*` o entradas vacías abortan el arranque con error que nombra la variable. `main.py` usa esa lista, con métodos y cabeceras explícitos (Authorization, Content-Type, X-XSRF-TOKEN, X-Correlation-ID).
- Rate limit (FR-008, D15) en `core/security.py`: `rate_limit_hit` (upsert de ventana fija sobre `rate_limits`, hits desde 1), `rate_limit_purge`, `enforce_login_rate_limit` (10/min por IP; al exceder, bloqueo de 15 min; 429 + Retry-After; BD caída → 503), `client_ip` (X-Real-IP solo con `TRUST_PROXY_HEADERS=true`; nunca X-Forwarded-For). `POST /auth/login` lo invoca antes de consultar usuario y bcrypt; log `auth.login.rate_limited` solo con ip.
- `reminder_worker._reminder_loop` llama a `rate_limit_purge(24h)` en cada ciclo (errores solo se registran).
- `pyproject.toml`: `[tool.pytest.ini_options] pythonpath = ["src"]` (sin él, pytest del venv del repo principal importaba el `src` del repo principal y no el del worktree).
- Tests nuevos: tests/test_t004_rate_limit_cors_is_active.py (13). Suite backend-lang: 96 passed, 5 skipped, 0 failed.

**Archivos modificados:** backend-lang/src/api/main.py, api/routes/auth.py, api/routes/workspaces.py, core/config.py, core/security.py, schemas/workspace.py, workers/reminder_worker.py, backend-lang/pyproject.toml, backend-lang/tests/test_t004_rate_limit_cors_is_active.py, log.md, logs.md, claude.md
**Commit:** ver `git log` (feat(auth): T004 ...)

**Actualizaciones a claude.md:**
- Sección T004: decisiones (CORS, rate limit, trust_proxy_headers), sin adaptaciones de fixtures y pendientes (T010/T012, T034, T006).

### [AGENTE: security] [FECHA: 2026-10-28 UTC]
**Cambios:**
- T004 corrección (revisión de seguridad): el bloqueo de login de 15 min era de ventana fija alineada al reloj (podía durar ~1 s). Ahora `enforce_login_rate_limit` inserta una fila `login:block:{ip}` con `window_start = now()` (ON CONFLICT DO NOTHING) al exceder 10/min, y antes de contar comprueba si existe una con `window_start > now() - 900 s` → 429 con `Retry-After = max(1, 900 - edad)`. Los intentos bloqueados no cuentan ni extienden el bloqueo. Límite por minuto sin cambios.
- Tests: reescrito el de bloqueo y añadido `test_login_block_is_rolling_900s_from_trigger` (899 s → 429, 901 s → no bloqueado). Suite: 97 passed, 5 skipped.

**Archivos modificados:** backend-lang/src/core/security.py, backend-lang/tests/test_t004_rate_limit_cors_is_active.py, log.md, logs.md, claude.md
**Commit:** ver `git log` (fix(auth): T004 bloqueo de login de 15 min ...)

**Actualizaciones a claude.md:**
- Decisión de bloqueo rolling de 900 s desde el último disparo.
