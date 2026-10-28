-- ============================================================
-- Migración 010 — calendars: canal push de Google y sync incremental; tabla oauth_states (nonce de un solo uso)
-- Tarea: T023 | Decisiones: D2, D-U1, D-U6 (sin RLS), D14 | US-005, FR-032..FR-036
-- Fecha: 2026-10-28
--
-- Sin BEGIN/COMMIT: la transacción la pone el runner (convención de 006..009). Idempotente (se puede aplicar dos veces).
-- Columnas nuevas nacen NULL: no hace falta pre-check de datos.
-- ============================================================

-- ── calendars.connected_by_user_id: FK con ON DELETE SET NULL ────────────────
-- Sigue NULLABLE (filas previas a OAuth no tienen usuario); el calendario sobrevive a la salida del usuario.
-- DROP por catálogo (el nombre puede diferir en la remota) → ADD con nombre fijo.
DO $$
DECLARE c record;
BEGIN
  FOR c IN
    SELECT con.conname FROM pg_constraint con
    JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = ANY (con.conkey)
    WHERE con.conrelid = 'public.calendars'::regclass AND con.contype = 'f'
      AND a.attname = 'connected_by_user_id'
  LOOP
    EXECUTE format('ALTER TABLE public.calendars DROP CONSTRAINT %I', c.conname);
  END LOOP;
END $$;

ALTER TABLE public.calendars ADD CONSTRAINT calendars_connected_by_user_id_fkey
  FOREIGN KEY (connected_by_user_id) REFERENCES public.users(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS calendars_connected_by_user_id_idx ON public.calendars (connected_by_user_id);

-- ── calendars: canal push y sync token ───────────────────────────────────────
ALTER TABLE public.calendars ADD COLUMN IF NOT EXISTS google_notification_channel_id TEXT NULL;
ALTER TABLE public.calendars ADD COLUMN IF NOT EXISTS google_channel_token_hash TEXT NULL;
ALTER TABLE public.calendars ADD COLUMN IF NOT EXISTS google_channel_expires_at TIMESTAMPTZ NULL;
ALTER TABLE public.calendars ADD COLUMN IF NOT EXISTS next_sync_token TEXT NULL;

ALTER TABLE public.calendars DROP CONSTRAINT IF EXISTS calendars_google_channel_token_hash_format;
ALTER TABLE public.calendars ADD CONSTRAINT calendars_google_channel_token_hash_format
  CHECK (google_channel_token_hash IS NULL OR google_channel_token_hash ~ '^[0-9a-f]{64}$');

ALTER TABLE public.calendars DROP CONSTRAINT IF EXISTS calendars_google_channel_pair;
ALTER TABLE public.calendars ADD CONSTRAINT calendars_google_channel_pair
  CHECK ((google_notification_channel_id IS NULL) = (google_channel_token_hash IS NULL));

-- Búsqueda del calendario por X-Goog-Channel-ID en el webhook.
CREATE UNIQUE INDEX IF NOT EXISTS calendars_google_channel_id_uq
  ON public.calendars (google_notification_channel_id) WHERE google_notification_channel_id IS NOT NULL;

COMMENT ON COLUMN public.calendars.google_notification_channel_id IS 'Id del canal push de Google (X-Goog-Channel-ID).';
COMMENT ON COLUMN public.calendars.google_channel_token_hash IS
  'Solo el hash SHA-256 (hex minúsculas) de X-Goog-Channel-Token; el token en claro nunca se guarda. Comparar con hmac.compare_digest.';
COMMENT ON COLUMN public.calendars.google_channel_expires_at IS 'Caducidad del canal push (renovar antes).';
COMMENT ON COLUMN public.calendars.next_sync_token IS 'Sync token incremental de Google Calendar.';

-- ── oauth_states: nonce de un solo uso del OAuth (FR-032, D2; sin RLS, D-U6) ──
-- La caducidad (10 min) la fija el backend al insertar. Consumo atómico:
-- UPDATE ... SET used_at = now() WHERE nonce = $1 AND used_at IS NULL AND expires_at > now() RETURNING ...
CREATE TABLE IF NOT EXISTS public.oauth_states (
  nonce        UUID PRIMARY KEY,
  workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  user_id      UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  expires_at   TIMESTAMPTZ NOT NULL,
  used_at      TIMESTAMPTZ NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT oauth_states_expires_after_created CHECK (expires_at > created_at),
  CONSTRAINT oauth_states_used_after_created CHECK (used_at IS NULL OR used_at >= created_at)
);
CREATE INDEX IF NOT EXISTS oauth_states_expires_at_idx ON public.oauth_states (expires_at);
CREATE INDEX IF NOT EXISTS oauth_states_workspace_id_idx ON public.oauth_states (workspace_id);
CREATE INDEX IF NOT EXISTS oauth_states_user_id_idx ON public.oauth_states (user_id);

-- ── DOWN (manual, en una transacción) ────────────────────────────────────────
-- ATENCIÓN: borra datos (canales push, hashes de token y sync tokens de calendars; todos los oauth_states).
-- DROP TABLE IF EXISTS public.oauth_states;
-- DROP INDEX IF EXISTS public.calendars_google_channel_id_uq;
-- DROP INDEX IF EXISTS public.calendars_connected_by_user_id_idx;
-- ALTER TABLE public.calendars DROP CONSTRAINT IF EXISTS calendars_google_channel_pair;
-- ALTER TABLE public.calendars DROP CONSTRAINT IF EXISTS calendars_google_channel_token_hash_format;
-- ALTER TABLE public.calendars DROP COLUMN IF EXISTS next_sync_token;
-- ALTER TABLE public.calendars DROP COLUMN IF EXISTS google_channel_expires_at;
-- ALTER TABLE public.calendars DROP COLUMN IF EXISTS google_channel_token_hash;
-- ALTER TABLE public.calendars DROP COLUMN IF EXISTS google_notification_channel_id;
-- ALTER TABLE public.calendars DROP CONSTRAINT IF EXISTS calendars_connected_by_user_id_fkey;
-- ALTER TABLE public.calendars ADD CONSTRAINT calendars_connected_by_user_id_fkey
--   FOREIGN KEY (connected_by_user_id) REFERENCES public.users(id);
