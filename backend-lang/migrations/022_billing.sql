-- 022: Planes (Emprendedor y Equipo), suscripciones con prueba y ciclo, citas adicionales, facturas de cobro manual,
-- eventos para medir el embudo y la cobranza, consumo de IA por día y reclamos de oferta por número.
-- El código que la usa falla «abierto» si aún no está aplicada: el agente y las citas siguen como antes.
-- Ver documentation/zumit-plan-de-pagos-y-sus.md. No hay pasarela: el super_admin registra los pagos.
-- Los negocios que ya existen NO reciben suscripción: sin fila se tratan como «sin plan asignado» y siguen igual.
-- (El runner envía cada trozo entre ';' a la BD: no dejar comentarios sueltos al final del archivo.)

-- ── Planes ──────────────────────────────────────────────────────────────────
ALTER TABLE billing_plans ADD COLUMN IF NOT EXISTS code TEXT;

ALTER TABLE billing_plans ADD COLUMN IF NOT EXISTS launch_price_cop INTEGER CHECK (launch_price_cop >= 0);

ALTER TABLE billing_plans ADD COLUMN IF NOT EXISTS max_appointments INTEGER CHECK (max_appointments >= 0);

ALTER TABLE billing_plans ADD COLUMN IF NOT EXISTS max_professionals INTEGER CHECK (max_professionals >= 0);

ALTER TABLE billing_plans ADD COLUMN IF NOT EXISTS extra_professional_price_cop INTEGER NOT NULL DEFAULT 0;

-- Los planes del modelo anterior (Gratis, Básico, Pro) no tienen código: se ocultan, no se borran.
UPDATE billing_plans SET is_active = FALSE WHERE code IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS billing_plans_code_uq ON billing_plans(code);

INSERT INTO billing_plans
    (code, name, description, price_cop, launch_price_cop, billing_interval,
     max_appointments, max_professionals, extra_professional_price_cop,
     max_channels, max_calendars, max_services, max_messages)
VALUES
    ('emprendedor', 'Emprendedor', 'Independiente o barbería pequeña', 120000, 50000, 'monthly', 250, 3, 40000, 1, 3, 1000, 0),
    ('equipo',   'Equipo',   'Barbería con equipo',               285000, 120000, 'monthly', 550, 6, 40000, 1, 6, 1000, 0)
ON CONFLICT (code) DO NOTHING;

-- ── Suscripciones ───────────────────────────────────────────────────────────
ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS subscriptions_status_check;

ALTER TABLE subscriptions ADD CONSTRAINT subscriptions_status_check
    CHECK (status IN ('trial','active','past_due','paused','cancelled','expired','pending_payment','suspended'));

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS trial_started_at TIMESTAMPTZ;

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMPTZ;

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS activated_at TIMESTAMPTZ;

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS cycle_anchor_day SMALLINT CHECK (cycle_anchor_day BETWEEN 1 AND 31);

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS discount_cycles_remaining INTEGER NOT NULL DEFAULT 0 CHECK (discount_cycles_remaining >= 0);

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS is_founder BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS founder_number INTEGER;

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS frozen_price_cop INTEGER CHECK (frozen_price_cop >= 0);

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS cancel_at_period_end BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS pending_plan_id UUID REFERENCES billing_plans(id);

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS past_due_since TIMESTAMPTZ;

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS paused_at TIMESTAMPTZ;

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS data_purge_after TIMESTAMPTZ;

-- Una sola suscripción viva por negocio (las canceladas y vencidas quedan como historial).
CREATE UNIQUE INDEX IF NOT EXISTS subscriptions_one_live_per_workspace
    ON subscriptions(workspace_id)
    WHERE status IN ('trial','active','past_due','paused','pending_payment');

CREATE UNIQUE INDEX IF NOT EXISTS subscriptions_founder_number_uq
    ON subscriptions(founder_number) WHERE founder_number IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);

-- ── Datos de cobro del negocio (para el documento de cobro de la contadora) ─
CREATE TABLE IF NOT EXISTS billing_profiles (
    workspace_id  UUID PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
    legal_name    TEXT NOT NULL,
    tax_id        TEXT NOT NULL,
    billing_email TEXT NOT NULL,
    address       TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Citas adicionales (bloque mensual o recarga puntual) ────────────────────
-- Vale para los ciclos que cruza [valid_from, valid_until); valid_until NULL = hasta que se quite.
-- Un bloque se reinicia cada ciclo (las citas sin usar vencen); una recarga vence al cierre del ciclo.
CREATE TABLE IF NOT EXISTS subscription_addons (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    kind            TEXT NOT NULL CHECK (kind IN ('appointments_block','appointments_topup')),
    quantity        INTEGER NOT NULL CHECK (quantity > 0),
    price_cop       INTEGER NOT NULL CHECK (price_cop >= 0),
    valid_from      DATE NOT NULL,
    valid_until     DATE,
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_addons_subscription ON subscription_addons(subscription_id, valid_from);

-- ── Facturas de cobro manual ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS billing_invoices (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id      UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    subscription_id   UUID REFERENCES subscriptions(id) ON DELETE SET NULL,
    kind              TEXT NOT NULL DEFAULT 'cycle' CHECK (kind IN ('cycle','proration')),
    period_start      DATE NOT NULL,
    period_end        DATE NOT NULL,
    due_date          DATE NOT NULL,
    amount_cop        INTEGER NOT NULL CHECK (amount_cop >= 0),
    status            TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','paid','overdue','void')),
    paid_at           TIMESTAMPTZ,
    payment_method    TEXT,
    payment_reference TEXT,
    verified_by       UUID REFERENCES users(id),
    document_number   TEXT,
    notes             TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Un cobro de ciclo por negocio y periodo. El prorrateo de un cambio de plan es otra factura (kind='proration').
CREATE UNIQUE INDEX IF NOT EXISTS billing_invoices_period_uq
    ON billing_invoices(workspace_id, period_start) WHERE status <> 'void' AND kind = 'cycle';

CREATE INDEX IF NOT EXISTS idx_billing_invoices_status_due ON billing_invoices(status, due_date);

CREATE TABLE IF NOT EXISTS billing_invoice_lines (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id  UUID NOT NULL REFERENCES billing_invoices(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL CHECK (kind IN ('plan','appointments','professional','meta_messages','proration','adjustment')),
    description TEXT NOT NULL,
    quantity    INTEGER NOT NULL DEFAULT 1,
    amount_cop  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_invoice_lines_invoice ON billing_invoice_lines(invoice_id);

-- ── Eventos: línea de tiempo de cada negocio y base del embudo y la cobranza ─
CREATE TABLE IF NOT EXISTS billing_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES subscriptions(id) ON DELETE SET NULL,
    type            TEXT NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_billing_events_ws ON billing_events(workspace_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_billing_events_type ON billing_events(type, created_at DESC);

-- ── Consumo de IA por negocio y día (para medir el margen real) ─────────────
CREATE TABLE IF NOT EXISTS agent_usage (
    workspace_id  UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    day           DATE NOT NULL,
    calls         INTEGER NOT NULL DEFAULT 0,
    input_tokens  BIGINT NOT NULL DEFAULT 0,
    output_tokens BIGINT NOT NULL DEFAULT 0,
    cost_usd      NUMERIC(12,6) NOT NULL DEFAULT 0,
    PRIMARY KEY (workspace_id, day)
);

-- ── Una prueba y un descuento por número de WhatsApp (claim_key = solo dígitos del número) ──
CREATE TABLE IF NOT EXISTS offer_claims (
    claim_key           TEXT PRIMARY KEY,
    workspace_id        UUID REFERENCES workspaces(id) ON DELETE SET NULL,
    trial_claimed_at    TIMESTAMPTZ,
    discount_claimed_at TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Mensajes de plantilla de Meta: tarifa por categoría y tasa de cambio ────
CREATE TABLE IF NOT EXISTS meta_template_rates (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category   TEXT NOT NULL CHECK (category IN ('utility','marketing','authentication','service')),
    usd_price  NUMERIC(10,5) NOT NULL CHECK (usd_price >= 0),
    valid_from DATE NOT NULL,
    UNIQUE (category, valid_from)
);

CREATE TABLE IF NOT EXISTS fx_rates (
    day      DATE PRIMARY KEY,
    usd_cop  NUMERIC(12,2) NOT NULL CHECK (usd_cop > 0)
);

ALTER TABLE followup_sends ADD COLUMN IF NOT EXISTS meta_category TEXT;

-- ── Parámetros de la plataforma (editables sin desplegar) ───────────────────
CREATE TABLE IF NOT EXISTS platform_settings (
    key        TEXT PRIMARY KEY,
    value      INTEGER NOT NULL,
    note       TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO platform_settings (key, value, note) VALUES
    ('trial_days', 7, 'Días de prueba gratis'),
    ('launch_discount_pct', 58, 'Descuento de lanzamiento (%)'),
    ('launch_discount_cycles', 3, 'Ciclos con descuento de lanzamiento'),
    ('quota_warn_pct', 80, 'Aviso al llegar a este % de las citas'),
    ('quota_margin', 20, 'Citas de margen después de agotar el cupo'),
    ('grace_days', 5, 'Días sin pago antes de pausar el asistente'),
    ('retention_days', 30, 'Días que se conservan los datos tras pausar o cancelar'),
    ('upcoming_notice_days', 3, 'Días de aviso antes de cada cobro'),
    ('low_usage_pct', 40, 'Uso bajo (%) durante 2 ciclos para proponer bajar de plan'),
    ('founder_cap', 30, 'Cupo de fundadores')
ON CONFLICT (key) DO NOTHING;

-- ── Citas del asistente: created_by IS NULL (el panel siempre guarda a quien la creó) ─
-- No se agrega ninguna columna: así el INSERT de citas no depende de esta migración.
CREATE INDEX IF NOT EXISTS idx_appointments_agent_created ON appointments(workspace_id, created_at) WHERE created_by IS NULL
