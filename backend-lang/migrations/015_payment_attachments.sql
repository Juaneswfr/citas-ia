-- 015: Comprobantes de pago adjuntos a cada movimiento (cobro/pago/gasto).
-- Los archivos viven en disco (UPLOADS_DIR); aquí solo se guarda el metadato.
-- storage_key es relativo a UPLOADS_DIR ("<workspace_id>/<uuid>.<ext>"): nunca se usa el nombre del usuario en disco.

CREATE TABLE IF NOT EXISTS movement_attachments (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id  UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    movement_id   UUID NOT NULL REFERENCES movements(id) ON DELETE CASCADE,
    original_name TEXT NOT NULL,
    content_type  TEXT NOT NULL
                  CHECK (content_type IN ('image/jpeg','image/png','image/webp','application/pdf')),
    size_bytes    INTEGER NOT NULL CHECK (size_bytes > 0),
    storage_key   TEXT NOT NULL UNIQUE,
    uploaded_by   UUID REFERENCES users(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_movement_attachments_movement
    ON movement_attachments(movement_id);

CREATE INDEX IF NOT EXISTS idx_movement_attachments_ws
    ON movement_attachments(workspace_id);
