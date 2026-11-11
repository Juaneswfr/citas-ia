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
    code: str = ""  # código corto del proveedor cuando rechaza (p. ej. 131047 = fuera de la ventana de 24 h)


class ProviderError(Exception):
    """Fallo del proveedor. Solo lleva un código corto, nunca cuerpos de respuesta ni claves."""

    def __init__(self, error: str, code: str = ""):
        super().__init__(error)
        self.error = error
        self.code = code


def _error_code(resp: httpx.Response) -> str:
    """Código corto del error del proveedor (p. ej. '131047', 'marketing_preference_stopped')."""
    try:
        body = resp.json()
    except ValueError:
        return ""
    if not isinstance(body, dict):
        return ""
    err = body.get("error")
    if isinstance(err, dict):
        return str(err.get("code") or err.get("type") or "")[:60]
    return str(err or body.get("code") or "")[:60]


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
    _API = "/meta/whatsapp/v24.0"
    _PATH = _API + "/{pid}/messages"

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

    def _headers(self) -> dict:
        return {"X-API-Key": self._api_key, "Content-Type": "application/json"}

    # ── Mensajes ──────────────────────────────────────────────────────────────

    async def send_text(
        self, *, to: str, text: str, phone_number_id: str, access_token: Optional[str] = None
    ) -> SendResult:
        # Verificado contra kapso-openapi-whatsapp.yaml: POST /{phone_number_id}/messages (WhatsappMessage),
        # auth X-API-Key, campos messaging_product/recipient_type/to/type/text.body.
        return await self._send_message(phone_number_id, {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        })

    async def send_template(
        self, *, to: str, phone_number_id: str, name: str, language: str,
        body_params: Optional[dict] = None, button_payloads: Optional[list] = None,
    ) -> SendResult:
        """Envía una plantilla aprobada (sirve fuera de la ventana de 24 h).

        body_params: {nombre_parametro: valor} para plantillas con parámetros NOMBRADOS.
        button_payloads: un payload por botón de respuesta rápida, en el orden de la plantilla.
        Forma tomada de docs.kapso.ai (send-a-message, templates/buttons).
        """
        components: list = []
        if body_params:
            components.append({"type": "body", "parameters": [
                {"type": "text", "parameter_name": key, "text": str(value)} for key, value in body_params.items()
            ]})
        for index, payload in enumerate(button_payloads or []):
            components.append({
                "type": "button", "sub_type": "quick_reply", "index": str(index),
                "parameters": [{"type": "payload", "payload": payload}],
            })
        template: dict = {"name": name, "language": {"code": language}}
        if components:
            template["components"] = components
        return await self._send_message(phone_number_id, {
            "messaging_product": "whatsapp", "recipient_type": "individual", "to": to,
            "type": "template", "template": template,
        })

    async def _send_message(self, phone_number_id: str, payload: dict) -> SendResult:
        """POST al endpoint de mensajes con reintentos en 429/5xx. Nunca registra el cuerpo ni la clave."""
        url = self._base_url + self._PATH.format(pid=phone_number_id)
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=self._timeout) as client:
                for attempt in range(self._max_retries + 1):
                    resp = await client.post(url, json=payload, headers=self._headers())
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
            code = _error_code(resp)
            log.error("[kapso] rechazo HTTP %s | code=%s", resp.status_code, code)
            return SendResult(ok=False, error=f"http_{resp.status_code}", code=code)
        try:
            message_id = resp.json().get("messages", [{}])[0].get("id", "")
        except (ValueError, AttributeError, IndexError):
            message_id = ""
        log.info("[kapso] enviado | wa_id=%s", message_id)
        return SendResult(ok=True, message_id=message_id)

    # ── Plantillas (viven en la cuenta de WhatsApp / WABA de cada negocio) ────

    async def _api(
        self, method: str, path: str, *, params: Optional[dict] = None, body: Optional[dict] = None
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=self._timeout) as client:
                resp = await client.request(
                    method, self._base_url + self._API + path, params=params, json=body, headers=self._headers()
                )
        except httpx.HTTPError as e:
            raise ProviderError(f"network_error:{type(e).__name__}") from None
        if resp.status_code >= 400:
            raise ProviderError(f"http_{resp.status_code}", _error_code(resp))
        return resp

    async def list_templates(self, business_account_id: str) -> list[dict]:
        """Plantillas de la cuenta con su estado (APPROVED | PENDING | REJECTED | DISABLED)."""
        resp = await self._api("GET", f"/{business_account_id}/message_templates", params={"limit": 100})
        try:
            data = resp.json().get("data")
        except (ValueError, AttributeError):
            raise ProviderError("bad_response") from None
        return data if isinstance(data, list) else []

    async def create_template(self, business_account_id: str, definition: dict) -> dict:
        """Envía una plantilla a revisión de Meta. Devuelve {id, status, category}."""
        resp = await self._api("POST", f"/{business_account_id}/message_templates", body=definition)
        try:
            data = resp.json()
        except ValueError:
            raise ProviderError("bad_response") from None
        return data if isinstance(data, dict) else {}

    # ── Archivos recibidos ────────────────────────────────────────────────────

    async def download_media(self, media_id: str, phone_number_id: str, max_bytes: int) -> bytes:
        """Descarga un archivo que envió un cliente. ProviderError("too_large") si supera max_bytes.

        Dos pasos (docs.kapso.ai, media/get-media-url): GET /{media_id}?phone_number_id= devuelve
        download_url (válida ~4 min; el token va en la URL) y luego se descarga en streaming con tope.
        """
        meta = await self._api("GET", f"/{media_id}", params={"phone_number_id": phone_number_id})
        try:
            info = meta.json()
        except ValueError:
            raise ProviderError("bad_response") from None
        if not isinstance(info, dict):
            raise ProviderError("bad_response")
        size = str(info.get("file_size") or "")
        if size.isdigit() and int(size) > max_bytes:
            raise ProviderError("too_large")
        url = str(info.get("download_url") or "")
        if not url.startswith(self._base_url + "/"):  # solo se descarga desde el propio proveedor
            raise ProviderError("no_download_url")
        buf = bytearray()
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=self._timeout * 2) as client:
                async with client.stream("GET", url) as resp:
                    if resp.status_code >= 400:
                        raise ProviderError(f"http_{resp.status_code}")
                    async for chunk in resp.aiter_bytes():
                        buf += chunk
                        if len(buf) > max_bytes:
                            raise ProviderError("too_large")
        except httpx.HTTPError as e:
            raise ProviderError(f"network_error:{type(e).__name__}") from None
        return bytes(buf)
