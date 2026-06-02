"""Schemas para Servicios del negocio."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ServiceCreate(BaseModel):
    name: str = Field(..., description="Nombre del servicio, ej: Corte clásico")
    description: Optional[str] = Field(None, description="Descripción visible al cliente")
    duration_minutes: int = Field(..., gt=0, description="Duración en minutos")
    buffer_minutes: int = Field(default=0, ge=0, description="Tiempo de preparación entre citas")
    price_cop: int = Field(..., gt=0, description="Precio en pesos colombianos")
    home_service_enabled: bool = Field(default=False, description="Permite servicio a domicilio")
    home_service_extra_minutes: int = Field(default=0, ge=0)
    home_service_extra_price_cop: int = Field(default=0, ge=0)


class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = Field(None, gt=0)
    buffer_minutes: Optional[int] = Field(None, ge=0)
    price_cop: Optional[int] = Field(None, gt=0)
    home_service_enabled: Optional[bool] = None
    home_service_extra_minutes: Optional[int] = Field(None, ge=0)
    home_service_extra_price_cop: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class ServiceOut(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: Optional[str]
    duration_minutes: int
    buffer_minutes: int
    price_cop: int
    home_service_enabled: bool
    home_service_extra_minutes: int
    home_service_extra_price_cop: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
