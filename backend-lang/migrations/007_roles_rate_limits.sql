-- ============================================================
-- Migración 007 — Rol workspace_owner en workspace_members y tabla rate_limits
-- Tarea: T001 | Decisiones: D-U1 (tras la convergencia 006), D-U6 (sin RLS), D14 (esquema canónico), D15 (rate_limits)
-- Fecha: 2026-10-28
--
-- Sin BEGIN/COMMIT: la transacción la pone el runner.
-- Orden obligatorio: DROP del CHECK → UPDATE owner→workspace_owner → ADD del CHECK nuevo
-- (el UPDATE antes del DROP viola el CHECK actual).
-- ============================================================

-- ── member_role: owner → workspace_owner ─────────────────────────────────────
-- El CHECK se busca por catálogo por si el nombre en la BD difiere del canónico.
DO $$
DECLARE c record;
BEGIN
  FOR c IN
    SELECT conname FROM pg_constraint
    WHERE conrelid = 'public.workspace_members'::regclass AND contype = 'c'
      AND pg_get_constraintdef(oid) LIKE '%member_role%'
  LOOP
    EXECUTE format('ALTER TABLE public.workspace_members DROP CONSTRAINT %I', c.conname);
  END LOOP;
END $$;

UPDATE public.workspace_members SET member_role = 'workspace_owner' WHERE member_role = 'owner';

ALTER TABLE public.workspace_members ADD CONSTRAINT workspace_members_member_role_check
  CHECK (member_role IN ('workspace_owner','manager','staff','viewer'));

-- ── rate_limits (D15): contador por clave y ventana ──────────────────────────
-- Sin RLS (D-U6): el aislamiento lo hace la aplicación (JWT propio).
CREATE TABLE IF NOT EXISTS public.rate_limits (
  key          TEXT NOT NULL,
  window_start TIMESTAMPTZ NOT NULL,
  hits         INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (key, window_start)
);
CREATE INDEX IF NOT EXISTS idx_rate_limits_window_start ON public.rate_limits (window_start);

-- ── DOWN (manual, en una transacción) ────────────────────────────────────────
-- ALTER TABLE public.workspace_members DROP CONSTRAINT IF EXISTS workspace_members_member_role_check;
-- UPDATE public.workspace_members SET member_role = 'owner' WHERE member_role = 'workspace_owner';
-- ALTER TABLE public.workspace_members ADD CONSTRAINT workspace_members_member_role_check
--   CHECK (member_role IN ('owner','manager','staff','viewer'));
-- DROP TABLE IF EXISTS public.rate_limits;
