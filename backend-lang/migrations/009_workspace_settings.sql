-- ============================================================
-- Migración 009 — workspaces.settings (JSONB) y unicidad de servicios por nombre dentro del workspace
-- Tarea: T015 | Decisiones: D-U6 (sin RLS), D3, D14, D15, D18 | US-003, FR-019..FR-024, FR-037..FR-041
-- Fecha: 2026-10-28
--
-- Sin BEGIN/COMMIT: la transacción la pone el runner (convención de 006/007/008). Idempotente (se puede aplicar dos veces).
-- La validación del contenido de settings (IANA, start<end, tono...) es de backend (T016); aquí solo "es un objeto JSON".
-- ============================================================

-- ── workspaces.settings ──────────────────────────────────────────────────────
ALTER TABLE public.workspaces ADD COLUMN IF NOT EXISTS settings JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE public.workspaces DROP CONSTRAINT IF EXISTS workspaces_settings_is_object;
ALTER TABLE public.workspaces ADD CONSTRAINT workspaces_settings_is_object
  CHECK (jsonb_typeof(settings) = 'object');

COMMENT ON COLUMN public.workspaces.settings IS
  'Claves: working_hours, onboarding, agent_tone, city, min_lead_minutes, cancel_cutoff_minutes. Contenido validado por backend.';

-- ── services: nombre único por workspace (sin distinguir mayúsculas ni espacios en los bordes) ──
-- Cubre TODAS las filas, también las inactivas (el borrado es soft delete y el histórico se conserva).
-- Pre-check: si hay duplicados se aborta SIN tocar datos; deduplicar es decisión humana.
DO $$
DECLARE n integer;
BEGIN
  SELECT count(*) INTO n FROM (
    SELECT 1 FROM public.services
    GROUP BY workspace_id, lower(btrim(name))
    HAVING count(*) > 1
  ) d;
  IF n > 0 THEN
    RAISE EXCEPTION '009 abortada: % grupo(s) de servicios duplicados (workspace_id, lower(btrim(name))); deduplicar manualmente y reintentar', n;
  END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS services_workspace_name_uq
  ON public.services (workspace_id, lower(btrim(name)));

-- ── DOWN (manual, en una transacción) ────────────────────────────────────────
-- DROP INDEX IF EXISTS public.services_workspace_name_uq;
-- ALTER TABLE public.workspaces DROP CONSTRAINT IF EXISTS workspaces_settings_is_object;
-- ALTER TABLE public.workspaces DROP COLUMN IF EXISTS settings;
