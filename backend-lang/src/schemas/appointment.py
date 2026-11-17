"""Schemas para Citas (appointments) y Bloques de disponibilidad."""
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class AppointmentCreate(BaseModel):
    customer_id: str = Field(..., description="ID del cliente")
    service_id: str = Field(..., description="ID del servicio")
    channel_id: Optional[str] = Field(None, description="Canal de WhatsApp (opcional — si None el backend busca el activo)")
    calendar_id: Optional[str] = Field(None, description="Calendario destino (opcional — si None no sincroniza con Google Calendar)")
    start_at: datetime = Field(..., description="Inicio de la cita (ISO 8601 con timezone)")
    is_home_service: bool = Field(default=False)
    home_address: Optional[str] = Field(None, description="Dirección si es domicilio")
    price_cop: int = Field(..., gt=0, description="Precio pactado en COP")
    home_service_price_cop: int = Field(default=0, ge=0)


class AppointmentUpdate(BaseModel):
    """Solo el dueño/manager puede actualizar. Sujeto a confirmación explícita (Principio IX)."""
    start_at: Optional[datetime] = None
    status: Optional[Literal["pending", "confirmed", "cancelled", "completed", "noshow", "rescheduled"]] = Field(
        None, description="pending|confirmed|cancelled|completed|noshow|rescheduled"
    )
    cancellation_reason: Optional[str] = None
    cancelled_by: Optional[str] = None


class AppointmentOut(BaseModel):
    id: str
    workspace_id: str
    customer_id: str
    service_id: str
    channel_id: Optional[str]
    calendar_id: Optional[str]
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


class AppointmentCancel(BaseModel):
    """Cancelación desde el panel por cualquier miembro del equipo."""
    reason: Optional[str] = Field(None, max_length=255, description="Motivo interno de la cancelación")


class AppointmentCancelOut(AppointmentOut):
    """La cita cancelada y si el cliente quedó avisado por WhatsApp."""
    customer_notified: bool
    notify_detail: Optional[str] = None  # por qué no se pudo avisar


class AvailabilityBlockCreate(BaseModel):
    """
    Bloqueo de agenda. Requiere confirmación explícita del dueño (Principio IX).
    """
    calendar_id: str
    start_at: datetime = Field(..., description="Inicio del bloqueo")
    end_at: datetime = Field(..., description="Fin del bloqueo")
    block_type: str = Field(
        "manual", description="manual|system|travel|external"
    )
    reason: Optional[str] = Field(None, max_length=500, description="Motivo del bloqueo")

    @model_validator(mode="after")
    def _end_after_start(self):
        if self.end_at <= self.start_at:
            raise ValueError("El fin del bloqueo debe ser posterior al inicio.")
        return self


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


class AvailabilityBlockCreated(AvailabilityBlockOut):
    """El bloqueo creado y cuántas citas ya agendadas caen dentro (no se cancelan solas)."""
    appointments_in_range: int = 0
