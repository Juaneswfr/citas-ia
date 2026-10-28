-- ============================================================
-- Migración 006 — Convergencia de la BD remota con 001..005
-- Tarea: T001 | Decisiones: D-U1 opción a (convergencia, sin reconstruir ni borrar datos),
--        D-U5 (PK surrogate de kapso_customers aceptada), D-U6 (sin RLS) | Plan: D14
-- Fecha: 2026-10-28
--
-- Idempotente: en una BD creada con 001..005 no cambia nada; en la remota agrega lo que
-- le falta frente al canónico. Se puede aplicar dos veces. Sin BEGIN/COMMIT (lo pone el runner).
-- D-U6: no crea ni borra políticas ni habilita/deshabilita RLS.
-- D-U5: no toca la PK de kapso_customers (remota PK(id) + UNIQUE(workspace_id)).
-- No toca (deuda documentada en claude.md): columnas extra de Alembic
-- (appointments.reminder_sent, reminder_1h_sent, reminder_24h_sent, users.password_hash,
-- kapso_customers.id), alembic_version, ni los DEFAULT gen_random_uuid() de la remota
-- (equivalentes a uuid_generate_v4() de 001; diferencia aceptada).
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

-- Equivale a "IF NOT EXISTS": solo se agrega si no hay ya un UNIQUE exacto sobre la columna.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'public.kapso_customers'::regclass AND contype = 'u'
      AND pg_get_constraintdef(oid) = 'UNIQUE (kapso_customer_id)'
  ) THEN
    ALTER TABLE public.kapso_customers ADD CONSTRAINT kapso_customers_kapso_customer_id_key
      UNIQUE (kapso_customer_id);
  END IF;
END $$;

-- ── channels (004/005): índices únicos ───────────────────────────────────────
CREATE UNIQUE INDEX IF NOT EXISTS channels_phone_number_id_uq
  ON public.channels (phone_number_id);
CREATE UNIQUE INDEX IF NOT EXISTS channels_webhook_token_uq
  ON public.channels (webhook_token);
-- El índice parcial no único idx_channels_phone_number_id (Alembic, solo en la remota) no está
-- en el canónico; se conserva (inocuo, la unicidad la cubre channels_phone_number_id_uq).

-- ── Defaults como 004 ────────────────────────────────────────────────────────
ALTER TABLE public.channels ALTER COLUMN connection_type DROP DEFAULT;
ALTER TABLE public.kapso_customers ALTER COLUMN setup_status SET DEFAULT 'none';
