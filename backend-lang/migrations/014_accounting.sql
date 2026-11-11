-- 014: Módulo contable simple (terceros, órdenes de venta/compra, movimientos, comisiones).
-- Modelo de caja: la fuente de verdad de ingresos/gastos es `movements`.
-- Cuentas por cobrar/pagar NO se guardan: saldo = total de la orden - movimientos no anulados.
-- Dinero en pesos COP (INTEGER), igual que services.price_cop.

-- ── Terceros (clientes, proveedores, empleados) ───────────────────────────────
CREATE TABLE IF NOT EXISTS third_parties (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    kind         TEXT NOT NULL DEFAULT 'customer'
                 CHECK (kind IN ('customer','supplier','employee','other')),
    name         TEXT NOT NULL,
    document_id  TEXT,
    phone        TEXT,
    email        TEXT,
    customer_id  UUID REFERENCES customers(id) ON DELETE SET NULL,
    member_id    UUID REFERENCES workspace_members(id) ON DELETE SET NULL,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_third_parties_ws_customer
    ON third_parties(workspace_id, customer_id) WHERE customer_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_third_parties_ws_member
    ON third_parties(workspace_id, member_id) WHERE member_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_third_parties_ws_kind
    ON third_parties(workspace_id, kind);

-- ── Categorías de ingreso/gasto ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS finance_categories (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    kind         TEXT NOT NULL CHECK (kind IN ('income','expense')),
    name         TEXT NOT NULL,
    is_system    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (workspace_id, kind, name)
);

-- ── Compensación por miembro (regla de pago del barbero) ──────────────────────
CREATE TABLE IF NOT EXISTS member_compensation (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id     UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    member_id        UUID NOT NULL REFERENCES workspace_members(id) ON DELETE CASCADE,
    model            TEXT NOT NULL DEFAULT 'commission'
                     CHECK (model IN ('commission','booth_rent','salary','hybrid')),
    commission_bps   INTEGER NOT NULL DEFAULT 0 CHECK (commission_bps BETWEEN 0 AND 10000),
    base_salary_cop  INTEGER NOT NULL DEFAULT 0 CHECK (base_salary_cop >= 0),
    rent_cop         INTEGER NOT NULL DEFAULT 0 CHECK (rent_cop >= 0),
    fixed_period     TEXT NOT NULL DEFAULT 'month' CHECK (fixed_period IN ('week','month')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (workspace_id, member_id)
);

-- ── Liquidaciones de comisión ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS commission_payouts (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id       UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    member_id          UUID NOT NULL REFERENCES workspace_members(id) ON DELETE CASCADE,
    period_start       DATE NOT NULL,
    period_end         DATE NOT NULL,
    commission_cop     INTEGER NOT NULL DEFAULT 0,
    base_cop           INTEGER NOT NULL DEFAULT 0,
    rent_deduction_cop INTEGER NOT NULL DEFAULT 0,
    tips_cop           INTEGER NOT NULL DEFAULT 0,
    net_cop            INTEGER NOT NULL DEFAULT 0,
    status             TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','paid','cancelled')),
    paid_at            TIMESTAMPTZ,
    created_by         UUID REFERENCES users(id),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (period_end >= period_start)
);

CREATE INDEX IF NOT EXISTS idx_payouts_ws_member
    ON commission_payouts(workspace_id, member_id, period_start);

-- ── Órdenes de venta ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sales_orders (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id   UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    number         INTEGER NOT NULL,
    third_party_id UUID REFERENCES third_parties(id) ON DELETE SET NULL,
    appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,
    status         TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','paid','void')),
    issued_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    total_cop      INTEGER NOT NULL DEFAULT 0 CHECK (total_cop >= 0),
    notes          TEXT,
    created_by     UUID REFERENCES users(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (workspace_id, number)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_sales_orders_appointment
    ON sales_orders(appointment_id) WHERE appointment_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_sales_orders_ws_issued
    ON sales_orders(workspace_id, issued_at DESC);

CREATE TABLE IF NOT EXISTS sales_order_lines (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id     UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    order_id         UUID NOT NULL REFERENCES sales_orders(id) ON DELETE CASCADE,
    service_id       UUID REFERENCES services(id) ON DELETE SET NULL,
    description      TEXT NOT NULL,
    qty              INTEGER NOT NULL DEFAULT 1 CHECK (qty > 0),
    unit_price_cop   INTEGER NOT NULL CHECK (unit_price_cop >= 0),
    line_total_cop   INTEGER NOT NULL CHECK (line_total_cop >= 0),
    member_id        UUID REFERENCES workspace_members(id) ON DELETE SET NULL,
    commission_bps   INTEGER NOT NULL DEFAULT 0,
    commission_cop   INTEGER NOT NULL DEFAULT 0,
    tip_cop          INTEGER NOT NULL DEFAULT 0 CHECK (tip_cop >= 0),
    payout_id        UUID REFERENCES commission_payouts(id) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sales_lines_order
    ON sales_order_lines(order_id);

CREATE INDEX IF NOT EXISTS idx_sales_lines_ws_member
    ON sales_order_lines(workspace_id, member_id) WHERE payout_id IS NULL;

-- ── Órdenes de compra (a proveedores) ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS purchase_orders (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id   UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    number         INTEGER NOT NULL,
    third_party_id UUID REFERENCES third_parties(id) ON DELETE SET NULL,
    category_id    UUID REFERENCES finance_categories(id) ON DELETE SET NULL,
    description    TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','paid','void')),
    issued_on      DATE NOT NULL DEFAULT CURRENT_DATE,
    due_on         DATE,
    total_cop      INTEGER NOT NULL CHECK (total_cop > 0),
    created_by     UUID REFERENCES users(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (workspace_id, number)
);

CREATE INDEX IF NOT EXISTS idx_purchase_orders_ws_status
    ON purchase_orders(workspace_id, status, due_on);

-- ── Movimientos (libro de caja) ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS movements (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id      UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    kind              TEXT NOT NULL CHECK (kind IN ('income','expense')),
    amount_cop        INTEGER NOT NULL CHECK (amount_cop > 0),
    occurred_on       DATE NOT NULL DEFAULT CURRENT_DATE,
    method            TEXT NOT NULL DEFAULT 'cash'
                      CHECK (method IN ('cash','transfer','card','nequi','other')),
    category_id       UUID REFERENCES finance_categories(id) ON DELETE SET NULL,
    third_party_id    UUID REFERENCES third_parties(id) ON DELETE SET NULL,
    sales_order_id    UUID REFERENCES sales_orders(id) ON DELETE SET NULL,
    purchase_order_id UUID REFERENCES purchase_orders(id) ON DELETE SET NULL,
    payout_id         UUID REFERENCES commission_payouts(id) ON DELETE SET NULL,
    description       TEXT,
    created_by        UUID REFERENCES users(id),
    voided_at         TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_movements_ws_date
    ON movements(workspace_id, occurred_on DESC) WHERE voided_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_movements_sales_order
    ON movements(sales_order_id) WHERE sales_order_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_movements_purchase_order
    ON movements(purchase_order_id) WHERE purchase_order_id IS NOT NULL;

-- Sin RLS: el aislamiento entre workspaces depende de JWT + require_workspace_access
-- (decisión vigente, ver CLAUDE.md).

-- ── Categorías base para workspaces existentes ────────────────────────────────
INSERT INTO finance_categories (workspace_id, kind, name, is_system)
SELECT w.id, c.kind, c.name, TRUE
FROM workspaces w
CROSS JOIN (VALUES
    ('income',  'Servicios'),
    ('income',  'Productos'),
    ('income',  'Arriendo de silla'),
    ('income',  'Otros ingresos'),
    ('expense', 'Arriendo del local'),
    ('expense', 'Insumos'),
    ('expense', 'Servicios públicos'),
    ('expense', 'Nómina y comisiones'),
    ('expense', 'Otros gastos')
) AS c(kind, name)
ON CONFLICT (workspace_id, kind, name) DO NOTHING;
