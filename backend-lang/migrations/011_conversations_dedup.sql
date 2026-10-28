-- ============================================================
-- Migración 011 — conversations: last_inbound_at, pending_booking; índice único de mensaje del proveedor
-- Tarea: T032 | Decisiones: D5, D6, D7, D14 | US-007, FR-042, FR-058, FR-071
-- Fecha: 2026-10-28
--
-- Sin BEGIN/COMMIT: la transacción la pone el runner. Idempotente.
-- Columnas nuevas nacen NULL, sin DEFAULT. Sin cambios de RLS (D-U6).
-- ============================================================

-- ── conversations: ventana de 24 h (FR-071, D7) y reserva pendiente (FR-058) ──
ALTER TABLE public.conversations ADD COLUMN IF NOT EXISTS last_inbound_at TIMESTAMPTZ NULL;
ALTER TABLE public.conversations ADD COLUMN IF NOT EXISTS pending_booking JSONB NULL;

ALTER TABLE public.conversations DROP CONSTRAINT IF EXISTS conversations_pending_booking_is_object;
ALTER TABLE public.conversations ADD CONSTRAINT conversations_pending_booking_is_object
  CHECK (pending_booking IS NULL OR jsonb_typeof(pending_booking) = 'object');

-- Backfill: último inbound por conversación. Solo filas aún NULL (idempotente).
UPDATE public.conversations c SET last_inbound_at = s.last_in
FROM (SELECT conversation_id, MAX(COALESCE(received_at, created_at)) AS last_in
      FROM public.messages WHERE direction = 'inbound' GROUP BY conversation_id) s
WHERE c.id = s.conversation_id AND c.last_inbound_at IS NULL;

COMMENT ON COLUMN public.conversations.last_inbound_at IS
  'Último mensaje inbound del cliente; base de can_send_freeform (ventana de 24 h, FR-071).';
COMMENT ON COLUMN public.conversations.pending_booking IS
  'Reserva propuesta pendiente de confirmación explícita (objeto JSON, FR-058).';

-- ── messages: dedup por id de mensaje del proveedor (wamid, FR-042) ──────────
-- Pre-check: nunca borra ni deduplica filas; si hay duplicados aborta y hay que auditar.
DO $$
DECLARE n bigint;
BEGIN
  SELECT count(*) INTO n FROM (
    SELECT provider_message_id FROM public.messages
    WHERE provider_message_id IS NOT NULL
    GROUP BY provider_message_id HAVING count(*) > 1
  ) d;
  IF n > 0 THEN
    RAISE EXCEPTION 'Migración 011: % grupos de messages.provider_message_id duplicados. Audítelos (sin borrado automático) antes de reintentar.', n;
  END IF;
END $$;

-- Parcial: outbound sin id de proveedor (NULL) puede coexistir. Árbitro de
-- INSERT ... ON CONFLICT (provider_message_id) WHERE provider_message_id IS NOT NULL DO NOTHING
CREATE UNIQUE INDEX IF NOT EXISTS messages_provider_message_id_uq
  ON public.messages (provider_message_id) WHERE provider_message_id IS NOT NULL;

-- ── DOWN (manual, en una transacción) ────────────────────────────────────────
-- DROP INDEX IF EXISTS public.messages_provider_message_id_uq;
-- ALTER TABLE public.conversations DROP CONSTRAINT IF EXISTS conversations_pending_booking_is_object;
-- ATENCIÓN: borra datos (reservas pendientes).
-- ALTER TABLE public.conversations DROP COLUMN IF EXISTS pending_booking;
-- ATENCIÓN: borra datos (último inbound; se puede recalcular con el backfill de arriba).
-- ALTER TABLE public.conversations DROP COLUMN IF EXISTS last_inbound_at;
