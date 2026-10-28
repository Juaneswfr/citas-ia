-- ============================================================
-- Migración 006 — Convergencia de la BD remota con 001..005
-- Tarea: T001 | Decisión: D-U1 opción a (convergencia, sin reconstruir ni borrar datos) | Plan: D14
-- Fecha: 2026-10-28
--
-- Idempotente: en una BD creada con 001..005 no cambia nada; en la remota agrega lo que
-- le falta frente al canónico. Se puede aplicar dos veces.
-- No toca (deuda documentada en claude.md): columnas extra de Alembic
-- (appointments.reminder_sent, reminder_1h_sent, reminder_24h_sent, users.password_hash,
-- kapso_customers.id), alembic_version, gen_random_uuid() vs uuid_generate_v4() (equivalentes)
-- ni la PK de kapso_customers (remota PK(id) vs canónica PK(workspace_id): decisión de PM).
-- Las políticas usan auth.uid() como 001: la BD destino debe tenerla (Supabase o stub).
-- ============================================================

-- ── kapso_webhook_events (003, definición exacta) ────────────────────────────
CREATE TABLE IF NOT EXISTS public.kapso_webhook_events (
  idempotency_key TEXT PRIMARY KEY,
  event           TEXT NOT NULL,
  received_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── kapso_customers (004): CHECK de setup_status y UNIQUE(kapso_customer_id) ───
ALTER TABLE public.kapso_customers DROP CONSTRAINT IF EXISTS kapso_customers_setup_status_check;
ALTER TABLE public.kapso_customers ADD CONSTRAINT kapso_customers_setup_status_check
  CHECK (setup_status IN ('none','pending','connected'));
ALTER TABLE public.kapso_customers DROP CONSTRAINT IF EXISTS kapso_customers_kapso_customer_id_key;
ALTER TABLE public.kapso_customers ADD CONSTRAINT kapso_customers_kapso_customer_id_key
  UNIQUE (kapso_customer_id);

-- ── channels (004/005): índices únicos ───────────────────────────────────────
CREATE UNIQUE INDEX IF NOT EXISTS channels_phone_number_id_uq
  ON public.channels (phone_number_id);
CREATE UNIQUE INDEX IF NOT EXISTS channels_webhook_token_uq
  ON public.channels (webhook_token);
-- Índice parcial no único de Alembic: queda sustituido por channels_phone_number_id_uq.
DROP INDEX IF EXISTS public.idx_channels_phone_number_id;

-- ── Defaults como 004 ────────────────────────────────────────────────────────
ALTER TABLE public.channels ALTER COLUMN connection_type DROP DEFAULT;
ALTER TABLE public.kapso_customers ALTER COLUMN setup_status SET DEFAULT 'none';

-- ── Políticas RLS (001, nombres y expresiones exactos) ───────────────────────
DROP POLICY IF EXISTS wm_select ON public.workspace_members;
CREATE POLICY wm_select ON public.workspace_members
    FOR SELECT USING (
        workspace_id IN (
            SELECT workspace_id FROM public.workspace_members
            WHERE user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS channels_select ON public.channels;
CREATE POLICY channels_select ON public.channels
    FOR SELECT USING (
        workspace_id IN (
            SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS calendars_select ON public.calendars;
CREATE POLICY calendars_select ON public.calendars
    FOR SELECT USING (
        workspace_id IN (
            SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS services_select ON public.services;
CREATE POLICY services_select ON public.services
    FOR SELECT USING (
        workspace_id IN (
            SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS customers_select ON public.customers;
CREATE POLICY customers_select ON public.customers
    FOR SELECT USING (
        workspace_id IN (
            SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS appointments_select ON public.appointments;
CREATE POLICY appointments_select ON public.appointments
    FOR SELECT USING (
        workspace_id IN (
            SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS conversations_select ON public.conversations;
CREATE POLICY conversations_select ON public.conversations
    FOR SELECT USING (
        workspace_id IN (
            SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS messages_select ON public.messages;
CREATE POLICY messages_select ON public.messages
    FOR SELECT USING (
        workspace_id IN (
            SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS agent_alerts_select ON public.agent_alerts;
CREATE POLICY agent_alerts_select ON public.agent_alerts
    FOR SELECT USING (
        workspace_id IN (
            SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS subscriptions_select ON public.subscriptions;
CREATE POLICY subscriptions_select ON public.subscriptions
    FOR SELECT USING (
        workspace_id IN (
            SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS audit_logs_select ON public.audit_logs;
CREATE POLICY audit_logs_select ON public.audit_logs
    FOR SELECT USING (
        workspace_id IN (
            SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
        )
    );
