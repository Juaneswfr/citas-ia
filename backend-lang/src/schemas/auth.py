"""Schemas de autenticación y sesión."""
from pydantic import BaseModel, Field, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Email del usuario")
    password: str = Field(..., min_length=8, description="Contraseña del usuario")


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT de acceso")
    token_type: str = Field(default="bearer")
    expires_in: int = Field(..., description="Segundos hasta expiración")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="Token de refresco")
