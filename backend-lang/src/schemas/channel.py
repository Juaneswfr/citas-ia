"""Schemas para Canales de WhatsApp y Calendarios de Google."""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class ChannelCreate(BaseModel):
    channel_type: str = Field(default="whatsapp", description="Tipo de canal")
    provider: str = Field(..., description="Proveedor del canal, ej: 360dialog")
    phone_number: str = Field(..., description="Número E.164, ej: +573001234567")
    display_name: Optional[str] = Field(None, description="Nombre visible del canal")
    coexistence_enabled: bool = Field(default=True)
    external_account_id: Optional[str] = None


class EmbeddedSignupRequest(BaseModel):
    """
    Datos recibidos del flujo de Meta Embedded Signup.

    El frontend los obtiene así:
    - code            → response.authResponse.code (callback de FB.login)
    - phone_number_id → event.data del postMessage con type='WA_EMBEDDED_SIGNUP'
    - waba_id         → mismo postMessage, campo data.waba_id
    """
    code: str = Field(..., description="Código de autorización de FB.login()")
    phone_number_id: str = Field(..., description="ID del número en Meta WABA")
    waba_id: str = Field(..., description="WhatsApp Business Account ID")


class ChannelOut(BaseModel):
    id: str
    workspace_id: str
    channel_type: str
    provider: str
    phone_number: str
    display_name: Optional[str]
    status: str
    coexistence_enabled: bool
    external_account_id: Optional[str]
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class CalendarCreate(BaseModel):
    name: str = Field(..., description="Nombre descriptivo del calendario")
    google_calendar_id: str = Field(..., description="ID del calendario en Google")
    oauth_code: str = Field(..., description="Código OAuth de autorización de Google")


class CalendarOut(BaseModel):
    id: str
    workspace_id: str
    name: str
    google_calendar_id: str
    connected_by_user_id: str
    sync_enabled: bool
    sync_status: str
    last_synced_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
