"""Schemas Pydantic para Workspace y WorkspaceMember."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr


class WorkspaceCreate(BaseModel):
    name: str = Field(..., description="Nombre comercial del negocio")
    legal_name: Optional[str] = Field(None, description="Razón social o nombre legal")
    slug: str = Field(..., description="Identificador único URL-friendly")
    country: str = Field(default="CO", description="Código ISO del país")
    timezone: str = Field(..., description="Zona horaria IANA, ej: America/Bogota")
    primary_phone: Optional[str] = Field(None, description="Teléfono principal de contacto")
    primary_email: Optional[EmailStr] = Field(None, description="Email principal de contacto")
    brand_color: Optional[str] = Field(None, description="Color hex del branding, ej: #1A1A1A")
    logo_url: Optional[str] = Field(None, description="URL del logo del negocio")


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Nombre comercial del negocio")
    legal_name: Optional[str] = None
    timezone: Optional[str] = None
    primary_phone: Optional[str] = None
    primary_email: Optional[EmailStr] = None
    brand_color: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: Optional[bool] = None


class WorkspaceOut(BaseModel):
    id: str
    name: str
    slug: str
    country: str
    timezone: str
    primary_phone: Optional[str]
    primary_email: Optional[str]
    brand_color: Optional[str]
    logo_url: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MemberInvite(BaseModel):
    email: EmailStr = Field(..., description="Email del usuario a invitar")
    member_role: str = Field(
        ..., description="Rol en el workspace: owner | manager | staff | viewer"
    )


class MemberOut(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    member_role: str
    status: str
    joined_at: Optional[datetime]
    created_at: datetime
