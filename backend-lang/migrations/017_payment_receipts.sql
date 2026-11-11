-- 017: Comprobantes de pago recibidos por WhatsApp, pendientes de que el negocio los confirme.
-- Tabla aparte de movement_attachments porque allí movement_id es NOT NULL: un comprobante recibido
-- todavía no tiene cobro. Al aprobarlo se registra el cobro y el archivo se adjunta a ese movimiento.
-- storage_key es relativo a UPLOADS_DIR ("<workspace_id>/receipts/<uuid>.<ext>").
-- Sin RLS: el aislamiento entre workspaces lo hace la aplicación (decisión vigente).
-- (El runner envía cada trozo entre ';' a la BD: no dejar comentarios sueltos al final del archivo.)

CREATE TABLE IF NOT EXISTS payment_receipts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    customer_id     UUID REFERENCES customers(id) ON DELETE SET NULL,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    message_id      UUID REFERENCES messages(id) ON DELETE SET NULL,
    storage_key     TEXT NOT NULL UNIQUE,
    content_type    TEXT NOT NULL
                    CHECK (content_type IN ('image/jpeg','image/png','image/webp','application/pdf')),
    size_bytes      INTEGER NOT NULL CHECK (size_bytes > 0),
    -- Datos leídos de la imagen (pueden venir vacíos o equivocados: el negocio los revisa).
    amount_cop      INTEGER CHECK (amount_cop IS NULL OR amount_cop > 0),
    paid_on         DATE,
    method          TEXT CHECK (method IS NULL OR method IN ('cash','transfer','card','nequi','other')),
    reference       TEXT,
    bank            TEXT,
    payer_name      TEXT,
    raw             JSONB NOT NULL DEFAULT '{}',
    -- Revisión
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
    sales_order_id  UUID REFERENCES sales_orders(id) ON DELETE SET NULL,
    movement_id     UUID REFERENCES movements(id) ON DELETE SET NULL,
    reviewed_by     UUID REFERENCES users(id),
    reviewed_at     TIMESTAMPTZ,
    reject_reason   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_payment_receipts_ws_status
    ON payment_receipts(workspace_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_payment_receipts_customer
    ON payment_receipts(customer_id);

-- Un mismo mensaje de WhatsApp no genera dos comprobantes (reintentos del webhook).
CREATE UNIQUE INDEX IF NOT EXISTS payment_receipts_message_uq
    ON payment_receipts(message_id) WHERE message_id IS NOT NULL;
