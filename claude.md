# Implementación y decisiones de diseño

CitasIA / Hilo: SaaS multi-tenant de citas por WhatsApp. Backend FastAPI + LangGraph en `backend-lang/`; esquema canónico en
`backend-lang/migrations/` (plan D14), aplicado en orden 001..N. Front en `front/`.

## T001 — Convergencia remota (006) y roles/rate_limits (007)

### Decisiones
- **Convergencia (D-U1 opción a):** la BD remota (creada por Alembic) no se reconstruye ni se borran datos. `006` agrega lo que falta
  frente a 001..005 y es idempotente (se puede aplicar dos veces; en una BD creada desde 001..005 no cambia nada).
- **idx_channels_phone_number_id** (parcial, no único, de Alembic): 006 lo borra después de crear `channels_phone_number_id_uq`, que lo
  sustituye (el canónico no lo tiene). El índice único es además requisito de `ON CONFLICT (phone_number_id)` en `kapso_onboarding.py`.
- **Defaults:** `channels.connection_type` sin default (antes 'coexistence' en remota) y `kapso_customers.setup_status` 'none'
  (antes 'pending'). Los INSERT de `api/routes/channels.py` no fijan connection_type: en la remota pasarán a guardar NULL, como el canónico.
- **member_role (007):** orden obligatorio DROP del CHECK (buscado por catálogo) → UPDATE owner→workspace_owner → ADD del CHECK nuevo.
  El DOWN (comentado al final de 007) hace lo inverso y borra rate_limits; probado en efímero.
- **rate_limits (D15):** PK (key, window_start), índice por window_start, RLS habilitado sin políticas: denegado a roles no
  privilegiados (probado). El backend usa el rol propietario de las tablas (en la remota `hilo_user`: no superusuario, sin BYPASSRLS,
  propietario de todas las tablas de public, sin FORCE RLS), por eso RLS no le aplica.

### Deudas aceptadas (no se tocan en T001)
- Columnas extra de Alembic: appointments.reminder_sent, reminder_1h_sent, reminder_24h_sent, users.password_hash, kapso_customers.id.
- `gen_random_uuid()` en la remota vs `uuid_generate_v4()` en el canónico: equivalentes.
- Tabla `alembic_version` (b1a2c3d4e5f6): no se actualiza; las migraciones SQL directas no la usan.

### Pendiente de PM (bloquea la aplicación en la remota)
1. **PK de kapso_customers:** remota PK(id) + UNIQUE(workspace_id); canónico PK(workspace_id). Opciones: (i) migrar la PK a
   workspace_id; (ii) aceptar la PK surrogate como equivalente funcional y excluirla del gate con autorización explícita.
2. **auth.uid() no existe en la remota** (PostgreSQL 17.11 Debian, no Supabase): las políticas de 001/006 no se pueden crear.
   Opciones: (a) crear `auth.uid()` stub en la remota; (b) políticas propias sin auth.uid(); (c) aceptar RLS sin políticas
   (denegado por defecto) y excluirlas del gate.
3. **Aviso:** la política canónica `wm_select` (001) se consulta a sí misma → "infinite recursion detected in policy" para roles no
   propietarios. Sin efecto en el backend (propietario); a corregir si algún cliente usa un rol limitado.

### Estado del gate (2026-10-28)
- Efímero limpio 001..007: PASS (diff 0 frente a la referencia, también tras DOWN + re-UP).
- Copia restaurada de la remota + stub auth.uid() + 006 + 007 en una transacción: criterios 10/10, queda solo la PK de kapso_customers
  → PASS con PK pendiente. Sin stub: 006 falla en CREATE POLICY y hace ROLLBACK limpio.
- Remota: **no aplicada**. T002–T004/T009 siguen bloqueadas hasta la decisión de PM.
