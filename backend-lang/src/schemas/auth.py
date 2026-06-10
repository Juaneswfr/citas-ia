"""Schemas de autenticación y sesión."""
from pydantic import BaseModel, Field, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Email del usuario")
    password: str = Field(..., min_length=8, description="Contraseña del usuario")


class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="Email del dueño del negocio")
    password: str = Field(..., min_length=8, description="Contraseña")
    workspace_name: str = Field(..., description="Nombre del negocio, ej: Barbería Juanes")
    workspace_slug: str = Field(..., description="Slug URL-friendly, ej: barberia-juanes")
    timezone: str = Field(default="America/Bogota", description="Zona horaria IANA")


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT de acceso")
    token_type: str = Field(default="bearer")
    expires_in: int = Field(..., description="Segundos hasta expiración")
    workspace_id: str = Field(default="", description="ID del workspace del usuario")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="Token de refresco")
