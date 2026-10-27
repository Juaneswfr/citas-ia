"""
Configuración central de la aplicación.
Carga variables de entorno y expone settings tipados.
"""
import os
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Base de datos ──────────────────────────────────────────────────────
    database_url: str = Field(..., alias="DATABASE_URL")

    # ── JWT ────────────────────────────────────────────────────────────────
    jwt_secret: str = Field(..., alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_access_expire_minutes: int = Field(default=60, alias="JWT_ACCESS_EXPIRE_MINUTES")

    # ── Google Calendar ────────────────────────────────────────────────────
    google_client_id: str = Field(default="", alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(default="", alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field(default="", alias="GOOGLE_REDIRECT_URI")
    google_encryption_key: str = Field(default="", alias="GOOGLE_ENCRYPTION_KEY")

    # ── WhatsApp ───────────────────────────────────────────────────────────
    whatsapp_verify_token: str = Field(default="", alias="WHATSAPP_VERIFY_TOKEN")
    whatsapp_app_secret: str = Field(default="", alias="WHATSAPP_APP_SECRET")
    whatsapp_api_token: str = Field(default="", alias="WHATSAPP_API_TOKEN")
    whatsapp_phone_number_id: str = Field(default="", alias="WHATSAPP_PHONE_NUMBER_ID")
    whatsapp_api_version: str = Field(default="v19.0", alias="WHATSAPP_API_VERSION")

    # ── Meta App (Embedded Signup) ─────────────────────────────────────────
    # El App ID se usa como client_id en el intercambio OAuth de Embedded Signup.
    # Se encuentra en: Meta Developer Portal → App → Settings → Basic → App ID
    meta_app_id: str = Field(default="", alias="META_APP_ID")

    # ── Agente ─────────────────────────────────────────────────────────────
    graph_timeout: int = Field(default=90, alias="GRAPH_TIMEOUT")

    # ── Redis / Workers ────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # ── Frontend URL (para redirects OAuth) ───────────────────────────────
    frontend_url: str = Field(default="https://hilo.esjuanez.com", alias="FRONTEND_URL")

    # ── Resend (emails transaccionales) ───────────────────────────────────
    resend_api_key: str = Field(default="", alias="RESEND_API_KEY")
    resend_from_email: str = Field(
        default="Hilo <noreply@hilo.esjuanez.com>", alias="RESEND_FROM_EMAIL"
    )

    # ── Sentry ─────────────────────────────────────────────────────────────
    sentry_dsn: str = Field(default="", alias="SENTRY_DSN")

    class Config:
        # .env.local sobreescribe .env — úsalo para overrides locales sin tocar producción
        env_file = [".env", ".env.local"]
        env_file_encoding = "utf-8"
        populate_by_name = True
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Singleton de settings; se cachea en el primer uso."""
    return Settings()
