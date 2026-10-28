"""
Modelos SQLAlchemy — espejo del schema PostgreSQL.
Solo para Alembic autogenerate. El runtime usa asyncpg raw.
"""
from sqlalchemy import (
    Boolean, Column, CheckConstraint, DateTime, ForeignKey,
    Index, Integer, Text, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase

NOW = text("NOW()")
UUID_V4 = text("uuid_generate_v4()")


class Base(DeclarativeBase):
    pass


# ── Users ─────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=UUID_V4)
    email = Column(Text, nullable=False, unique=True)
    name = Column(Text)
    phone = Column(Text)
    password_hash = Column(Text)
    role = Column(Text, nullable=False, server_default="workspace_owner")
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)
    last_login_at = Column(DateTime(timezone=True))
    metadata_ = Column("metadata", JSONB, server_default="{}")


# ── Workspaces ────────────────────────────────────────────────────────────────

class Workspace(Base):
    __tablename__ = "workspaces"
    __table_args__ = (
        Index("idx_workspaces_slug", "slug"),
    )

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=UUID_V4)
    name = Column(Text, nullable=False)
    legal_name = Column(Text)
    slug = Column(Text, nullable=False, unique=True)
    country = Column(Text, nullable=False, server_default="CO")
    timezone = Column(Text, nullable=False, server_default="America/Bogota")
    primary_phone = Column(Text)
    primary_email = Column(Text)
    brand_color = Column(Text)
    logo_url = Column(Text)
    business_type = Column(Text, comment="Tipo de negocio: barberia | salon | manicure | spa | otro")
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id"),
        Index("idx_workspace_members_ws_user", "workspace_id", "user_id"),
    )

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=UUID_V4)
    workspace_id = Column(UUID(as_uuid=False), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    member_role = Column(Text, nullable=False, server_default="staff")
    status = Column(Text, nullable=False, server_default="active")
    joined_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)


# ── Channels ──────────────────────────────────────────────────────────────────

class Channel(Base):
    __tablename__ = "channels"
    __table_args__ = (
        UniqueConstraint("workspace_id", "phone_number"),
        Index("idx_channels_ws_phone", "workspace_id", "phone_number"),
        Index("idx_channels_phone_number_id", "phone_number_id", postgresql_where=text("phone_number_id IS NOT NULL")),
    )

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=UUID_V4)
    workspace_id = Column(UUID(as_uuid=False), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    channel_type = Column(Text, nullable=False, server_default="whatsapp")
    provider = Column(Text, nullable=False)
    phone_number = Column(Text, nullable=False)
    display_name = Column(Text)
    status = Column(Text, nullable=False, server_default="active")
    coexistence_enabled = Column(Boolean, nullable=False, server_default="true")
    external_account_id = Column(Text)
    phone_number_id = Column(Text)
    webhook_secret_encrypted = Column(Text)
    metadata_ = Column("metadata", JSONB, server_default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)


# ── Calendars ─────────────────────────────────────────────────────────────────

class Calendar(Base):
    __tablename__ = "calendars"
    __table_args__ = (
        UniqueConstraint("workspace_id", "google_calendar_id"),
        Index("idx_calendars_ws_gcal", "workspace_id", "google_calendar_id"),
    )

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=UUID_V4)
    workspace_id = Column(UUID(as_uuid=False), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    google_calendar_id = Column(Text, nullable=False)
    connected_by_user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"))
    oauth_refresh_token_encrypted = Column(Text, nullable=False)
    sync_enabled = Column(Boolean, nullable=False, server_default="true")
    sync_status = Column(Text, nullable=False, server_default="active")
    last_synced_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)


# ── Services ──────────────────────────────────────────────────────────────────

class Service(Base):
    __tablename__ = "services"
    __table_args__ = (
        Index("idx_services_ws_active", "workspace_id", "is_active"),
    )

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=UUID_V4)
    workspace_id = Column(UUID(as_uuid=False), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text)
    duration_minutes = Column(Integer, nullable=False)
    buffer_minutes = Column(Integer, nullable=False, server_default="0")
    price_cop = Column(Integer, nullable=False)
    home_service_enabled = Column(Boolean, nullable=False, server_default="false")
    home_service_extra_minutes = Column(Integer, nullable=False, server_default="0")
    home_service_extra_price_cop = Column(Integer, nullable=False, server_default="0")
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)


# ── Customers ─────────────────────────────────────────────────────────────────

class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("workspace_id", "phone"),
        Index("idx_customers_ws_phone", "workspace_id", "phone"),
    )

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=UUID_V4)
    workspace_id = Column(UUID(as_uuid=False), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    phone = Column(Text, nullable=False)
    name = Column(Text)
    email = Column(Text)
    notes = Column(Text)
    last_seen_at = Column(DateTime(timezone=True))
    source_channel_id = Column(UUID(as_uuid=False), ForeignKey("channels.id"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)


# ── Appointments ──────────────────────────────────────────────────────────────

class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="appointments_check"),
        Index("idx_appointments_ws_start_status", "workspace_id", "start_at", "status"),
    )

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=UUID_V4)
    workspace_id = Column(UUID(as_uuid=False), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    customer_id = Column(UUID(as_uuid=False), ForeignKey("customers.id"), nullable=False)
    service_id = Column(UUID(as_uuid=False), ForeignKey("services.id"), nullable=False)
    channel_id = Column(UUID(as_uuid=False), ForeignKey("channels.id"), nullable=False)
    calendar_id = Column(UUID(as_uuid=False), ForeignKey("calendars.id"), nullable=False)
    start_at = Column(DateTime(timezone=True), nullable=False)
    end_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(Text, nullable=False, server_default="pending")
    price_cop = Column(Integer, nullable=False)
    home_service_price_cop = Column(Integer, nullable=False, server_default="0")
    is_home_service = Column(Boolean, nullable=False, server_default="false")
    home_address = Column(Text)
    google_event_id = Column(Text)
    cancellation_reason = Column(Text)
    cancelled_by = Column(UUID(as_uuid=False), ForeignKey("users.id"))
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"))
    confirmed_at = Column(DateTime(timezone=True))
    cancelled_at = Column(DateTime(timezone=True))
    reminder_24h_sent = Column(Boolean, nullable=False, server_default="false")
    reminder_1h_sent = Column(Boolean, nullable=False, server_default="false")
    reminder_sent = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)


# ── Availability Blocks ───────────────────────────────────────────────────────

class AvailabilityBlock(Base):
    __tablename__ = "availability_blocks"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="availability_blocks_check"),
        Index("idx_avail_blocks_ws_range", "workspace_id", "start_at", "end_at"),
    )

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=UUID_V4)
    workspace_id = Column(UUID(as_uuid=False), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    calendar_id = Column(UUID(as_uuid=False), ForeignKey("calendars.id"), nullable=False)
    start_at = Column(DateTime(timezone=True), nullable=False)
    end_at = Column(DateTime(timezone=True), nullable=False)
    block_type = Column(Text, nullable=False, server_default="manual")
    reason = Column(Text)
    source = Column(Text, nullable=False, server_default="manual")
    google_event_id = Column(Text)
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)


# ── Conversations ─────────────────────────────────────────────────────────────

class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("idx_conversations_ws_customer_status", "workspace_id", "customer_id", "status"),
    )

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=UUID_V4)
    workspace_id = Column(UUID(as_uuid=False), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    channel_id = Column(UUID(as_uuid=False), ForeignKey("channels.id"), nullable=False)
    customer_id = Column(UUID(as_uuid=False), ForeignKey("customers.id"))
    status = Column(Text, nullable=False, server_default="open")
    current_intent = Column(Text)
    last_message_at = Column(DateTime(timezone=True))
    last_agent_state = Column(Text)
    needs_review = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)


# ── Messages ──────────────────────────────────────────────────────────────────

class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("idx_messages_conv_sent", "conversation_id", "sent_at"),
    )

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=UUID_V4)
    workspace_id = Column(UUID(as_uuid=False), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    conversation_id = Column(UUID(as_uuid=False), ForeignKey("conversations.id"), nullable=False)
    channel_id = Column(UUID(as_uuid=False), ForeignKey("channels.id"), nullable=False)
    customer_id = Column(UUID(as_uuid=False), ForeignKey("customers.id"))
    direction = Column(Text, nullable=False)
    sender_type = Column(Text, nullable=False)
    message_type = Column(Text, nullable=False, server_default="text")
    content = Column(Text)
    media_url = Column(Text)
    provider_message_id = Column(Text)
    status = Column(Text, nullable=False, server_default="received")
    sent_at = Column(DateTime(timezone=True))
    received_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)


# ── Agent Runs ────────────────────────────────────────────────────────────────

class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("idx_agent_runs_ws_conv", "workspace_id", "conversation_id"),
    )

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=UUID_V4)
    workspace_id = Column(UUID(as_uuid=False), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    conversation_id = Column(UUID(as_uuid=False), ForeignKey("conversations.id"))
    status = Column(Text, nullable=False, server_default="running")
    input_summary = Column(Text)
    output_summary = Column(Text)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)
    ended_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)


# ── Tool Calls ────────────────────────────────────────────────────────────────

class ToolCall(Base):
    __tablename__ = "tool_calls"

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=UUID_V4)
    agent_run_id = Column(UUID(as_uuid=False), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False)
    tool_name = Column(Text, nullable=False)
    tool_input = Column(JSONB)
    tool_output = Column(JSONB)
    status = Column(Text, nullable=False, server_default="success")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)


# ── Agent Alerts ──────────────────────────────────────────────────────────────

class AgentAlert(Base):
    __tablename__ = "agent_alerts"

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=UUID_V4)
    workspace_id = Column(UUID(as_uuid=False), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    conversation_id = Column(UUID(as_uuid=False), ForeignKey("conversations.id"))
    severity = Column(Text, nullable=False, server_default="warning")
    reason = Column(Text)
    resolved = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)


# ── Billing Plans ─────────────────────────────────────────────────────────────

class BillingPlan(Base):
    __tablename__ = "billing_plans"

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=UUID_V4)
    name = Column(Text, nullable=False)
    description = Column(Text)
    price_cop = Column(Integer, nullable=False)
    billing_interval = Column(Text, nullable=False, server_default="monthly")
    max_channels = Column(Integer, nullable=False, server_default="1")
    max_calendars = Column(Integer, nullable=False, server_default="1")
    max_services = Column(Integer, nullable=False, server_default="10")
    max_messages = Column(Integer, nullable=False, server_default="1000")
    features = Column(JSONB, server_default="[]")
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)


# ── Subscriptions ─────────────────────────────────────────────────────────────

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=UUID_V4)
    workspace_id = Column(UUID(as_uuid=False), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    billing_plan_id = Column(UUID(as_uuid=False), ForeignKey("billing_plans.id"), nullable=False)
    status = Column(Text, nullable=False, server_default="active")
    payment_method = Column(Text)
    paid_this_month = Column(Boolean, nullable=False, server_default="false")
    current_period_start = Column(DateTime(timezone=True))
    current_period_end = Column(DateTime(timezone=True))
    next_billing_date = Column(DateTime(timezone=True))
    payment_verified_by = Column(UUID(as_uuid=False), ForeignKey("users.id"))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)


# ── Audit Logs ────────────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_logs_ws_action", "workspace_id", "action", "created_at"),
    )

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=UUID_V4)
    workspace_id = Column(UUID(as_uuid=False), ForeignKey("workspaces.id"))
    actor_user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"))
    action = Column(Text, nullable=False)
    entity_type = Column(Text, nullable=False)
    entity_id = Column(Text, nullable=False)
    before_data = Column(JSONB)
    after_data = Column(JSONB)
    ip_address = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=NOW)
