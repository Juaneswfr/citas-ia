"""Schemas del seguimiento por WhatsApp (ajustes, plantillas y envíos)."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

FollowupKind = Literal["reminder", "post_visit", "payment_due", "reactivation"]
TemplateStatus = Literal["not_created", "pending", "approved", "rejected", "disabled", "error"]


class FollowupSettings(BaseModel):
    """Qué seguimientos tiene activos el negocio y con qué tiempos."""
    reminder_enabled: bool = True
    reminder_hours_before: int = Field(24, ge=1, le=72)
    post_visit_enabled: bool = False
    post_visit_hours_after: int = Field(2, ge=1, le=24)
    payment_due_enabled: bool = False
    payment_due_days: int = Field(1, ge=1, le=30)
    reactivation_enabled: bool = False
    reactivation_days: int = Field(30, ge=14, le=365)


class FollowupTemplateOut(BaseModel):
    kind: FollowupKind
    name: str
    category: str
    body: str
    buttons: list[str]
    status: TemplateStatus
    detail: Optional[str] = None
    synced_at: Optional[datetime] = None


class FollowupTemplatesOut(BaseModel):
    """Estado de las plantillas en la cuenta de WhatsApp del negocio."""
    connected: bool  # hay un número de WhatsApp activo; sin él no se envía ningún seguimiento
    can_activate: bool
    reason: Optional[str] = None  # por qué no se pueden activar (sin canal, número de pruebas...)
    templates: list[FollowupTemplateOut]


class FollowupSendOut(BaseModel):
    id: str
    kind: FollowupKind
    customer_name: Optional[str] = None
    status: Literal["sending", "sent", "failed"]
    via: Optional[Literal["template", "text"]] = None
    error: Optional[str] = None
    created_at: datetime
