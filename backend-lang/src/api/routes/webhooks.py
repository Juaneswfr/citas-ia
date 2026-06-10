"""
Router /webhooks — WhatsApp y Google Calendar.

Principio XI: Todo webhook MUST validar firma/token antes de procesar.
Principio VII: No exponer secretos en logs ni responses.
SC-007: Rate limiting 200 req/min por workspace en /webhooks/whatsapp.
"""
import hashlib
import hmac
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter

from core.config import get_settings
from core.supabase_client import get_supabase

log = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _get_workspace_from_request(request: Request) -> str:
    """Extrae workspace_id del payload para usar como clave de rate limiting."""
    # Intentar extraer del query param o del body (usado por slowapi)
    return request.headers.get("X-Workspace-ID", request.client.host if request.client else "unknown")


_limiter = Limiter(key_func=_get_workspace_from_request)


def _verify_whatsapp_signature(request_body: bytes, signature_header: str) -> bool:
    """
    Valida la firma HMAC-SHA256 de Meta/WhatsApp.
    Principio XI: Sin verificación de firma, el endpoint es un vector de ataque.
    """
    settings = get_settings()
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        settings.whatsapp_app_secret.encode(),
        request_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@router.get(
    "/whatsapp",
    summary="Verificación del webhook de WhatsApp (handshake inicial de Meta)",
)
async def whatsapp_verify(request: Request):
    """
    Meta llama a GET /webhooks/whatsapp con mode, challenge y verify_token
    para confirmar el endpoint. Responde con challenge si el token coincide.
    """
    settings = get_settings()
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == settings.whatsapp_verify_token:
        log.info("[webhooks/whatsapp] handshake OK")
        return int(challenge)

    raise HTTPException(status_code=403, detail="Verify token inválido.")


@router.post(
    "/whatsapp",
    summary="Recibir mensajes entrantes de WhatsApp",
)
@_limiter.limit("200/minute")
async def whatsapp_inbound(request: Request):
    """
    Flujo:
    1. Validar firma HMAC (Principio XI).
    2. Parsear payload.
    3. Identificar workspace/canal.
    4. Encontrar o crear conversación.
    5. Persistir mensaje.
    6. Lanzar agente LangGraph (async, no bloquea el ACK).
    7. Responder 200 inmediatamente (WhatsApp requiere ACK < 20s).
    """
    body_bytes = await request.body()
    sig = request.headers.get("X-Hub-Signature-256", "")

    if not _verify_whatsapp_signature(body_bytes, sig):
        log.warning("[webhooks/whatsapp] firma inválida — rechazado")
        raise HTTPException(status_code=403, detail="Firma inválida.")

    payload = await request.json()
    log.info("[webhooks/whatsapp] recibido | entries=%d", len(payload.get("entry", [])))

    # Procesar en background para no bloquear el ACK
    import asyncio
    asyncio.create_task(_process_whatsapp_payload(payload))

    return {"status": "ok"}


async def _process_whatsapp_payload(payload: dict):
    """Procesa el payload de WhatsApp fuera del ciclo de request."""
    from services.conversation_service import ConversationService
    from services.agent_service import AgentService

    try:
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                # phone_number_id identifica QUÉ número del negocio recibió el mensaje
                business_phone_number_id = value.get("metadata", {}).get("phone_number_id")
                messages = value.get("messages", [])
                for msg in messages:
                    customer_phone = msg.get("from")
                    text = msg.get("text", {}).get("body", "")
                    if not customer_phone or not text or not business_phone_number_id:
                        continue

                    conversation = await ConversationService.find_or_create(
                        customer_phone=customer_phone,
                        phone_number_id=business_phone_number_id,
                    )
                    # Guardar teléfono en conversation para que AgentService pueda enviar
                    conversation["customer_phone"] = customer_phone
                    await ConversationService.save_message(
                        conversation_id=conversation["id"],
                        workspace_id=conversation["workspace_id"],
                        channel_id=conversation["channel_id"],
                        customer_id=conversation.get("customer_id"),
                        direction="inbound",
                        sender_type="customer",
                        content=text,
                    )
                    await AgentService.run(conversation=conversation, message=text)
    except Exception as e:
        log.error("[webhooks/whatsapp] error procesando payload | err=%s", e, exc_info=True)


@router.post(
    "/google-calendar",
    summary="Notificaciones de cambio de Google Calendar",
)
async def google_calendar_notification(request: Request):
    """
    Google Calendar envía notificaciones push cuando hay cambios.
    Principio VI: Mantener Calendar sincronizado con la BD.
    """
    channel_id = request.headers.get("X-Goog-Channel-ID")
    resource_state = request.headers.get("X-Goog-Resource-State")

    if resource_state == "sync":
        log.info("[webhooks/google-calendar] sync handshake | channel=%s", channel_id)
        return {"status": "ok"}

    log.info("[webhooks/google-calendar] cambio detectado | channel=%s | state=%s",
             channel_id, resource_state)

    # Procesar sincronización en background
    import asyncio
    asyncio.create_task(_sync_calendar_changes(channel_id))
    return {"status": "ok"}


async def _sync_calendar_changes(channel_id: str):
    """Sincroniza cambios de Calendar detectados vía notificación push."""
    from services.calendar_service import CalendarService
    try:
        await CalendarService.sync_from_notification(channel_id)
    except Exception as e:
        log.error("[webhooks/google-calendar] error sync | channel=%s | err=%s", channel_id, e, exc_info=True)
