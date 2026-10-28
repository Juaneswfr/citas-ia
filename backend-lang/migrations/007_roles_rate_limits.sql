-- ============================================================
-- Migración 007 — Rol workspace_owner en workspace_members y tabla rate_limits
-- Tarea: T001 | Decisiones: D-U1 (006 queda para la convergencia remota), D14 (esquema canónico), D15 (rate_limits)
-- [kanban: t_3cc1eaad] (tarjeta padre t_f215abc3)
-- Fecha: 2026-10-28
--
-- Idempotente: puede ejecutarse dos veces y deja el mismo estado.
-- Orden obligatorio en el bloque 1: DROP del CHECK → UPDATE owner→workspace_owner → ADD del CHECK nuevo
-- (con el CHECK actual el UPDATE a 'workspace_owner' viola la restricción).
-- ============================================================

-- ── Bloque 1: member_role owner → workspace_owner ────────────────────────────
BEGIN;

-- El CHECK se busca por catálogo porque el nombre en la BD puede diferir del canónico.
-- Si no hay CHECK no hace nada; si ya es el nuevo, se elimina y se vuelve a crear abajo.
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

COMMIT;

-- ── Bloque 2: rate_limits (D15), contador por clave y ventana fija ───────────
BEGIN;

CREATE TABLE IF NOT EXISTS public.rate_limits (
  key          TEXT NOT NULL,
  window_start TIMESTAMPTZ NOT NULL,
  hits         INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (key, window_start)
);

-- Para la limpieza de ventanas viejas que hace el reminder worker.
CREATE INDEX IF NOT EXISTS idx_rate_limits_window_start ON public.rate_limits (window_start);

-- RLS activo SIN políticas, a propósito: el backend se conecta como propietario de la tabla
-- (el propietario no queda sujeto a RLS sin FORCE) y los demás roles quedan denegados.
-- No se crean políticas basadas en el esquema auth de Supabase: la BD remota no lo tiene.
ALTER TABLE public.rate_limits ENABLE ROW LEVEL SECURITY;

COMMIT;

-- ── DOWN (manual, en una transacción) ────────────────────────────────────────
-- BEGIN;
-- ALTER TABLE public.workspace_members DROP CONSTRAINT IF EXISTS workspace_members_member_role_check;
-- UPDATE public.workspace_members SET member_role = 'owner' WHERE member_role = 'workspace_owner';
-- ALTER TABLE public.workspace_members ADD CONSTRAINT workspace_members_member_role_check
--   CHECK (member_role IN ('owner','manager','staff','viewer'));
-- DROP TABLE IF EXISTS public.rate_limits;
-- COMMIT;
