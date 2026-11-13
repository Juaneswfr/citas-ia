"""Schemas del panel de administración de la plataforma (solo super_admin)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from core.business_types import validate_business_type


class CountByKey(BaseModel):
    """Conteo agrupado (por tipo de negocio, por estado de suscripción…)."""

    key: str
    count: int


class WeeklySignups(BaseModel):
    week_start: datetime
    count: int


class AdminOverviewOut(BaseModel):
    workspaces_total: int
    workspaces_active: int
    workspaces_new_30d: int
    users_total: int
    channels_active: int
    appointments_30d: int
    messages_30d: int
    by_business_type: list[CountByKey]
    by_subscription_status: list[CountByKey]
    signups_by_week: list[WeeklySignups]


class AdminWorkspaceRow(BaseModel):
    id: str
    name: str
    slug: str
    business_type: Optional[str] = None
    is_active: bool
    timezone: str
    created_at: datetime
    owner_email: Optional[str] = None
    plan_name: Optional[str] = None
    subscription_status: Optional[str] = None
    members: int
    channels_active: int
    appointments_30d: int
    last_message_at: Optional[datetime] = None


class AdminWorkspaceList(BaseModel):
    items: list[AdminWorkspaceRow]
    total: int


class AdminMemberOut(BaseModel):
    user_id: str
    name: Optional[str] = None
    email: str
    member_role: str
    status: str


class AdminChannelOut(BaseModel):
    id: str
    provider: str
    phone_number: str
    display_name: Optional[str] = None
    status: str


class AdminCalendarOut(BaseModel):
    id: str
    name: str
    sync_status: str


class AdminWorkspaceCounts(BaseModel):
    services: int
    customers: int
    appointments: int


class AdminWorkspaceDetail(BaseModel):
    workspace: AdminWorkspaceRow
    members: list[AdminMemberOut]
    channels: list[AdminChannelOut]
    calendars: list[AdminCalendarOut]
    counts: AdminWorkspaceCounts


class AdminWorkspaceUpdate(BaseModel):
    """Cambios que solo la plataforma puede hacer sobre un negocio."""

    is_active: Optional[bool] = Field(None, description="false suspende el negocio: no inicia sesión y el agente no responde")
    business_type: Optional[str] = Field(None, description="Tipo de negocio del catálogo")

    @field_validator("business_type")
    @classmethod
    def _check_business_type(cls, value: Optional[str]) -> Optional[str]:
        return validate_business_type(value)


class AdminUserRow(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None
    workspace_id: Optional[str] = None
    workspace_name: Optional[str] = None


class AdminUserList(BaseModel):
    items: list[AdminUserRow]
    total: int


class HealthCheckOut(BaseModel):
    """Resultado de probar un servicio externo. `status`: ok | warn | bad."""

    id: str
    label: str
    status: str
    detail: str
    latency_ms: Optional[int] = None
    action_url: Optional[str] = None


class HealthNumberOut(BaseModel):
    channel_id: str
    workspace_name: str
    phone_number: str
    status: str
    detail: str


class HealthErrorOut(BaseModel):
    id: str
    severity: str
    reason: Optional[str] = None
    created_at: datetime
    workspace_name: str


class HealthActivityOut(BaseModel):
    inbound_24h: int
    outbound_24h: int
    last_inbound_at: Optional[datetime] = None
    last_outbound_at: Optional[datetime] = None
    runs_ok_24h: int
    runs_error_24h: int
    unanswered_24h: int
    recent_errors: list[HealthErrorOut]


class AdminHealthOut(BaseModel):
    checks: list[HealthCheckOut]
    numbers: list[HealthNumberOut]
    activity: HealthActivityOut


class AdminUserUpdate(BaseModel):
    is_active: bool = Field(..., description="false bloquea el inicio de sesión del usuario")
