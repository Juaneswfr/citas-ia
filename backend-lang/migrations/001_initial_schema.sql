-- ============================================================
-- CitasIA — Schema inicial de base de datos
-- Versión: 001 | Fecha: 2026-06-01
--
-- Principio IV (Constitución): Multi-tenant con aislamiento total.
-- Principio VII: Estructura segura de datos con constraints explícitos.
-- Principio XI: RLS activado en todas las tablas de negocio.
-- ============================================================

-- ── Extensiones ───────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── TABLA: users ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.users (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email         TEXT NOT NULL UNIQUE,
    name          TEXT,
    phone         TEXT,
    role          TEXT NOT NULL DEFAULT 'workspace_owner'
                  CHECK (role IN ('super_admin','workspace_owner','manager','staff','system_agent')),
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,
    metadata      JSONB DEFAULT '{}'
);

-- ── TABLA: workspaces ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.workspaces (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name          TEXT NOT NULL,
    legal_name    TEXT,
    slug          TEXT NOT NULL UNIQUE,
    country       TEXT NOT NULL DEFAULT 'CO',
    timezone      TEXT NOT NULL DEFAULT 'America/Bogota',
    primary_phone TEXT,
    primary_email TEXT,
    brand_color   TEXT,
    logo_url      TEXT,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── TABLA: workspace_members ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.workspace_members (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    user_id      UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    member_role  TEXT NOT NULL DEFAULT 'staff'
                 CHECK (member_role IN ('owner','manager','staff','viewer')),
    status       TEXT NOT NULL DEFAULT 'active'
                 CHECK (status IN ('active','inactive','pending')),
    joined_at    TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (workspace_id, user_id)
);

-- ── TABLA: channels ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.channels (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id         UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_type         TEXT NOT NULL DEFAULT 'whatsapp',
    provider             TEXT NOT NULL,
    phone_number         TEXT NOT NULL,
    display_name         TEXT,
    status               TEXT NOT NULL DEFAULT 'active'
                         CHECK (status IN ('active','paused','error','disconnected')),
    coexistence_enabled  BOOLEAN NOT NULL DEFAULT TRUE,
    external_account_id  TEXT,
    metadata             JSONB DEFAULT '{}',
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (workspace_id, phone_number)
);

-- ── TABLA: calendars ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.calendars (
    id                            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id                  UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    name                          TEXT NOT NULL,
    google_calendar_id            TEXT NOT NULL,
    connected_by_user_id          UUID REFERENCES public.users(id),
    -- Principio VII: token cifrado en la capa de servicio antes de persistir
    oauth_refresh_token_encrypted TEXT NOT NULL,
    sync_enabled                  BOOLEAN NOT NULL DEFAULT TRUE,
    sync_status                   TEXT NOT NULL DEFAULT 'active'
                                  CHECK (sync_status IN ('active','paused','error','disconnected')),
    last_synced_at                TIMESTAMPTZ,
    created_at                    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (workspace_id, google_calendar_id)
);

-- ── TABLA: services ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.services (
    id                         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id               UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    name                       TEXT NOT NULL,
    description                TEXT,
    duration_minutes           INTEGER NOT NULL CHECK (duration_minutes > 0),
    buffer_minutes             INTEGER NOT NULL DEFAULT 0 CHECK (buffer_minutes >= 0),
    price_cop                  INTEGER NOT NULL CHECK (price_cop > 0),
    home_service_enabled       BOOLEAN NOT NULL DEFAULT FALSE,
    home_service_extra_minutes INTEGER NOT NULL DEFAULT 0,
    home_service_extra_price_cop INTEGER NOT NULL DEFAULT 0,
    is_active                  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── TABLA: customers ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.customers (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id      UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    phone             TEXT NOT NULL,
    name              TEXT,
    email             TEXT,
    notes             TEXT,
    last_seen_at      TIMESTAMPTZ,
    source_channel_id UUID REFERENCES public.channels(id),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (workspace_id, phone)
);

-- ── TABLA: appointments ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.appointments (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id          UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    customer_id           UUID NOT NULL REFERENCES public.customers(id),
    service_id            UUID NOT NULL REFERENCES public.services(id),
    channel_id            UUID NOT NULL REFERENCES public.channels(id),
    calendar_id           UUID NOT NULL REFERENCES public.calendars(id),
    start_at              TIMESTAMPTZ NOT NULL,
    end_at                TIMESTAMPTZ NOT NULL,
    status                TEXT NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending','confirmed','cancelled','completed','noshow','rescheduled')),
    price_cop             INTEGER NOT NULL CHECK (price_cop >= 0),
    home_service_price_cop INTEGER NOT NULL DEFAULT 0,
    is_home_service       BOOLEAN NOT NULL DEFAULT FALSE,
    home_address          TEXT,
    google_event_id       TEXT,           -- Principio VI: referencia al evento de Calendar
    cancellation_reason   TEXT,
    cancelled_by          UUID REFERENCES public.users(id),
    created_by            UUID REFERENCES public.users(id),
    confirmed_at          TIMESTAMPTZ,
    cancelled_at          TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (end_at > start_at)
);

-- ── TABLA: availability_blocks ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.availability_blocks (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id  UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    calendar_id   UUID NOT NULL REFERENCES public.calendars(id),
    start_at      TIMESTAMPTZ NOT NULL,
    end_at        TIMESTAMPTZ NOT NULL,
    block_type    TEXT NOT NULL DEFAULT 'manual'
                  CHECK (block_type IN ('manual','system','travel','external')),
    reason        TEXT,
    source        TEXT NOT NULL DEFAULT 'manual',
    google_event_id TEXT,
    created_by    UUID REFERENCES public.users(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (end_at > start_at)
);

-- ── TABLA: conversations ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.conversations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id    UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id      UUID NOT NULL REFERENCES public.channels(id),
    customer_id     UUID REFERENCES public.customers(id),
    status          TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open','active','waiting_user','closed')),
    current_intent  TEXT,
    last_message_at TIMESTAMPTZ,
    last_agent_state TEXT,
    needs_review    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── TABLA: messages ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.messages (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id         UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    conversation_id      UUID NOT NULL REFERENCES public.conversations(id),
    channel_id           UUID NOT NULL REFERENCES public.channels(id),
    customer_id          UUID REFERENCES public.customers(id),
    direction            TEXT NOT NULL CHECK (direction IN ('inbound','outbound')),
    sender_type          TEXT NOT NULL CHECK (sender_type IN ('customer','agent','system')),
    message_type         TEXT NOT NULL DEFAULT 'text',
    content              TEXT,
    media_url            TEXT,
    provider_message_id  TEXT,
    status               TEXT NOT NULL DEFAULT 'received',
    sent_at              TIMESTAMPTZ,
    received_at          TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── TABLA: agent_runs ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.agent_runs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id    UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES public.conversations(id),
    status          TEXT NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running','completed','error','cancelled')),
    input_summary   TEXT,
    output_summary  TEXT,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at        TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── TABLA: tool_calls ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.tool_calls (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_run_id UUID NOT NULL REFERENCES public.agent_runs(id) ON DELETE CASCADE,
    tool_name    TEXT NOT NULL,
    tool_input   JSONB,
    tool_output  JSONB,
    status       TEXT NOT NULL DEFAULT 'success'
                 CHECK (status IN ('success','error')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── TABLA: agent_alerts ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.agent_alerts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id    UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES public.conversations(id),
    severity        TEXT NOT NULL DEFAULT 'warning'
                    CHECK (severity IN ('info','warning','error','critical')),
    reason          TEXT,
    resolved        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── TABLA: billing_plans ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.billing_plans (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name             TEXT NOT NULL,
    description      TEXT,
    price_cop        INTEGER NOT NULL CHECK (price_cop >= 0),
    billing_interval TEXT NOT NULL DEFAULT 'monthly'
                     CHECK (billing_interval IN ('monthly','annual','one_time')),
    max_channels     INTEGER NOT NULL DEFAULT 1,
    max_calendars    INTEGER NOT NULL DEFAULT 1,
    max_services     INTEGER NOT NULL DEFAULT 10,
    max_messages     INTEGER NOT NULL DEFAULT 1000,
    features         JSONB DEFAULT '[]',
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── TABLA: subscriptions ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.subscriptions (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id         UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    billing_plan_id      UUID NOT NULL REFERENCES public.billing_plans(id),
    status               TEXT NOT NULL DEFAULT 'active'
                         CHECK (status IN ('active','pending_payment','suspended','cancelled','expired')),
    payment_method       TEXT,
    paid_this_month      BOOLEAN NOT NULL DEFAULT FALSE,
    current_period_start TIMESTAMPTZ,
    current_period_end   TIMESTAMPTZ,
    next_billing_date    TIMESTAMPTZ,
    payment_verified_by  UUID REFERENCES public.users(id),
    notes                TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── TABLA: audit_logs ─────────────────────────────────────────────────────────
-- Principio V: Registro inmutable de acciones críticas. Sin UPDATE/DELETE.
CREATE TABLE IF NOT EXISTS public.audit_logs (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id  UUID REFERENCES public.workspaces(id),
    actor_user_id UUID REFERENCES public.users(id),
    action        TEXT NOT NULL,
    entity_type   TEXT NOT NULL,
    entity_id     TEXT NOT NULL,
    before_data   JSONB,
    after_data    JSONB,
    ip_address    TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- ÍNDICES OBLIGATORIOS (Principio IV: RLS + consultas eficientes)
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_workspaces_slug ON public.workspaces(slug);
CREATE INDEX IF NOT EXISTS idx_workspace_members_ws_user ON public.workspace_members(workspace_id, user_id);
CREATE INDEX IF NOT EXISTS idx_channels_ws_phone ON public.channels(workspace_id, phone_number);
CREATE INDEX IF NOT EXISTS idx_calendars_ws_gcal ON public.calendars(workspace_id, google_calendar_id);
CREATE INDEX IF NOT EXISTS idx_services_ws_active ON public.services(workspace_id, is_active);
CREATE INDEX IF NOT EXISTS idx_customers_ws_phone ON public.customers(workspace_id, phone);
CREATE INDEX IF NOT EXISTS idx_appointments_ws_start_status ON public.appointments(workspace_id, start_at, status);
CREATE INDEX IF NOT EXISTS idx_avail_blocks_ws_range ON public.availability_blocks(workspace_id, start_at, end_at);
CREATE INDEX IF NOT EXISTS idx_conversations_ws_customer_status ON public.conversations(workspace_id, customer_id, status);
CREATE INDEX IF NOT EXISTS idx_messages_conv_sent ON public.messages(conversation_id, sent_at);
CREATE INDEX IF NOT EXISTS idx_agent_runs_ws_conv ON public.agent_runs(workspace_id, conversation_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_ws_action ON public.audit_logs(workspace_id, action, created_at);

-- ============================================================
-- ROW LEVEL SECURITY (Principio IV + Principio XI)
-- ============================================================

-- Activar RLS en todas las tablas de negocio
ALTER TABLE public.workspaces          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workspace_members   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.channels            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.calendars           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.services            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.customers           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.appointments        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.availability_blocks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversations       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_runs          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tool_calls          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_alerts        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subscriptions       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs          ENABLE ROW LEVEL SECURITY;

-- ── Políticas RLS: workspace_members ─────────────────────────────────────────
-- Un usuario solo ve membresías de workspaces a los que pertenece
CREATE POLICY wm_select ON public.workspace_members
    FOR SELECT USING (
        workspace_id IN (
            SELECT workspace_id FROM public.workspace_members
            WHERE user_id = auth.uid()
        )
    );

-- ── Política base reutilizable: verificar pertenencia al workspace ─────────────
-- Para cada tabla de negocio: SELECT permitido si el usuario pertenece al workspace
CREATE POLICY channels_select ON public.channels
    FOR SELECT USING (
        workspace_id IN (
            SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
        )
    );

CREATE POLICY calendars_select ON public.calendars
    FOR SELECT USING (
        workspace_id IN (
            SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
        )
    );

CREATE POLICY services_select ON public.services
    FOR SELECT USING (
        workspace_id IN (
            SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
        )
    );

CREATE POLICY customers_select ON public.customers
    FOR SELECT USING (
        workspace_id IN (
            SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
        )
    );

CREATE POLICY appointments_select ON public.appointments
    FOR SELECT USING (
        workspace_id IN (
            SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
        )
    );

CREATE POLICY conversations_select ON public.conversations
    FOR SELECT USING (
        workspace_id IN (
            SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
        )
    );

CREATE POLICY messages_select ON public.messages
    FOR SELECT USING (
        workspace_id IN (
            SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
        )
    );

CREATE POLICY agent_alerts_select ON public.agent_alerts
    FOR SELECT USING (
        workspace_id IN (
            SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
        )
    );

CREATE POLICY subscriptions_select ON public.subscriptions
    FOR SELECT USING (
        workspace_id IN (
            SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
        )
    );

CREATE POLICY audit_logs_select ON public.audit_logs
    FOR SELECT USING (
        workspace_id IN (
            SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
        )
    );

-- Nota: Las operaciones INSERT/UPDATE/DELETE sobre tablas de negocio
-- se realizan desde el backend con service_role (que bypasa RLS).
-- El backend verifica permisos de rol antes de cada operación (Principio XI).
-- audit_logs nunca tiene UPDATE/DELETE por diseño (registro inmutable).
