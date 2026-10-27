-- Migración 003 — Idempotencia de webhooks Kapso (P3)
-- La PK única permite reclamar la clave con INSERT ... ON CONFLICT DO NOTHING
-- antes de procesar; un reintento con la misma clave no inserta fila.
CREATE TABLE IF NOT EXISTS public.kapso_webhook_events (
  idempotency_key TEXT PRIMARY KEY,
  event           TEXT NOT NULL,
  received_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
