-- ============================================================
-- Migración 002 — Agrega business_type a workspaces
-- Fecha: 2026-06-29
-- Ejecutar en: Supabase Dashboard → SQL Editor
-- ============================================================

ALTER TABLE public.workspaces
  ADD COLUMN IF NOT EXISTS business_type TEXT;

COMMENT ON COLUMN public.workspaces.business_type IS
  'Tipo de negocio: barberia | salon | manicure | spa | otro';
