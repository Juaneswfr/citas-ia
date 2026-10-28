-- ============================================================
-- Migración 008 — Cuenta: email_verified_at, auth_tokens, CHECK de subscriptions.status con 'trial',
-- plan Trial, backfill de trial y slug único
-- Tarea: T009 | Decisiones: D-U1, D-U6 (sin RLS), D14, US-002, US-013(b), FR-106
-- Fecha: 2026-10-28
--
-- Sin BEGIN/COMMIT: la transacción la pone el runner. Idempotente (se puede aplicar dos veces).
-- ============================================================

-- ── users.email_verified_at ──────────────────────────────────────────────────
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ NULL;

-- ── auth_tokens: verificación de email y reset de contraseña (sin RLS, D-U6) ──
CREATE TABLE IF NOT EXISTS public.auth_tokens (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  purpose    TEXT NOT NULL CHECK (purpose IN ('email_verification','password_reset')),
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at    TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_auth_tokens_user_purpose ON public.auth_tokens (user_id, purpose);
COMMENT ON COLUMN public.auth_tokens.token_hash IS
  'Solo el hash SHA-256 (hex) del token; el token en claro nunca se guarda.';
COMMENT ON COLUMN public.auth_tokens.used_at IS 'Un solo uso: se marca al consumirse.';

-- ── subscriptions.status: añade 'trial' ──────────────────────────────────────
-- Ensanchamiento: DROP (por catálogo, el nombre puede diferir) → ADD; no hace falta UPDATE.
DO $$
DECLARE c record;
BEGIN
  FOR c IN
    SELECT conname FROM pg_constraint
    WHERE conrelid = 'public.subscriptions'::regclass AND contype = 'c'
      AND pg_get_constraintdef(oid) LIKE '%status%'
  LOOP
    EXECUTE format('ALTER TABLE public.subscriptions DROP CONSTRAINT %I', c.conname);
  END LOOP;
END $$;

ALTER TABLE public.subscriptions ADD CONSTRAINT subscriptions_status_check
  CHECK (status IN ('trial','active','pending_payment','suspended','cancelled','expired'));

-- ── Plan semilla Trial ───────────────────────────────────────────────────────
INSERT INTO public.billing_plans (name, description, price_cop, billing_interval, is_active)
SELECT 'Trial', 'Plan de prueba; duración administrable por super_admin (FR-106)', 0, 'one_time', TRUE
WHERE NOT EXISTS (SELECT 1 FROM public.billing_plans WHERE name = 'Trial');

-- ── Backfill (US-013(b)): trial para cada workspace sin suscripción ───────────
-- current_period_start queda NULL: el inicio del trial cae a workspaces.created_at (FR-106).
INSERT INTO public.subscriptions (workspace_id, billing_plan_id, status)
SELECT w.id,
       (SELECT id FROM public.billing_plans WHERE name = 'Trial' ORDER BY created_at LIMIT 1),
       'trial'
FROM public.workspaces w
WHERE NOT EXISTS (SELECT 1 FROM public.subscriptions s WHERE s.workspace_id = w.id);

-- ── workspaces.slug: índice único solo si falta (001 ya lo crea con UNIQUE) ───
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_index i
    WHERE i.indrelid = 'public.workspaces'::regclass AND i.indisunique AND i.indpred IS NULL
      AND i.indnatts = 1  -- indkey es int2vector base 0: se compara indkey[0], no el array
      AND i.indkey[0] = (SELECT attnum FROM pg_attribute
                         WHERE attrelid = 'public.workspaces'::regclass AND attname = 'slug')
  ) THEN
    CREATE UNIQUE INDEX workspaces_slug_uq ON public.workspaces (slug);
  END IF;
END $$;

-- ── DOWN (manual, en una transacción) ────────────────────────────────────────
-- El paso 3 CAMBIA DATOS a propósito: las suscripciones 'trial' pasan a 'pending_payment' para que el CHECK
-- original de 001 las acepte (no se pueden borrar sin perder la relación workspace→plan).
-- DROP TABLE IF EXISTS public.auth_tokens;
-- ALTER TABLE public.users DROP COLUMN IF EXISTS email_verified_at;
-- UPDATE public.subscriptions SET status = 'pending_payment' WHERE status = 'trial';
-- ALTER TABLE public.subscriptions DROP CONSTRAINT IF EXISTS subscriptions_status_check;
-- ALTER TABLE public.subscriptions ADD CONSTRAINT subscriptions_status_check
--   CHECK (status IN ('active','pending_payment','suspended','cancelled','expired'));
-- UPDATE public.billing_plans SET is_active = FALSE
--   WHERE name = 'Trial' AND EXISTS (SELECT 1 FROM public.subscriptions s WHERE s.billing_plan_id = billing_plans.id);
-- DELETE FROM public.billing_plans b
--   WHERE b.name = 'Trial' AND NOT EXISTS (SELECT 1 FROM public.subscriptions s WHERE s.billing_plan_id = b.id);
