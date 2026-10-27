-- Migración 005 — Webhook por número de Kapso (Lote 4)
-- webhook_token va en la URL (/webhooks/kapso/n/{token}); el secreto de firma se guarda cifrado
-- (Fernet, KAPSO_SECRETS_KEY), nunca en claro. El índice único permite varios NULL.
ALTER TABLE public.channels ADD COLUMN IF NOT EXISTS webhook_token TEXT;
ALTER TABLE public.channels ADD COLUMN IF NOT EXISTS kapso_webhook_id TEXT;
ALTER TABLE public.channels ADD COLUMN IF NOT EXISTS webhook_secret_encrypted TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS channels_webhook_token_uq
  ON public.channels (webhook_token);
