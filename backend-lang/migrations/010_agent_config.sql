-- 010: Configuración del agente de WhatsApp
-- Separada de business_hours (horario de citas) — el agente puede tener su propio horario de respuesta.

CREATE TABLE IF NOT EXISTS agent_config (
    workspace_id UUID PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
    agent_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    out_of_hours_message TEXT NOT NULL DEFAULT 'Hola! Por ahora estamos fuera de horario. Te responderemos en cuanto abramos. 🤙',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_hours (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    day_of_week SMALLINT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    open_time TIME NOT NULL DEFAULT '09:00',
    close_time TIME NOT NULL DEFAULT '21:00',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE(workspace_id, day_of_week)
);

CREATE INDEX IF NOT EXISTS idx_agent_hours_ws ON agent_hours(workspace_id);
