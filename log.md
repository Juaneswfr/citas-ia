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
