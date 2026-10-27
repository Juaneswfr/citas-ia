"""
Configuración central de la aplicación.
Carga variables de entorno y expone settings tipados.
"""
import os
from functools import lru_cache
from pydantic import Field, model_validator
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

    # ── Kapso (proveedor WhatsApp) ─────────────────────────────────────────
    kapso_enabled: bool = Field(default=False, alias="KAPSO_ENABLED")
    kapso_api_key: str = Field(default="", alias="KAPSO_API_KEY")
    # Secreto del webhook de PROYECTO (eventos como whatsapp.phone_number.created).
    kapso_webhook_secret_project: str = Field(default="", alias="KAPSO_WEBHOOK_SECRET_PROJECT")
    # Obsoleto: los mensajes se verifican con el secreto cifrado de cada canal (/webhooks/kapso/n/{token}).
    kapso_webhook_secret_number: str = Field(default="", alias="KAPSO_WEBHOOK_SECRET_NUMBER")
    # Obsoleto: ya no se usa para verificar firmas (la ruta de proyecto solo usa el secreto de proyecto).
    kapso_webhook_secret: str = Field(default="", alias="KAPSO_WEBHOOK_SECRET")
    kapso_base_url: str = Field(default="https://api.kapso.ai", alias="KAPSO_BASE_URL")
    # Clave Fernet (base64 urlsafe de 32 bytes) que cifra el secreto de webhook de cada canal.
    kapso_secrets_key: str = Field(default="", alias="KAPSO_SECRETS_KEY")

    @model_validator(mode="after")
    def _require_kapso_secrets(self):
        # Solo nombres de variables en el mensaje; nunca valores.
        if self.kapso_enabled and not (
            self.kapso_api_key and self.kapso_webhook_secret_project and self.kapso_secrets_key
        ):
            raise ValueError(
                "KAPSO_ENABLED=true requiere KAPSO_API_KEY, KAPSO_WEBHOOK_SECRET_PROJECT "
                "y KAPSO_SECRETS_KEY"
            )
        if self.kapso_enabled:
            from cryptography.fernet import Fernet
            try:
                Fernet(self.kapso_secrets_key.encode())
            except Exception:
                raise ValueError("KAPSO_SECRETS_KEY no es una clave Fernet válida")
        return self

    # ── Sentry ─────────────────────────────────────────────────────────────
    sentry_dsn: str = Field(default="", alias="SENTRY_DSN")

    class Config:
        # .env.local sobreescribe .env — úsalo para overrides locales sin tocar producción
        env_file = [".env", ".env.local"]
        env_file_encoding = "utf-8"
        populate_by_name = True
        hide_input_in_errors = True  # un ValidationError no debe imprimir secretos del entorno
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Singleton de settings; se cachea en el primer uso."""
    return Settings()
