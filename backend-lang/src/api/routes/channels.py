"""
Router /workspaces/{workspace_id}/channels — Canales WhatsApp.
Router /workspaces/{workspace_id}/calendars — Calendarios Google.

Principio VII: Tokens OAuth se almacenan cifrados; nunca se retornan en responses.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status

from core.security import require_workspace_access
from core.supabase_client import get_supabase
from schemas.channel import (
    CalendarCreate, CalendarOut, ChannelCreate, ChannelOut, EmbeddedSignupRequest,
)

log = logging.getLogger(__name__)
router = APIRouter(tags=["channels", "calendars"])


# ── Canales WhatsApp ──────────────────────────────────────────────────────────

@router.get(
    "/workspaces/{workspace_id}/channels",
    response_model=list[ChannelOut],
    summary="Listar canales de WhatsApp del workspace",
    dependencies=[Depends(require_workspace_access("viewer"))],
)
async def list_channels(workspace_id: str):
    supabase = get_supabase()
    result = supabase.table("channels").select("*").eq("workspace_id", workspace_id).execute()
    return result.data or []


@router.post(
    "/workspaces/{workspace_id}/channels",
    response_model=ChannelOut,
    status_code=201,
    summary="Registrar canal de WhatsApp coexistente",
    dependencies=[Depends(require_workspace_access("owner"))],
)
async def create_channel(workspace_id: str, body: ChannelCreate, current_user: dict = Depends(require_workspace_access("owner"))):
    supabase = get_supabase()
    data = body.model_dump()
    data.update({"workspace_id": workspace_id, "status": "active"})
    result = supabase.table("channels").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Error registrando canal.")
    log.info("[channels] created | workspace=%s | phone=%s", workspace_id, body.phone_number)
    return result.data[0]


@router.patch(
    "/workspaces/{workspace_id}/channels/{channel_id}/status",
    response_model=ChannelOut,
    summary="Cambiar estado del canal (active|paused|disconnected)",
    dependencies=[Depends(require_workspace_access("owner"))],
)
async def update_channel_status(workspace_id: str, channel_id: str, new_status: str, current_user: dict = Depends(require_workspace_access("owner"))):
    from services.audit_service import AuditService
    allowed = {"active", "paused", "disconnected"}
    if new_status not in allowed:
        raise HTTPException(status_code=422, detail=f"Estado inválido. Permitidos: {allowed}")
    supabase = get_supabase()

    before = supabase.table("channels").select("id,status").eq("id", channel_id).eq("workspace_id", workspace_id).single().execute()

    result = (
        supabase.table("channels")
        .update({"status": new_status})
        .eq("id", channel_id)
        .eq("workspace_id", workspace_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Canal no encontrado.")

    await AuditService.log(
        workspace_id=workspace_id,
        actor_user_id=current_user.get("sub"),
        action="channel.status",
        entity_type="channel",
        entity_id=channel_id,
        before_data=before.data or {},
        after_data={"status": new_status},
    )
    log.info("[channels] status=%s | workspace=%s | channel=%s", new_status, workspace_id, channel_id)
    return result.data[0]


@router.post(
    "/workspaces/{workspace_id}/channels/embedded-signup",
    response_model=ChannelOut,
    status_code=201,
    summary="Conectar WhatsApp via Meta Embedded Signup (OTP incluido en el popup de Meta)",
)
async def embedded_signup_connect(
    workspace_id: str,
    body: EmbeddedSignupRequest,
    current_user: dict = Depends(require_workspace_access("owner")),
):
    """
    Completa el onboarding de WhatsApp Business después de que el dueño del negocio
    completó el flujo de Meta Embedded Signup en el frontend (login Facebook → WABA →
    número de teléfono → verificación OTP).

    El endpoint:
    1. Intercambia el code por un user access token
    2. Obtiene display_phone_number y verified_name del número
    3. Suscribe el WABA al app de CitasIA (webhooks)
    4. Cifra el access token y guarda el canal en Supabase
    """
    from services.embedded_signup_service import EmbeddedSignupService

    # 1. Intercambiar código por access token
    access_token = await EmbeddedSignupService.exchange_code(body.code)
    if not access_token:
        raise HTTPException(
            status_code=400,
            detail="Error intercambiando código con Meta. Verifica META_APP_ID y WHATSAPP_APP_SECRET.",
        )

    # 2. Obtener información del número
    phone_info = await EmbeddedSignupService.get_phone_info(access_token, body.phone_number_id)
    display_phone = phone_info.get("display_phone_number", "")
    verified_name = phone_info.get("verified_name", "")

    if not display_phone:
        raise HTTPException(
            status_code=400,
            detail="No se pudo obtener el número de teléfono de Meta. Verifica phone_number_id.",
        )

    # 3. Suscribir WABA al app (para recibir webhooks)
    subscribed = await EmbeddedSignupService.subscribe_waba(access_token, body.waba_id)
    if not subscribed:
        log.warning(
            "[channels] WABA no suscrito — webhooks no llegarán | workspace=%s | waba=%s",
            workspace_id, body.waba_id,
        )

    # 4. Cifrar access token antes de persistir
    encrypted_token = EmbeddedSignupService.encrypt_token(access_token)

    supabase = get_supabase()
    channel_data = {
        "workspace_id": workspace_id,
        "channel_type": "whatsapp",
        "provider": "meta_cloud_api",
        "phone_number": display_phone,
        "display_name": verified_name or display_phone,
        "coexistence_enabled": True,
        "external_account_id": body.waba_id,
        "status": "active",
        "metadata": {
            "phone_number_id": body.phone_number_id,
            "waba_id": body.waba_id,
            "waba_access_token_encrypted": encrypted_token,
            "webhook_subscribed": subscribed,
        },
    }

    # Verificar si ya existe un canal con este WABA (reconexión)
    existing = (
        supabase.table("channels")
        .select("id")
        .eq("workspace_id", workspace_id)
        .eq("external_account_id", body.waba_id)
        .execute()
    )

    if existing.data:
        result = (
            supabase.table("channels")
            .update(channel_data)
            .eq("id", existing.data[0]["id"])
            .execute()
        )
        log.info(
            "[channels] reconectado via embedded_signup | workspace=%s | phone=%s",
            workspace_id, display_phone,
        )
    else:
        result = supabase.table("channels").insert(channel_data).execute()
        log.info(
            "[channels] nuevo canal via embedded_signup | workspace=%s | phone=%s",
            workspace_id, display_phone,
        )

    if not result.data:
        raise HTTPException(status_code=500, detail="Error guardando canal en la base de datos.")

    return result.data[0]


# ── Calendarios Google ────────────────────────────────────────────────────────

@router.get(
    "/workspaces/{workspace_id}/calendars",
    response_model=list[CalendarOut],
    summary="Listar calendarios conectados",
    dependencies=[Depends(require_workspace_access("viewer"))],
)
async def list_calendars(workspace_id: str):
    supabase = get_supabase()
    # Principio VII: NO retornar oauth_refresh_token_encrypted
    result = (
        supabase.table("calendars")
        .select("id,workspace_id,name,google_calendar_id,connected_by_user_id,sync_enabled,sync_status,last_synced_at,created_at,updated_at")
        .eq("workspace_id", workspace_id)
        .execute()
    )
    return result.data or []


@router.post(
    "/workspaces/{workspace_id}/calendars",
    response_model=CalendarOut,
    status_code=201,
    summary="Conectar Google Calendar con OAuth",
    dependencies=[Depends(require_workspace_access("owner"))],
)
async def connect_calendar(workspace_id: str, body: CalendarCreate, current_user: dict = Depends(require_workspace_access("owner"))):
    from integrations.google_calendar import exchange_oauth_code

    token = await exchange_oauth_code(body.oauth_code)
    if not token:
        raise HTTPException(status_code=400, detail="Error intercambiando código OAuth con Google.")

    supabase = get_supabase()
    data = {
        "workspace_id": workspace_id,
        "name": body.name,
        "google_calendar_id": body.google_calendar_id,
        "connected_by_user_id": current_user.get("sub"),
        "oauth_refresh_token_encrypted": token["encrypted_refresh_token"],  # ya cifrado
        "sync_enabled": True,
        "sync_status": "active",
    }
    result = supabase.table("calendars").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Error guardando calendario.")

    log.info("[calendars] connected | workspace=%s | cal=%s", workspace_id, body.google_calendar_id)
    # Retornar sin el token cifrado
    return {k: v for k, v in result.data[0].items() if k != "oauth_refresh_token_encrypted"}


@router.delete(
    "/workspaces/{workspace_id}/calendars/{calendar_id}",
    status_code=204,
    summary="Desconectar calendario. Requiere confirmación del dueño.",
    dependencies=[Depends(require_workspace_access("owner"))],
)
async def disconnect_calendar(workspace_id: str, calendar_id: str, current_user: dict = Depends(require_workspace_access("owner"))):
    supabase = get_supabase()
    supabase.table("calendars").update({"sync_enabled": False, "sync_status": "disconnected"}).eq("id", calendar_id).eq("workspace_id", workspace_id).execute()
    log.info("[calendars] disconnected | workspace=%s | cal=%s | by=%s", workspace_id, calendar_id, current_user.get("sub"))
