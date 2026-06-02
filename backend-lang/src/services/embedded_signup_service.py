"""
EmbeddedSignupService — Flujo de Meta Embedded Signup para WhatsApp Business.

Permite a los dueños de negocio conectar su propio número de WhatsApp
directamente desde el dashboard de CitasIA, incluyendo verificación OTP
manejada por el popup de Meta (no por CitasIA).

Flujo completo:
  1. Frontend carga el SDK de Facebook y lanza FB.login()
  2. El popup de Meta guía al usuario: login Facebook → seleccionar WABA
     → agregar número de teléfono → recibir y verificar OTP
  3. Meta devuelve: code (en FB.login callback) + phone_number_id + waba_id
     (via window.postMessage con tipo WA_EMBEDDED_SIGNUP)
  4. Frontend envía los tres valores a POST /embedded-signup
  5. Este servicio intercambia code → access_token (Graph API)
  6. Obtiene info pública del número (display_phone_number, verified_name)
  7. Suscribe el WABA al app de CitasIA (para recibir webhooks futuros)
  8. El access_token se cifra con Fernet antes de persistir

Principio VII (Constitución): El access_token del WABA se almacena cifrado;
nunca se retorna en responses.
"""
import logging
from typing import Optional

import httpx

from core.config import get_settings

log = logging.getLogger(__name__)


class EmbeddedSignupService:
    """Integración con Meta Embedded Signup para conectar WABAs de clientes."""

    @staticmethod
    async def exchange_code(code: str) -> Optional[str]:
        """
        Intercambia el código de autorización de Embedded Signup por un
        user access token de Meta Graph API.

        Args:
            code: Código recibido de FB.login() en el frontend.

        Returns:
            User access token, o None si el intercambio falla.
        """
        settings = get_settings()
        url = "https://graph.facebook.com/v19.0/oauth/access_token"
        params = {
            "client_id": settings.meta_app_id,
            "client_secret": settings.whatsapp_app_secret,
            "code": code,
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                token = resp.json().get("access_token")
                log.info("[embedded_signup] código intercambiado correctamente")
                return token
        except httpx.HTTPStatusError as e:
            log.error(
                "[embedded_signup] error HTTP %s intercambiando código | %s",
                e.response.status_code,
                e.response.text[:300],
            )
            return None
        except Exception as e:
            log.error("[embedded_signup] error intercambiando código | %s", e)
            return None

    @staticmethod
    async def get_phone_info(access_token: str, phone_number_id: str) -> dict:
        """
        Obtiene información pública del número de WhatsApp registrado en Meta.

        Args:
            access_token: Token del usuario dueño del WABA.
            phone_number_id: ID del número en Meta.

        Returns:
            Dict con 'display_phone_number' y 'verified_name', o {} si falla.
        """
        settings = get_settings()
        url = f"https://graph.facebook.com/{settings.whatsapp_api_version}/{phone_number_id}"
        params = {
            "fields": "verified_name,display_phone_number",
            "access_token": access_token,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                log.info(
                    "[embedded_signup] phone info | id=%s | number=%s | name=%s",
                    phone_number_id,
                    data.get("display_phone_number"),
                    data.get("verified_name"),
                )
                return data
        except Exception as e:
            log.error(
                "[embedded_signup] error obteniendo phone info | id=%s | %s",
                phone_number_id, e,
            )
            return {}

    @staticmethod
    async def subscribe_waba(access_token: str, waba_id: str) -> bool:
        """
        Suscribe el WABA al app de CitasIA para recibir webhooks de mensajes.

        Sin esta suscripción, los mensajes de WhatsApp del número conectado
        no llegan al webhook de CitasIA.

        Args:
            access_token: Token del usuario dueño del WABA.
            waba_id: WhatsApp Business Account ID.

        Returns:
            True si la suscripción fue exitosa.
        """
        settings = get_settings()
        url = f"https://graph.facebook.com/{settings.whatsapp_api_version}/{waba_id}/subscribed_apps"
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, headers=headers)
                data = resp.json()
                success = data.get("success", False)
                if success:
                    log.info("[embedded_signup] WABA suscrito al app | waba=%s", waba_id)
                else:
                    log.warning(
                        "[embedded_signup] suscripción no confirmada | waba=%s | resp=%s",
                        waba_id, str(data)[:200],
                    )
                return success
        except Exception as e:
            log.error(
                "[embedded_signup] error suscribiendo WABA | waba=%s | %s", waba_id, e
            )
            return False

    @staticmethod
    def encrypt_token(token: str) -> str:
        """
        Cifra el access token con Fernet para almacenamiento seguro.

        Reutiliza la misma clave de cifrado que los tokens de Google OAuth.
        Principio VII: nunca almacenar tokens en texto plano.
        """
        from cryptography.fernet import Fernet
        settings = get_settings()
        key = settings.google_encryption_key
        if not key:
            raise RuntimeError("GOOGLE_ENCRYPTION_KEY no configurada — no se puede cifrar el token.")
        fernet = Fernet(key.encode() if isinstance(key, str) else key)
        return fernet.encrypt(token.encode()).decode()
