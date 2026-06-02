"""Schemas para Citas (appointments) y Bloques de disponibilidad."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class AppointmentCreate(BaseModel):
    customer_id: str = Field(..., description="ID del cliente")
    service_id: str = Field(..., description="ID del servicio")
    channel_id: str = Field(..., description="Canal de WhatsApp de origen")
    calendar_id: str = Field(..., description="Calendario destino")
    start_at: datetime = Field(..., description="Inicio de la cita (ISO 8601 con timezone)")
    is_home_service: bool = Field(default=False)
    home_address: Optional[str] = Field(None, description="Dirección si es domicilio")
    price_cop: int = Field(..., gt=0, description="Precio pactado en COP")
    home_service_price_cop: int = Field(default=0, ge=0)


class AppointmentUpdate(BaseModel):
    """Solo el dueño/manager puede actualizar. Sujeto a confirmación explícita (Principio IX)."""
    start_at: Optional[datetime] = None
    status: Optional[str] = Field(
        None, description="pending|confirmed|cancelled|completed|noshow|rescheduled"
    )
    cancellation_reason: Optional[str] = None
    cancelled_by: Optional[str] = None


class AppointmentOut(BaseModel):
    id: str
    workspace_id: str
    customer_id: str
    service_id: str
    channel_id: str
    calendar_id: str
    start_at: datetime
    end_at: datetime
    status: str
    price_cop: int
    home_service_price_cop: int
    is_home_service: bool
    home_address: Optional[str]
    google_event_id: Optional[str]
    cancellation_reason: Optional[str]
    cancelled_by: Optional[str]
    created_by: Optional[str]
    confirmed_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class AvailabilityBlockCreate(BaseModel):
    """
    Bloqueo de agenda. Requiere confirmación explícita del dueño (Principio IX).
    """
    calendar_id: str
    start_at: datetime = Field(..., description="Inicio del bloqueo")
    end_at: datetime = Field(..., description="Fin del bloqueo")
    block_type: str = Field(
        ..., description="manual|system|travel|external"
    )
    reason: Optional[str] = Field(None, description="Motivo del bloqueo")


class AvailabilityBlockOut(BaseModel):
    id: str
    workspace_id: str
    calendar_id: str
    start_at: datetime
    end_at: datetime
    block_type: str
    reason: Optional[str]
    source: str
    google_event_id: Optional[str]
    created_by: Optional[str]
    created_at: datetime
