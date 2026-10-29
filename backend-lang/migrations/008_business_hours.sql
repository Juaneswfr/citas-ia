-- 008_business_hours.sql
-- Horario de atención del negocio por día de la semana.
-- day_of_week: 0=Lunes … 6=Domingo (semana ISO)

CREATE TABLE IF NOT EXISTS business_hours (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id  UUID    NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    day_of_week   SMALLINT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    open_time     TIME    NOT NULL DEFAULT '09:00',
    close_time    TIME    NOT NULL DEFAULT '19:00',
    is_open       BOOLEAN NOT NULL DEFAULT true,
    UNIQUE (workspace_id, day_of_week)
);

CREATE INDEX IF NOT EXISTS idx_business_hours_workspace ON business_hours(workspace_id);
