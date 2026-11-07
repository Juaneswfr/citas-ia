-- 013: Ligar calendario a un miembro del equipo (barbero/agente).
-- Reemplaza UNIQUE(workspace_id, google_calendar_id) con dos índices parciales:
--   · uno para calendarios sin miembro (comportamiento anterior)
--   · otro para calendarios con miembro (un calendario por miembro por workspace)

ALTER TABLE calendars ADD COLUMN member_id UUID REFERENCES workspace_members(id) ON DELETE SET NULL;

-- Eliminar el único índice/constraint existente
ALTER TABLE calendars DROP CONSTRAINT IF EXISTS calendars_workspace_id_google_calendar_id_key;

-- Reemplazos parciales
CREATE UNIQUE INDEX idx_calendars_ws_gcal_unassigned
    ON calendars(workspace_id, google_calendar_id)
    WHERE member_id IS NULL;

CREATE UNIQUE INDEX idx_calendars_ws_member
    ON calendars(workspace_id, member_id)
    WHERE member_id IS NOT NULL;
