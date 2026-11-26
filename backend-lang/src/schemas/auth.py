"""Schemas de autenticación y sesión."""
from pydantic import BaseModel, Field, EmailStr, field_validator


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Email del usuario")
    password: str = Field(..., min_length=8, description="Contraseña del usuario")


class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="Email del dueño del negocio")
    password: str = Field(..., min_length=8, description="Contraseña")
    workspace_name: str = Field(..., description="Nombre del negocio, ej: Barbería Juanes")
    workspace_slug: str = Field(..., description="Slug URL-friendly, ej: barberia-juanes")
    timezone: str = Field(default="America/Bogota", description="Zona horaria IANA")


class ProfileUpdate(BaseModel):
    """Datos que la propia persona puede cambiar de su cuenta."""
    name: str = Field(..., min_length=1, max_length=120, description="Nombre de la persona")

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El nombre no puede estar vacío.")
        return v


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT de acceso")
    token_type: str = Field(default="bearer")
    expires_in: int = Field(..., description="Segundos hasta expiración")
    workspace_id: str = Field(default="", description="ID del workspace del usuario")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="Token de refresco")


class GoogleTicketRequest(BaseModel):
    ticket: str = Field(..., description="Ticket de un solo uso que entrega el callback de Google")


class OAuthLinkRequest(BaseModel):
    ticket: str = Field(..., description="Ticket de vinculación que dejó el callback de Google o Facebook")
    password: str = Field(..., min_length=1, max_length=200, description="Contraseña de la cuenta existente")


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(..., description="Correo de la cuenta")


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., description="Token del enlace que llegó por correo")
    password: str = Field(..., min_length=8, max_length=200, description="Contraseña nueva")


class GoogleTicketResponse(TokenResponse):
    is_new: bool = Field(default=False, description="True si la cuenta se acaba de crear con Google")
