"""
Router /workspaces/{workspace_id}/channels — Canales WhatsApp.
Router /workspaces/{workspace_id}/calendars — Calendarios Google.

Principio VII: Tokens OAuth se almacenan cifrados; nunca se retornan en responses.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status

import asyncpg
from core.database import get_db
from core.security import require_workspace_access
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
async def list_channels(
    workspace_id: str,
    db: asyncpg.Connection = Depends(get_db),
):
    rows = await db.fetch("SELECT * FROM channels WHERE workspace_id = $1", workspace_id)
    return [dict(r) for r in rows]


@router.post(
    "/workspaces/{workspace_id}/channels",
    response_model=ChannelOut,
    status_code=201,
    summary="Registrar canal de WhatsApp coexistente",
    dependencies=[Depends(require_workspace_access("workspace_owner"))],
)
async def create_channel(
    workspace_id: str,
    body: ChannelCreate,
    current_user: dict = Depends(require_workspace_access("workspace_owner")),
    db: asyncpg.Connection = Depends(get_db),
):
    import json
    data = body.model_dump()
    row = await db.fetchrow(
        """
        INSERT INTO channels
            (workspace_id, channel_type, provider, phone_number, phone_number_id,
             display_name, coexistence_enabled, external_account_id, status, metadata)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'active',$9)
        RETURNING *
        """,
        workspace_id,
        data.get("channel_type", "whatsapp"),
        data.get("provider", ""),
        data.get("phone_number", ""),
        data.get("phone_number_id"),
        data.get("display_name"),
        data.get("coexistence_enabled", True),
        data.get("external_account_id"),
        json.dumps(data.get("metadata")) if data.get("metadata") else None,
    )
    if not row:
        raise HTTPException(status_code=500, detail="Error registrando canal.")
    log.info("[channels] created | workspace=%s | phone=%s", workspace_id, body.phone_number)
    return dict(row)


@router.patch(
    "/workspaces/{workspace_id}/channels/{channel_id}/status",
    response_model=ChannelOut,
    summary="Cambiar estado del canal (active|paused|disconnected)",
    dependencies=[Depends(require_workspace_access("workspace_owner"))],
)
async def update_channel_status(
    workspace_id: str,
    channel_id: str,
    new_status: str,
    current_user: dict = Depends(require_workspace_access("workspace_owner")),
    db: asyncpg.Connection = Depends(get_db),
):
    from services.audit_service import AuditService
    allowed = {"active", "paused", "disconnected"}
    if new_status not in allowed:
        raise HTTPException(status_code=422, detail=f"Estado inválido. Permitidos: {allowed}")

    before = await db.fetchrow(
        "SELECT id, status FROM channels WHERE id = $1 AND workspace_id = $2",
        channel_id, workspace_id,
    )
    row = await db.fetchrow(
        "UPDATE channels SET status = $1 WHERE id = $2 AND workspace_id = $3 RETURNING *",
        new_status, channel_id, workspace_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Canal no encontrado.")

    await AuditService.log(
        workspace_id=workspace_id,
        actor_user_id=current_user.get("sub"),
        action="channel.status",
        entity_type="channel",
        entity_id=channel_id,
        before_data=dict(before) if before else {},
        after_data={"status": new_status},
    )
    log.info("[channels] status=%s | workspace=%s | channel=%s", new_status, workspace_id, channel_id)
    return dict(row)


@router.post(
    "/workspaces/{workspace_id}/channels/embedded-signup",
    response_model=ChannelOut,
    status_code=201,
    summary="Conectar WhatsApp via Meta Embedded Signup",
)
async def embedded_signup_connect(
    workspace_id: str,
    body: EmbeddedSignupRequest,
    current_user: dict = Depends(require_workspace_access("workspace_owner")),
    db: asyncpg.Connection = Depends(get_db),
):
    import json
    from services.embedded_signup_service import EmbeddedSignupService

    access_token = await EmbeddedSignupService.exchange_code(body.code)
    if not access_token:
        raise HTTPException(
            status_code=400,
            detail="Error intercambiando código con Meta. Verifica META_APP_ID y WHATSAPP_APP_SECRET.",
        )

    phone_info = await EmbeddedSignupService.get_phone_info(access_token, body.phone_number_id)
    display_phone = phone_info.get("display_phone_number", "")
    verified_name = phone_info.get("verified_name", "")

    if not display_phone:
        raise HTTPException(
            status_code=400, detail="No se pudo obtener el número de teléfono de Meta.",
        )

    subscribed = await EmbeddedSignupService.subscribe_waba(access_token, body.waba_id)
    if not subscribed:
        log.warning("[channels] WABA no suscrito | workspace=%s | waba=%s", workspace_id, body.waba_id)

    encrypted_token = EmbeddedSignupService.encrypt_token(access_token)

    metadata = json.dumps({
        "phone_number_id": body.phone_number_id,
        "waba_id": body.waba_id,
        "waba_access_token_encrypted": encrypted_token,
        "webhook_subscribed": subscribed,
    })

    # Verificar si ya existe un canal con este WABA (reconexión)
    existing = await db.fetchrow(
        "SELECT id FROM channels WHERE workspace_id = $1 AND external_account_id = $2",
        workspace_id, body.waba_id,
    )

    if existing:
        row = await db.fetchrow(
            """
            UPDATE channels SET
                phone_number = $1, phone_number_id = $2, display_name = $3,
                status = 'active', metadata = $4
            WHERE id = $5
            RETURNING *
            """,
            display_phone, body.phone_number_id, verified_name or display_phone,
            metadata, existing["id"],
        )
        log.info("[channels] reconectado | workspace=%s | phone=%s", workspace_id, display_phone)
    else:
        row = await db.fetchrow(
            """
            INSERT INTO channels
                (workspace_id, channel_type, provider, phone_number, phone_number_id,
                 display_name, coexistence_enabled, external_account_id, status, metadata)
            VALUES ($1,'whatsapp','meta_cloud_api',$2,$3,$4,TRUE,$5,'active',$6)
            RETURNING *
            """,
            workspace_id, display_phone, body.phone_number_id,
            verified_name or display_phone, body.waba_id, metadata,
        )
        log.info("[channels] nuevo canal | workspace=%s | phone=%s", workspace_id, display_phone)

    if not row:
        raise HTTPException(status_code=500, detail="Error guardando canal en la base de datos.")
    return dict(row)


# ── Calendarios Google ────────────────────────────────────────────────────────

@router.get(
    "/workspaces/{workspace_id}/calendars",
    response_model=list[CalendarOut],
    summary="Listar calendarios conectados",
    dependencies=[Depends(require_workspace_access("viewer"))],
)
async def list_calendars(
    workspace_id: str,
    db: asyncpg.Connection = Depends(get_db),
):
    # Principio VII: NO retornar oauth_refresh_token_encrypted
    rows = await db.fetch(
        """
        SELECT id, workspace_id, name, google_calendar_id, connected_by_user_id,
               sync_enabled, sync_status, last_synced_at, created_at, updated_at
        FROM calendars
        WHERE workspace_id = $1
        """,
        workspace_id,
    )
    return [dict(r) for r in rows]


@router.post(
    "/workspaces/{workspace_id}/calendars",
    response_model=CalendarOut,
    status_code=201,
    summary="Conectar Google Calendar con OAuth",
    dependencies=[Depends(require_workspace_access("workspace_owner"))],
)
async def connect_calendar(
    workspace_id: str,
    body: CalendarCreate,
    current_user: dict = Depends(require_workspace_access("workspace_owner")),
    db: asyncpg.Connection = Depends(get_db),
):
    from integrations.google_calendar import exchange_oauth_code

    token = await exchange_oauth_code(body.oauth_code)
    if not token:
        raise HTTPException(status_code=400, detail="Error intercambiando código OAuth con Google.")

    row = await db.fetchrow(
        """
        INSERT INTO calendars
            (workspace_id, name, google_calendar_id, connected_by_user_id,
             oauth_refresh_token_encrypted, sync_enabled, sync_status)
        VALUES ($1,$2,$3,$4,$5,TRUE,'active')
        RETURNING id, workspace_id, name, google_calendar_id, connected_by_user_id,
                  sync_enabled, sync_status, last_synced_at, created_at, updated_at
        """,
        workspace_id,
        body.name,
        body.google_calendar_id,
        current_user.get("sub"),
        token["encrypted_refresh_token"],
    )
    if not row:
        raise HTTPException(status_code=500, detail="Error guardando calendario.")

    log.info("[calendars] connected | workspace=%s | cal=%s", workspace_id, body.google_calendar_id)
    return dict(row)


@router.delete(
    "/workspaces/{workspace_id}/calendars/{calendar_id}",
    status_code=204,
    summary="Desconectar calendario.",
    dependencies=[Depends(require_workspace_access("workspace_owner"))],
)
async def disconnect_calendar(
    workspace_id: str,
    calendar_id: str,
    current_user: dict = Depends(require_workspace_access("workspace_owner")),
    db: asyncpg.Connection = Depends(get_db),
):
    await db.execute(
        "UPDATE calendars SET sync_enabled=FALSE, sync_status='disconnected' WHERE id=$1 AND workspace_id=$2",
        calendar_id, workspace_id,
    )
    log.info("[calendars] disconnected | workspace=%s | cal=%s | by=%s",
             workspace_id, calendar_id, current_user.get("sub"))
