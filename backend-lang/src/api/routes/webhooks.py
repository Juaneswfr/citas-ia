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


def _verify_kapso_signature(request_body: bytes, signature_header: str) -> bool:
    """HMAC-SHA256 hex del raw body (X-Webhook-Signature) contra el secreto de proyecto o de número.

    El evento va en un header sin firmar, así que no se usa para elegir secreto: se prueban todos
    (sin cortocircuito) y basta que uno coincida. KAPSO_WEBHOOK_SECRET es solo compatibilidad.
    """
    s = get_settings()
    secrets = [x for x in (s.kapso_webhook_secret_project, s.kapso_webhook_secret_number,
                           s.kapso_webhook_secret) if x]
    sig = (signature_header or "").strip()
    if not secrets or not sig:
        return False
    ok = False
    for secret in secrets:
        expected = hmac.new(secret.encode(), request_body, hashlib.sha256).hexdigest()
        ok |= hmac.compare_digest(expected, sig)
    return ok


async def _claim_idempotency_key(key: str, event: str) -> bool:
    """True si la clave es nueva (se reclama); False si ya existía (reintento)."""
    from core import database

    async with database._pool.acquire() as conn:
        row = await conn.fetchval(
            "INSERT INTO public.kapso_webhook_events (idempotency_key, event) "
            "VALUES ($1, $2) ON CONFLICT (idempotency_key) DO NOTHING RETURNING 1",
            key, event,
        )
    return row is not None


@router.post("/kapso", summary="Eventos entrantes de Kapso")
async def kapso_inbound(request: Request):
    if not get_settings().kapso_enabled:
        raise HTTPException(status_code=404)

    body_bytes = await request.body()
    if not _verify_kapso_signature(body_bytes, request.headers.get("X-Webhook-Signature", "")):
        log.warning("[webhooks/kapso] firma inválida — rechazado")
        raise HTTPException(status_code=401)

    event = request.headers.get("X-Webhook-Event", "")
    key = request.headers.get("X-Idempotency-Key", "")
    if not key:
        raise HTTPException(status_code=400)

    if not await _claim_idempotency_key(key, event):
        log.info("[webhooks/kapso] duplicado ignorado | event=%s", event)
        return {"status": "duplicate"}

    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(status_code=400)
    # Lote (X-Webhook-Batch: true): eventos en payload["data"]; sin lote: el payload es el evento.
    batch = request.headers.get("X-Webhook-Batch", "").lower() == "true"
    items = payload.get("data") if batch and isinstance(payload.get("data"), list) else [payload]

    import asyncio
    asyncio.create_task(_process_kapso_events(event, items))
    return {"status": "ok"}


async def _process_kapso_events(event: str, items: list):
    """Procesa mensajes entrantes de Kapso fuera del ciclo de request.

    SUPUESTO (sin verificar): nombres de headers (X-Webhook-Signature/Event/X-Idempotency-Key),
    evento "whatsapp.message.received" y forma del payload vienen del plan, no de docs oficiales.
    """
    if event == "whatsapp.phone_number.created":
        from core import database
        from services.kapso_onboarding import KapsoOnboardingService
        for item in items:
            try:
                async with database._pool.acquire() as conn:
                    await KapsoOnboardingService.handle_phone_number_created(conn, item)
            except Exception as e:
                log.error("[webhooks/kapso] error en phone_number.created | err=%s", type(e).__name__)
        return
    if event != "whatsapp.message.received":
        return
    from services.conversation_service import ConversationService
    from services.agent_service import AgentService

    for item in items:
        try:
            msg = item.get("message") or {}
            customer_phone = msg.get("from")
            text = (msg.get("text") or {}).get("body", "")
            business_phone_number_id = item.get("phone_number_id")
            if not customer_phone or not text or not business_phone_number_id:
                continue
            conversation = await ConversationService.find_or_create(
                customer_phone=customer_phone, phone_number_id=business_phone_number_id
            )
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
            log.error("[webhooks/kapso] error procesando evento | err=%s", type(e).__name__, exc_info=False)


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
