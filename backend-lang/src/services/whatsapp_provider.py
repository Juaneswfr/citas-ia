"""
WhatsAppProvider — adaptador de envío por proveedor (Meta directo | Kapso).

El transporte HTTP de Kapso se inyecta (httpx.AsyncBaseTransport) para probar sin red.
Principio XI: la API key nunca se registra en logs.
"""
import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, Protocol

import httpx

from services.whatsapp_service import WhatsAppService

log = logging.getLogger(__name__)


@dataclass
class SendResult:
    ok: bool
    message_id: str = ""
    error: str = ""


class WhatsAppProvider(Protocol):
    async def send_text(
        self, *, to: str, text: str, phone_number_id: str, access_token: Optional[str] = None
    ) -> SendResult: ...


class MetaProvider:
    """Envuelve WhatsAppService sin cambiar su comportamiento."""

    async def send_text(
        self, *, to: str, text: str, phone_number_id: str, access_token: Optional[str] = None
    ) -> SendResult:
        ok = await WhatsAppService.send_message(
            to=to, text=text, phone_number_id=phone_number_id, access_token=access_token
        )
        return SendResult(ok=ok, error="" if ok else "meta_send_failed")


class KapsoProvider:
    # shortcut: ruta/versión Meta-compatible fija, parametrizar si Kapso cambia de versión.
    _PATH = "/meta/whatsapp/v24.0/{pid}/messages"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.kapso.ai",
        transport: Optional[httpx.AsyncBaseTransport] = None,
        timeout: float = 10.0,
        max_retries: int = 2,
        sleep=asyncio.sleep,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._transport = transport
        self._timeout = timeout
        self._max_retries = max_retries
        self._sleep = sleep

    async def send_text(
        self, *, to: str, text: str, phone_number_id: str, access_token: Optional[str] = None
    ) -> SendResult:
        # Verificado contra kapso-openapi-whatsapp.yaml: POST /{phone_number_id}/messages (WhatsappMessage),
        # auth X-API-Key, campos messaging_product/recipient_type/to/type/text.body.
        url = self._base_url + self._PATH.format(pid=phone_number_id)
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        headers = {"X-API-Key": self._api_key, "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=self._timeout) as client:
                for attempt in range(self._max_retries + 1):
                    resp = await client.post(url, json=payload, headers=headers)
                    if (resp.status_code == 429 or resp.status_code >= 500) and attempt < self._max_retries:
                        try:
                            delay = float(resp.headers.get("Retry-After", 0.5 * 2**attempt))
                        except ValueError:
                            delay = 0.5
                        await self._sleep(min(delay, 2.0))
                        continue
                    break
        except httpx.TimeoutException:
            log.error("[kapso] timeout")
            return SendResult(ok=False, error="timeout")
        except httpx.HTTPError as e:
            log.error("[kapso] error de red | type=%s", type(e).__name__)
            return SendResult(ok=False, error="network_error")

        if resp.status_code >= 400:
            log.error("[kapso] rechazo HTTP %s", resp.status_code)
            return SendResult(ok=False, error=f"http_{resp.status_code}")
        try:
            message_id = resp.json().get("messages", [{}])[0].get("id", "")
        except (ValueError, AttributeError, IndexError):
            message_id = ""
        log.info("[kapso] enviado | wa_id=%s", message_id)
        return SendResult(ok=True, message_id=message_id)
