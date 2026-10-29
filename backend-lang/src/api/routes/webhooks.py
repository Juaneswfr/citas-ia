"""
Router /webhooks — WhatsApp y Google Calendar.

Principio XI: Todo webhook MUST validar firma/token antes de procesar.
Principio VII: No exponer secretos en logs ni responses.
SC-007: Rate limiting 200 req/min por workspace en /webhooks/whatsapp.
"""
import asyncio
import hashlib
import hmac
import json
import logging
from cryptography.fernet import InvalidToken
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
# Kapso: la clave es la IP, no X-Workspace-ID (un header que el emisor controla anularía el límite).
_kapso_limiter = Limiter(key_func=lambda request: request.client.host if request.client else "unknown")
_KAPSO_LIMIT = "300/minute"
_MAX_BODY = 1024 * 1024  # 1 MB

# Referencias fuertes: el loop solo guarda weak refs a las tareas y el GC podría recolectarlas.
_bg_tasks: set = set()


def _spawn(coro):
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


async def _read_body_limited(request: Request) -> bytes:
    """Lee el cuerpo y responde 413 si supera 1 MB, sin bufferizar más de lo permitido."""
    cl = request.headers.get("content-length", "")
    if cl.isdigit() and int(cl) > _MAX_BODY:
        raise HTTPException(status_code=413)
    buf = bytearray()
    async for chunk in request.stream():
        buf += chunk
        if len(buf) > _MAX_BODY:
            raise HTTPException(status_code=413)
    return bytes(buf)


def _verify_whatsapp_signature(request_body: bytes, signature_header: str) -> bool:
    """
    Valida la firma HMAC-SHA256 de Meta/WhatsApp.
    Principio XI: Sin verificación de firma, el endpoint es un vector de ataque.
    """
    settings = get_settings()
    if not settings.whatsapp_app_secret:  # fail closed: nunca firmar con clave vacía
        return False
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        settings.whatsapp_app_secret.encode(),
        request_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected.encode(), signature_header.encode())


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
    if not get_settings().whatsapp_app_secret:
        log.error("[webhooks/whatsapp] WHATSAPP_APP_SECRET no configurado — webhook deshabilitado")
        raise HTTPException(status_code=503, detail="Webhook no disponible.")
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
    """HMAC-SHA256 hex del raw body (X-Webhook-Signature) contra el secreto de PROYECTO únicamente.

    Los mensajes se firman con el secreto de cada número y entran por /kapso/n/{token}.
    """
    secret = get_settings().kapso_webhook_secret_project
    sig = (signature_header or "").strip()
    if not secret or not sig:
        return False
    expected = hmac.new(secret.encode(), request_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.encode(), sig.encode())


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


async def _release_idempotency_key(key: str) -> None:
    from core import database

    async with database._pool.acquire() as conn:
        await conn.execute("DELETE FROM public.kapso_webhook_events WHERE idempotency_key=$1", key)


async def _run_kapso_task(key: str, event: str, items: list) -> None:
    """Procesa en background; si falla, libera la clave para que el reintento de Kapso procese.

    Riesgo residual: en un lote con fallo parcial, el reintento reprocesa también los ítems que ya
    habían salido bien (mensajes duplicados); y si el proceso muere (o falla la propia liberación)
    tras reclamar la clave, el evento se pierde. Cierre real: cola/outbox persistente o idempotencia por mensaje.
    """
    try:
        await _process_kapso_events(event, items)
    except Exception as e:
        log.error("[webhooks/kapso] procesamiento falló, liberando clave | err=%s", type(e).__name__)
        try:
            await _release_idempotency_key(key)
        except Exception as e2:
            log.error("[webhooks/kapso] no se pudo liberar la clave | err=%s", type(e2).__name__)


async def _get_channel_by_webhook_token(token: str):
    from core import database

    async with database._pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT phone_number_id, webhook_secret_encrypted FROM public.channels WHERE webhook_token=$1",
            token,
        )


@router.post("/kapso/n/{token}", summary="Mensajes entrantes de Kapso (webhook por número)")
@_kapso_limiter.limit(_KAPSO_LIMIT)
async def kapso_number_inbound(token: str, request: Request):
    s = get_settings()
    if not s.kapso_enabled:
        raise HTTPException(status_code=404)
    body_bytes = await _read_body_limited(request)
    channel = await _get_channel_by_webhook_token(token)
    if channel is None or not channel["webhook_secret_encrypted"]:
        raise HTTPException(status_code=404)

    from services.kapso_onboarding import decrypt_secret

    try:
        secret = decrypt_secret(s.kapso_secrets_key, channel["webhook_secret_encrypted"])
    except (InvalidToken, ValueError) as e:
        log.error("[webhooks/kapso/n] no se pudo descifrar el secreto del canal | err=%s", type(e).__name__)
        raise HTTPException(status_code=503)
    expected = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
    sig = request.headers.get("X-Webhook-Signature", "").strip()
    if not hmac.compare_digest(expected.encode(), sig.encode()):
        log.warning("[webhooks/kapso/n] firma inválida — rechazado")
        raise HTTPException(status_code=401)

    key = request.headers.get("X-Idempotency-Key", "")
    if not key:
        raise HTTPException(status_code=400)
    event = request.headers.get("X-Webhook-Event", "")
    if not await _claim_idempotency_key(key, event):
        log.info("[webhooks/kapso/n] duplicado ignorado | event=%s", event)
        return {"status": "duplicate"}
    try:
        payload = json.loads(body_bytes)
    except ValueError:
        raise HTTPException(status_code=400)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400)
    batch = request.headers.get("X-Webhook-Batch", "").lower() == "true"
    items = payload.get("data") if batch and isinstance(payload.get("data"), list) else [payload]
    # El número lo fija el canal del token, no el cuerpo: un secreto no sirve para otro número.
    items = [{**i, "phone_number_id": channel["phone_number_id"]} for i in items if isinstance(i, dict)]

    if event == "whatsapp.message.received":
        _spawn(_run_kapso_task(key, event, items))
    return {"status": "ok"}


async def _get_channel_by_phone_number_id(phone_number_id: str):
    from core import database

    async with database._pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT id, workspace_id, phone_number_id FROM public.channels WHERE phone_number_id=$1",
            phone_number_id,
        )


@router.post("/kapso/sandbox", summary="Mensajes entrantes del sandbox de Kapso")
@_kapso_limiter.limit(_KAPSO_LIMIT)
async def kapso_sandbox_inbound(request: Request):
    """Webhook para el sandbox de Kapso. Verifica firma con KAPSO_SANDBOX_WEBHOOK_SECRET,
    extrae phone_number_id del payload y rutea al workspace del canal."""
    s = get_settings()
    if not s.kapso_enabled:
        raise HTTPException(status_code=404)
    if not s.kapso_sandbox_webhook_secret:
        log.error("[webhooks/kapso/sandbox] KAPSO_SANDBOX_WEBHOOK_SECRET no configurado")
        raise HTTPException(status_code=503)

    body_bytes = await _read_body_limited(request)
    sig = request.headers.get("X-Webhook-Signature", "").strip()
    expected = hmac.new(s.kapso_sandbox_webhook_secret.encode(), body_bytes, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected.encode(), sig.encode()):
        log.warning("[webhooks/kapso/sandbox] firma inválida — rechazado")
        raise HTTPException(status_code=401)

    key = request.headers.get("X-Idempotency-Key", "")
    if not key:
        raise HTTPException(status_code=400)
    event = request.headers.get("X-Webhook-Event", "")
    if not await _claim_idempotency_key(key, event):
        return {"status": "duplicate"}

    try:
        payload = json.loads(body_bytes)
    except ValueError:
        raise HTTPException(status_code=400)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400)

    batch = request.headers.get("X-Webhook-Batch", "").lower() == "true"
    items = payload.get("data") if batch and isinstance(payload.get("data"), list) else [payload]

    if event == "whatsapp.message.received":
        _spawn(_run_kapso_task(key, event, items))
    return {"status": "ok"}


@router.post("/kapso", summary="Eventos de proyecto de Kapso (no mensajes)")
@_kapso_limiter.limit(_KAPSO_LIMIT)
async def kapso_inbound(request: Request):
    if not get_settings().kapso_enabled:
        raise HTTPException(status_code=404)

    body_bytes = await _read_body_limited(request)
    if not _verify_kapso_signature(body_bytes, request.headers.get("X-Webhook-Signature", "")):
        log.warning("[webhooks/kapso] firma inválida — rechazado")
        raise HTTPException(status_code=401)

    event = request.headers.get("X-Webhook-Event", "")
    if event.startswith("whatsapp.message."):  # los mensajes solo entran por /kapso/n/{token}
        raise HTTPException(status_code=400)
    key = request.headers.get("X-Idempotency-Key", "")
    if not key:
        raise HTTPException(status_code=400)

    if not await _claim_idempotency_key(key, event):
        log.info("[webhooks/kapso] duplicado ignorado | event=%s", event)
        return {"status": "duplicate"}

    try:
        payload = json.loads(body_bytes)
    except ValueError:
        raise HTTPException(status_code=400)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400)
    # Lote (X-Webhook-Batch: true): eventos en payload["data"]; sin lote: el payload es el evento.
    batch = request.headers.get("X-Webhook-Batch", "").lower() == "true"
    items = payload.get("data") if batch and isinstance(payload.get("data"), list) else [payload]

    _spawn(_run_kapso_task(key, event, items))
    return {"status": "ok"}


async def _process_kapso_events(event: str, items: list):
    """Procesa mensajes entrantes de Kapso fuera del ciclo de request.

    SUPUESTO (sin verificar): nombres de headers (X-Webhook-Signature/Event/X-Idempotency-Key),
    evento "whatsapp.message.received" y forma del payload vienen del plan, no de docs oficiales.
    """
    if event in ("whatsapp.phone_number.created", "whatsapp.phone_number.deleted"):
        from core import database
        from services import kapso_onboarding as ko
        s = get_settings()
        client = ko.KapsoPlatformClient(s.kapso_api_key, s.kapso_base_url)
        failed = False
        for item in items:
            try:
                async with database._pool.acquire() as conn:
                    if event.endswith(".created"):
                        if await ko.KapsoOnboardingService.handle_phone_number_created(conn, item):
                            await ko.provision_number_webhook(
                                conn, client, phone_number_id=item["phone_number_id"],
                                base_url=s.frontend_url, secrets_key=s.kapso_secrets_key)
                    elif item.get("phone_number_id"):
                        await ko.deprovision_number_webhook(
                            conn, client, phone_number_id=item["phone_number_id"])
            except Exception as e:
                failed = True
                log.error("[webhooks/kapso] error en %s | err=%s", event, type(e).__name__)
        if failed:
            raise RuntimeError("kapso_item_failed")  # _run_kapso_task libera la clave
        return
    if event != "whatsapp.message.received":
        return
    from services.conversation_service import ConversationService
    from services.agent_service import AgentService

    failed = False
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
            failed = True
            log.error("[webhooks/kapso] error procesando evento | err=%s", type(e).__name__, exc_info=False)
    if failed:
        raise RuntimeError("kapso_item_failed")  # _run_kapso_task libera la clave


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
