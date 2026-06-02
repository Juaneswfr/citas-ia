"""
WhatsAppService — Envío de mensajes salientes via Meta Graph API.

Principio II (Constitución): Toda lógica de envío vive en el backend.
Principio XI: El API token nunca se expone en logs ni responses.
Responsabilidad única (Principio X): solo maneja el envío saliente por WhatsApp.
"""
import logging
from typing import Optional

import httpx

from core.config import get_settings

log = logging.getLogger(__name__)


class WhatsAppService:
    """Envía mensajes de texto via Meta WhatsApp Business API."""

    @staticmethod
    def _base_url() -> str:
        settings = get_settings()
        return (
            f"https://graph.facebook.com/{settings.whatsapp_api_version}"
            f"/{settings.whatsapp_phone_number_id}/messages"
        )

    @staticmethod
    async def send_message(
        to: str,
        text: str,
        phone_number_id: Optional[str] = None,
    ) -> bool:
        """
        Envía un mensaje de texto a un número WhatsApp.

        Args:
            to: Número E.164 del destinatario (ej: "+573001234567").
            text: Texto del mensaje (≤4096 caracteres).
            phone_number_id: Override del phone_number_id del canal; si None usa el de Settings.

        Returns:
            True si Meta confirmó el envío, False si hubo error.
        """
        settings = get_settings()

        pid = phone_number_id or settings.whatsapp_phone_number_id
        if not pid:
            log.error("[whatsapp] WHATSAPP_PHONE_NUMBER_ID no configurado — mensaje no enviado")
            return False

        url = (
            f"https://graph.facebook.com/{settings.whatsapp_api_version}"
            f"/{pid}/messages"
        )
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        headers = {
            "Authorization": f"Bearer {settings.whatsapp_api_token}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                message_id = data.get("messages", [{}])[0].get("id", "")
                log.info("[whatsapp] enviado | to=%s | wa_id=%s", to, message_id)
                return True

        except httpx.HTTPStatusError as e:
            log.error(
                "[whatsapp] error HTTP %s | to=%s | body=%s",
                e.response.status_code, to, e.response.text[:200],
            )
            return False
        except Exception as e:
            log.error("[whatsapp] error enviando mensaje | to=%s | err=%s", to, e)
            return False

    @staticmethod
    async def send_template(
        to: str,
        template_name: str,
        language_code: str = "es",
        components: Optional[list] = None,
        phone_number_id: Optional[str] = None,
    ) -> bool:
        """
        Envía un mensaje de plantilla (template) aprobado por Meta.
        Útil para recordatorios de cita que se envían fuera de la ventana de 24h.

        Args:
            to: Número E.164 del destinatario.
            template_name: Nombre de la plantilla aprobada en Meta.
            language_code: Código de idioma (default: "es").
            components: Lista de componentes de la plantilla (header, body, buttons).
            phone_number_id: Override del phone_number_id.

        Returns:
            True si Meta confirmó el envío.
        """
        settings = get_settings()
        pid = phone_number_id or settings.whatsapp_phone_number_id
        if not pid:
            log.error("[whatsapp] WHATSAPP_PHONE_NUMBER_ID no configurado")
            return False

        url = (
            f"https://graph.facebook.com/{settings.whatsapp_api_version}"
            f"/{pid}/messages"
        )
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }
        if components:
            payload["template"]["components"] = components

        headers = {
            "Authorization": f"Bearer {settings.whatsapp_api_token}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                log.info("[whatsapp] template enviado | to=%s | template=%s", to, template_name)
                return True
        except Exception as e:
            log.error("[whatsapp] error enviando template | to=%s | template=%s | err=%s",
                      to, template_name, e)
            return False
