"""Seguimiento por WhatsApp: ajustes del negocio, plantillas en su cuenta de WhatsApp y envío.

El envío es de «una sola vez»: antes de mandar nada se reclama la fila en followup_sends
(índices únicos por cita y por venta), así un reinicio del worker no repite mensajes.
"""
import logging
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.database import AsyncSessionLocal
from schemas.followups import FollowupSettings
from services import followup_templates as ft
from services.whatsapp_provider import KapsoProvider, ProviderError

log = logging.getLogger(__name__)

_SETTINGS_COLUMNS = ", ".join(FollowupSettings.model_fields)
_STATUS_FROM_META = {"APPROVED": "approved", "PENDING": "pending", "REJECTED": "rejected", "DISABLED": "disabled"}
# Errores pasajeros: se libera el envío para reintentar en la siguiente pasada del worker.
_TRANSIENT = ("timeout", "network_error", "http_429", "http_500", "http_502", "http_503", "http_504")
# Estados de Meta en los que el número no puede enviar. Kapso solo documenta "CONNECTED"; el resto
# (FLAGGED, RESTRICTED...) se deja pasar porque el número sigue operando.
_DISCONNECTED_STATES = frozenset({"DISCONNECTED", "DELETED", "BANNED", "MIGRATED"})


def _provider() -> KapsoProvider:
    s = get_settings()
    return KapsoProvider(s.kapso_api_key, s.kapso_base_url)


def _is_sandbox(phone_number_id: Optional[str]) -> bool:
    return bool(phone_number_id) and str(phone_number_id) == get_settings().kapso_sandbox_phone_number_id


# ── Ajustes ───────────────────────────────────────────────────────────────────

async def get_followup_settings(db: AsyncSession, workspace_id: str) -> dict:
    """Ajustes del negocio; si nunca los guardó, los valores por defecto."""
    row = (await db.execute(
        text(f"SELECT {_SETTINGS_COLUMNS} FROM followup_settings WHERE workspace_id = :w"), {"w": workspace_id},
    )).mappings().fetchone()
    return dict(row) if row else FollowupSettings().model_dump()


async def update_followup_settings(db: AsyncSession, workspace_id: str, body: FollowupSettings) -> dict:
    """Guarda los ajustes completos del negocio."""
    data = body.model_dump()
    columns = list(data)
    await db.execute(
        text(f"""
            INSERT INTO followup_settings (workspace_id, {", ".join(columns)})
            VALUES (:w, {", ".join(":" + c for c in columns)})
            ON CONFLICT (workspace_id) DO UPDATE SET
                {", ".join(f"{c} = EXCLUDED.{c}" for c in columns)}, updated_at = NOW()
        """),
        {"w": workspace_id, **data},
    )
    await db.commit()
    return data


# ── Plantillas ────────────────────────────────────────────────────────────────

async def _kapso_channel(db: AsyncSession, workspace_id: str) -> Optional[dict]:
    row = (await db.execute(
        text("""
            SELECT id, phone_number_id, provider, external_account_id FROM channels
            WHERE workspace_id = :w AND status = 'active' AND phone_number_id IS NOT NULL
            ORDER BY (provider = 'kapso') DESC, created_at LIMIT 1
        """),
        {"w": workspace_id},
    )).mappings().fetchone()
    return dict(row) if row else None


def _blocked_reason(channel: Optional[dict]) -> Optional[str]:
    """Por qué este negocio no puede usar plantillas todavía; None si puede."""
    if not channel:
        return "Conecta primero el número de WhatsApp del negocio."
    if channel["provider"] != "kapso":
        return "Las plantillas solo están disponibles en números conectados por Kapso."
    if _is_sandbox(channel["phone_number_id"]):
        return ("El número de pruebas no admite plantillas: los seguimientos se envían como texto "
                "y solo llegan si el cliente escribió en las últimas 24 horas.")
    return None


async def list_templates(db: AsyncSession, workspace_id: str) -> dict:
    """Las cuatro plantillas con el estado que tienen en la cuenta de WhatsApp del negocio."""
    rows = (await db.execute(
        text("SELECT kind, status, detail, synced_at FROM followup_templates WHERE workspace_id = :w"),
        {"w": workspace_id},
    )).mappings().fetchall()
    by_kind = {r["kind"]: r for r in rows}
    channel = await _kapso_channel(db, workspace_id)
    reason = _blocked_reason(channel)
    templates = []
    for kind in ft.KINDS:
        tpl, row = ft.TEMPLATES[kind], by_kind.get(kind)
        templates.append({
            "kind": kind, "name": tpl.name, "category": tpl.category, "body": tpl.body,
            "buttons": [label for label, _ in tpl.buttons],
            "status": row["status"] if row else "not_created",
            "detail": row["detail"] if row else None,
            "synced_at": row["synced_at"] if row else None,
        })
    return {"connected": channel is not None, "can_activate": reason is None, "reason": reason,
            "templates": templates}


def _platform_client():
    from services.kapso_onboarding import KapsoPlatformClient
    s = get_settings()
    return KapsoPlatformClient(s.kapso_api_key, s.kapso_base_url)


async def _verify_connection(db: AsyncSession, channel: dict) -> str:
    """Comprueba en Kapso que el número sigue conectado y devuelve el ID de su cuenta de WhatsApp.

    La tabla `channels` solo sabe lo que pasó al conectar; un número retirado después seguiría
    figurando activo. De paso guarda la cuenta y si el número está en coexistencia.
    """
    from services.kapso_onboarding import KapsoError
    not_connected = HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Este número ya no está conectado en Kapso. Vuelve a conectar WhatsApp.")
    unavailable = HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="No se pudo consultar la cuenta de WhatsApp del número. Intenta de nuevo.")
    try:
        number = await _platform_client().get_phone_number(channel["phone_number_id"])
    except KapsoError as e:
        log.error("[followups] no se pudo consultar el número en Kapso | err=%s", e)
        raise (not_connected if str(e) == "http_404" else unavailable) from None

    state = str(number.get("status") or "").upper()
    if state in _DISCONNECTED_STATES:
        log.warning("[followups] número no conectado | channel=%s | status=%s", channel["id"], state)
        raise not_connected
    waba = number.get("business_account_id")
    if not waba:
        raise unavailable

    coexistence = number.get("is_coexistence")
    await db.execute(
        text("""
            UPDATE channels SET external_account_id = :waba,
                coexistence_enabled = COALESCE(:coex, coexistence_enabled),
                connection_type = COALESCE(:conn_type, connection_type),
                updated_at = NOW()
            WHERE id = :id
        """),
        {"waba": str(waba), "id": channel["id"],
         "coex": coexistence if isinstance(coexistence, bool) else None,
         "conn_type": ("coexistence" if coexistence else "dedicated") if isinstance(coexistence, bool) else None},
    )
    return str(waba)


async def sync_templates(db: AsyncSession, workspace_id: str, create_missing: bool) -> dict:
    """Lee el estado de las plantillas en Meta y, si `create_missing`, envía a revisión las que falten.

    Idempotente: una plantilla que ya existe con ese nombre no se vuelve a crear.
    """
    channel = await _kapso_channel(db, workspace_id)
    reason = _blocked_reason(channel)
    if reason:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=reason)
    waba = await _verify_connection(db, channel)
    provider = _provider()
    try:
        existing = {t.get("name"): t for t in await provider.list_templates(waba) if isinstance(t, dict)}
    except ProviderError as e:
        log.error("[followups] no se pudieron listar plantillas | workspace=%s | err=%s", workspace_id, e.error)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="WhatsApp no respondió al consultar las plantillas. Intenta de nuevo.")

    for kind in ft.KINDS:
        tpl = ft.TEMPLATES[kind]
        found = existing.get(tpl.name)
        detail = None
        if found:
            state = _STATUS_FROM_META.get(str(found.get("status", "")).upper(), "pending")
        elif create_missing:
            try:
                created = await provider.create_template(waba, tpl.definition())
                state = _STATUS_FROM_META.get(str(created.get("status", "")).upper(), "pending")
            except ProviderError as e:
                log.error("[followups] no se pudo crear plantilla | workspace=%s | kind=%s | err=%s code=%s",
                          workspace_id, kind, e.error, e.code)
                state, detail = "error", f"WhatsApp rechazó la solicitud ({e.code or e.error})."
        else:
            continue
        await db.execute(
            text("""
                INSERT INTO followup_templates (workspace_id, kind, template_name, language, status, detail, synced_at)
                VALUES (:w, :kind, :name, :lang, :status, :detail, NOW())
                ON CONFLICT (workspace_id, kind) DO UPDATE SET
                    template_name = EXCLUDED.template_name, language = EXCLUDED.language,
                    status = EXCLUDED.status, detail = EXCLUDED.detail, synced_at = NOW(), updated_at = NOW()
            """),
            {"w": workspace_id, "kind": kind, "name": tpl.name, "lang": ft.LANGUAGE,
             "status": state, "detail": detail},
        )
    await db.commit()
    return await list_templates(db, workspace_id)


async def list_sends(db: AsyncSession, workspace_id: str, limit: int = 50) -> list[dict]:
    """Últimos seguimientos enviados, más recientes primero."""
    rows = (await db.execute(
        text("""
            SELECT fs.id, fs.kind, c.name AS customer_name, fs.status, fs.via, fs.error, fs.created_at
            FROM followup_sends fs LEFT JOIN customers c ON c.id = fs.customer_id
            WHERE fs.workspace_id = :w ORDER BY fs.created_at DESC LIMIT :limit
        """),
        {"w": workspace_id, "limit": limit},
    )).mappings().fetchall()
    return [dict(r) for r in rows]


# ── Envío ─────────────────────────────────────────────────────────────────────

async def _claim(kind: str, workspace_id: str, customer_id: str,
                 appointment_id: Optional[str], sales_order_id: Optional[str]) -> Optional[str]:
    """Reserva el envío. None si ya existía (otro proceso o una pasada anterior lo tomó)."""
    async with AsyncSessionLocal() as db:
        try:
            send_id = (await db.execute(
                text("""
                    INSERT INTO followup_sends (workspace_id, kind, customer_id, appointment_id, sales_order_id)
                    VALUES (:w, :kind, :c, :a, :o) RETURNING id
                """),
                {"w": workspace_id, "kind": kind, "c": customer_id, "a": appointment_id, "o": sales_order_id},
            )).scalar_one()
            await db.commit()
            return str(send_id)
        except IntegrityError:
            await db.rollback()
            return None


async def _finish(send_id: str, *, state: Optional[str], via: Optional[str] = None,
                  error: Optional[str] = None, message_id: Optional[str] = None) -> None:
    """Cierra el envío; con state=None lo libera para que se reintente."""
    async with AsyncSessionLocal() as db:
        if state is None:
            await db.execute(text("DELETE FROM followup_sends WHERE id = :id"), {"id": send_id})
        else:
            await db.execute(
                text("""UPDATE followup_sends SET status = :s, via = :via, error = :e, provider_message_id = :m
                        WHERE id = :id"""),
                {"s": state, "via": via, "e": error, "m": message_id, "id": send_id},
            )
        await db.commit()


async def send_followup(
    kind: str, workspace_id: str, customer_id: str, phone: str, values: dict, *,
    appointment_id: Optional[str] = None, sales_order_id: Optional[str] = None,
) -> str:
    """Envía un seguimiento una sola vez. Devuelve 'sent' | 'failed' | 'skipped' | 'duplicate'.

    Con plantilla aprobada se envía como plantilla (llega aunque el cliente no haya escrito hace
    más de 24 h). En el número de pruebas, o en un canal que no es Kapso, se envía el mismo texto
    como mensaje libre. Si la plantilla aún no está aprobada no se envía nada y se reintenta luego.
    """
    tpl = ft.TEMPLATES[kind]
    async with AsyncSessionLocal() as db:
        channel = await _kapso_channel(db, workspace_id)
        approved = (await db.execute(
            text("SELECT 1 FROM followup_templates WHERE workspace_id = :w AND kind = :k AND status = 'approved'"),
            {"w": workspace_id, "k": kind},
        )).scalar_one_or_none()
    if not channel:
        return "skipped"
    as_text = channel["provider"] != "kapso" or _is_sandbox(channel["phone_number_id"])
    if not as_text and not approved:
        return "skipped"

    send_id = await _claim(kind, workspace_id, customer_id, appointment_id, sales_order_id)
    if not send_id:
        return "duplicate"

    body = tpl.render(values)
    try:
        if as_text:
            from services.whatsapp_service import WhatsAppService
            result = await WhatsAppService.send_text(
                to=phone, text=body, phone_number_id=channel["phone_number_id"], provider=channel["provider"])
        else:
            result = await _provider().send_template(
                to=phone, phone_number_id=channel["phone_number_id"], name=tpl.name, language=ft.LANGUAGE,
                body_params=tpl.body_params(values), button_payloads=tpl.button_payloads(appointment_id or ""),
            )
    except Exception as e:  # nunca dejar el envío en 'sending'
        log.error("[followups] error enviando | kind=%s | err=%s", kind, type(e).__name__)
        await _finish(send_id, state=None)
        return "failed"

    via = "text" if as_text else "template"
    if not result.ok:
        if result.code == "marketing_preference_stopped":
            await set_marketing_opt_out(workspace_id, customer_id)
        transient = result.error in _TRANSIENT
        await _finish(send_id, state=None if transient else "failed", via=via,
                      error=(result.code or result.error)[:200])
        log.warning("[followups] no enviado | kind=%s | workspace=%s | err=%s code=%s",
                    kind, workspace_id, result.error, result.code)
        return "failed"

    await _finish(send_id, state="sent", via=via, message_id=result.message_id or None)
    await _save_outbound(workspace_id, phone, channel["phone_number_id"], body, tpl, result.message_id)
    log.info("[followups] enviado | kind=%s | workspace=%s | via=%s", kind, workspace_id, via)
    return "sent"


async def _save_outbound(workspace_id: str, phone: str, phone_number_id: str, body: str,
                         tpl: ft.FollowupTemplate, message_id: str) -> None:
    """Guarda el mensaje en la conversación para que el panel y el agente vean qué se le dijo al cliente."""
    from services.conversation_service import ConversationService
    try:
        conversation = await ConversationService.find_or_create(customer_phone=phone, phone_number_id=phone_number_id)
        content = body + ("\n[Botones: " + " / ".join(label for label, _ in tpl.buttons) + "]" if tpl.buttons else "")
        await ConversationService.save_message(
            conversation_id=conversation["id"], workspace_id=workspace_id,
            channel_id=conversation["channel_id"], customer_id=conversation.get("customer_id"),
            direction="outbound", sender_type="system", content=content,
            message_type="template", provider_message_id=message_id or None,
        )
    except Exception as e:  # el mensaje ya salió; no se pierde el envío por un fallo al registrarlo
        log.error("[followups] no se pudo guardar el mensaje enviado | err=%s", type(e).__name__)


async def set_marketing_opt_out(workspace_id: str, customer_id: str) -> None:
    """El cliente no quiere más mensajes promocionales (reactivación)."""
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("UPDATE customers SET marketing_opt_out = TRUE, updated_at = NOW() WHERE id = :c AND workspace_id = :w"),
            {"c": customer_id, "w": workspace_id},
        )
        await db.commit()


async def confirm_appointment(workspace_id: str, customer_id: str, appointment_id: str) -> Optional[dict]:
    """Marca que el cliente confirmó su cita desde el recordatorio. None si la cita no es suya o ya no aplica."""
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            text("""
                UPDATE appointments SET confirmed_by_customer_at = COALESCE(confirmed_by_customer_at, NOW()),
                       updated_at = NOW()
                WHERE id = CAST(:a AS uuid) AND workspace_id = :w AND customer_id = :c
                  AND status IN ('pending','confirmed') AND start_at > NOW()
                RETURNING id, start_at
            """),
            {"a": appointment_id, "w": workspace_id, "c": customer_id},
        )).mappings().fetchone()
        await db.commit()
    return dict(row) if row else None
