-- Migración 004 — Onboarding Kapso (P2)
-- channels.phone_number_id lo usa el código (conversation_service, channels) pero no estaba
-- en 001; IF NOT EXISTS lo hace seguro en BDs que ya lo tengan. El índice único impide que
-- un número quede asociado a dos workspaces.
ALTER TABLE public.channels ADD COLUMN IF NOT EXISTS phone_number_id TEXT;
ALTER TABLE public.channels ADD COLUMN IF NOT EXISTS connection_type TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS channels_phone_number_id_uq
  ON public.channels (phone_number_id);

CREATE TABLE IF NOT EXISTS public.kapso_customers (
  workspace_id           UUID PRIMARY KEY REFERENCES public.workspaces(id) ON DELETE CASCADE,
  kapso_customer_id      TEXT NOT NULL UNIQUE,
  setup_link_id          TEXT,
  setup_link_url         TEXT,
  setup_link_expires_at  TIMESTAMPTZ,
  setup_status           TEXT NOT NULL DEFAULT 'none'
                         CHECK (setup_status IN ('none','pending','connected')),
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);
