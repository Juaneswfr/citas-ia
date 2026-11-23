-- 023: Cuenta de cobro (documento, envío y consecutivo), datos de quien cobra, y costo real de la IA desde LangSmith.
-- El consecutivo sale de una secuencia: nunca se repite ni se reutiliza aunque se anule una cuenta de cobro.
-- La BD nunca guarda el PDF: se genera al vuelo desde los datos de la factura, así siempre refleja lo que hay en ella.
-- (El runner envía cada trozo entre ';' a la BD: no dejar comentarios sueltos al final del archivo.)

-- ── Quien emite la cuenta de cobro (una sola fila) ──────────────────────────
CREATE TABLE IF NOT EXISTS platform_issuer (
    id                   SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    legal_name           TEXT NOT NULL,
    id_type              TEXT NOT NULL DEFAULT 'CC' CHECK (id_type IN ('CC','NIT','CE','PASAPORTE')),
    id_number            TEXT NOT NULL,
    city                 TEXT,
    address              TEXT,
    email                TEXT,
    phone                TEXT,
    payment_instructions TEXT,
    legal_note           TEXT,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Consecutivo de las cuentas de cobro ─────────────────────────────────────
CREATE SEQUENCE IF NOT EXISTS billing_document_seq START 1;

-- ── La factura guarda cuándo se emitió la cuenta de cobro y a quién se envió ─
ALTER TABLE billing_invoices ADD COLUMN IF NOT EXISTS document_issued_at TIMESTAMPTZ;

ALTER TABLE billing_invoices ADD COLUMN IF NOT EXISTS last_sent_at TIMESTAMPTZ;

ALTER TABLE billing_invoices ADD COLUMN IF NOT EXISTS last_sent_to TEXT;

ALTER TABLE billing_invoices ADD COLUMN IF NOT EXISTS send_count INTEGER NOT NULL DEFAULT 0;

-- Un número de documento no se repite entre facturas vigentes.
CREATE UNIQUE INDEX IF NOT EXISTS billing_invoices_document_uq
    ON billing_invoices(document_number) WHERE document_number IS NOT NULL AND status <> 'void';

-- ── Costo real de la IA según LangSmith (la estimación por tokens queda en cost_usd) ─
ALTER TABLE agent_usage ADD COLUMN IF NOT EXISTS ls_runs INTEGER;

ALTER TABLE agent_usage ADD COLUMN IF NOT EXISTS ls_tokens BIGINT;

ALTER TABLE agent_usage ADD COLUMN IF NOT EXISTS ls_cost_usd NUMERIC(12,6);

ALTER TABLE agent_usage ADD COLUMN IF NOT EXISTS ls_synced_at TIMESTAMPTZ;

-- ── Registro de cada sincronización con LangSmith ───────────────────────────
CREATE TABLE IF NOT EXISTS langsmith_sync_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    day_from    DATE NOT NULL,
    day_to      DATE NOT NULL,
    runs        INTEGER NOT NULL DEFAULT 0,
    workspaces  INTEGER NOT NULL DEFAULT 0,
    cost_usd    NUMERIC(12,6) NOT NULL DEFAULT 0,
    without_cost INTEGER NOT NULL DEFAULT 0,
    error       TEXT
);

CREATE INDEX IF NOT EXISTS idx_langsmith_sync_log_started ON langsmith_sync_log(started_at DESC)
