-- 016: Seguimiento por WhatsApp con plantillas (recordatorio, post-visita, cobro pendiente, reactivación).
-- El texto de las plantillas es fijo y vive en código (services/followup_templates.py); aquí solo se guarda
-- qué tiene activo cada barbería, el estado de aprobación en su cuenta de WhatsApp y el registro de envíos.
-- followup_sends garantiza un solo envío por cita/venta aunque el worker se reinicie
-- (sustituye a appointments.reminder_sent, que nunca estuvo en estas migraciones).
-- Sin RLS: el aislamiento entre workspaces lo hace la aplicación (decisión vigente).
-- (El runner envía cada trozo entre ';' a la BD: no dejar comentarios sueltos al final del archivo.)

-- ── Ajustes por workspace ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS followup_settings (
    workspace_id            UUID PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
    reminder_enabled        BOOLEAN NOT NULL DEFAULT TRUE,
    reminder_hours_before   INTEGER NOT NULL DEFAULT 24 CHECK (reminder_hours_before BETWEEN 1 AND 72),
    post_visit_enabled      BOOLEAN NOT NULL DEFAULT FALSE,
    post_visit_hours_after  INTEGER NOT NULL DEFAULT 2 CHECK (post_visit_hours_after BETWEEN 1 AND 24),
    payment_due_enabled     BOOLEAN NOT NULL DEFAULT FALSE,
    payment_due_days        INTEGER NOT NULL DEFAULT 1 CHECK (payment_due_days BETWEEN 1 AND 30),
    reactivation_enabled    BOOLEAN NOT NULL DEFAULT FALSE,
    reactivation_days       INTEGER NOT NULL DEFAULT 30 CHECK (reactivation_days BETWEEN 14 AND 365),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Estado de cada plantilla en la cuenta de WhatsApp del workspace ─────────
CREATE TABLE IF NOT EXISTS followup_templates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    kind            TEXT NOT NULL CHECK (kind IN ('reminder','post_visit','payment_due','reactivation')),
    template_name   TEXT NOT NULL,
    language        TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','approved','rejected','disabled','error')),
    detail          TEXT,
    synced_at       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (workspace_id, kind)
);

-- ── Registro de envíos ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS followup_sends (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    kind                TEXT NOT NULL CHECK (kind IN ('reminder','post_visit','payment_due','reactivation')),
    customer_id         UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    appointment_id      UUID REFERENCES appointments(id) ON DELETE CASCADE,
    sales_order_id      UUID REFERENCES sales_orders(id) ON DELETE CASCADE,
    status              TEXT NOT NULL DEFAULT 'sending' CHECK (status IN ('sending','sent','failed')),
    via                 TEXT CHECK (via IN ('template','text')),
    error               TEXT,
    provider_message_id TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Un envío por cita y tipo (recordatorio, post-visita) y uno por venta (cobro pendiente).
CREATE UNIQUE INDEX IF NOT EXISTS followup_sends_appointment_uq
    ON followup_sends(kind, appointment_id) WHERE appointment_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS followup_sends_order_uq
    ON followup_sends(kind, sales_order_id) WHERE sales_order_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_followup_sends_customer
    ON followup_sends(customer_id, kind, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_followup_sends_ws
    ON followup_sends(workspace_id, created_at DESC);

-- ── Columnas nuevas ─────────────────────────────────────────────────────────
-- El cliente pidió no recibir más mensajes promocionales (botón «No más mensajes»).
ALTER TABLE customers ADD COLUMN IF NOT EXISTS marketing_opt_out BOOLEAN NOT NULL DEFAULT FALSE;

-- El cliente pulsó «Confirmar» en el recordatorio.
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS confirmed_by_customer_at TIMESTAMPTZ;
