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

### [AGENTE: dba] [FECHA: 2026-10-28 13:59 UTC]
**Cambios:**
- Nueva migración `backend-lang/migrations/007_roles_rate_limits.sql` (T001, D-U1, D14, D15) [kanban: t_3cc1eaad]:
  - Bloque 1 (transacción): DROP por catálogo del CHECK de `workspace_members.member_role` → UPDATE `owner`→`workspace_owner` → ADD `workspace_members_member_role_check` con `('workspace_owner','manager','staff','viewer')`.
  - Bloque 2 (transacción): tabla `rate_limits(key, window_start, hits)` con PK `(key, window_start)`, índice `idx_rate_limits_window_start` y RLS activo sin políticas.
  - DOWN manual comentado al final.
- Validado en PostgreSQL 16.14 efímero (no en la remota): 001..005 + 007 dos veces, exit 0; INSERT `owner` falla (23514), INSERT `workspace_owner` ok, 0 filas `owner` (3 → 0); upsert de rate_limits devuelve 1 y 2; `relrowsecurity=true`; DOWN y re-up exit 0. `test_migrations_integration.py` 5 passed; suite backend 88 passed.
- No se creó ningún `006_*.sql` (lo hace otra tarea, D-U1).

**Archivos modificados:** backend-lang/migrations/007_roles_rate_limits.sql, log.md, claude.md
**Commit:** ver git log (mensaje "feat(db): T001 roles workspace_owner y rate_limits (007) [kanban: t_3cc1eaad]")

**Actualizaciones a claude.md:**
- Nombre 007 (006 reservado), orden DROP→UPDATE→ADD y RLS sin políticas en rate_limits.
