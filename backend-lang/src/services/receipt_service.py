"""Comprobantes de pago recibidos por WhatsApp.

Flujo: el cliente envía la imagen → se descarga, se valida por la firma del archivo, se guarda en
UPLOADS_DIR y se lee con receipt_ocr → queda `pending`. Nada se cobra solo: un manager lo aprueba
(registra el cobro en la venta y adjunta el archivo al movimiento) o lo rechaza.
"""
import logging
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.database import AsyncSessionLocal
from schemas.accounting import PaymentCreate
from schemas.receipts import ReceiptApprove
from services import attachment_service, receipt_ocr, sales_service
from services.whatsapp_provider import KapsoProvider, ProviderError

log = logging.getLogger(__name__)

_SELECT = """
    SELECT r.id, r.customer_id, c.name AS customer_name, c.phone AS customer_phone, r.content_type,
           r.size_bytes, r.amount_cop, r.paid_on, r.method, r.reference, r.bank, r.payer_name, r.status,
           r.sales_order_id, r.movement_id, r.reject_reason, r.reviewed_at, r.created_at
    FROM payment_receipts r LEFT JOIN customers c ON c.id = r.customer_id
"""
_FILE_NAMES = {"image/jpeg": "comprobante-whatsapp.jpg", "image/png": "comprobante-whatsapp.png",
               "image/webp": "comprobante-whatsapp.webp", "application/pdf": "comprobante-whatsapp.pdf"}


# ── Recepción (webhook, fuera del ciclo de request) ───────────────────────────

async def ingest(
    *, workspace_id: str, customer_id: Optional[str], conversation_id: Optional[str],
    message_id: Optional[str], media_id: str, phone_number_id: str, provider: Optional[KapsoProvider] = None,
    llm=None,
) -> dict:
    """Descarga, valida, lee y guarda un archivo enviado por el cliente.

    Devuelve {"outcome": ..., "amount_cop": int|None}; outcome es
    'receipt' (guardado, pendiente de revisión), 'not_receipt', 'unsupported', 'too_large' o 'error'.
    """
    if provider is None:
        s = get_settings()
        provider = KapsoProvider(s.kapso_api_key, s.kapso_base_url)
    try:
        data = await provider.download_media(media_id, phone_number_id, attachment_service.MAX_BYTES)
    except ProviderError as e:
        if e.error == "too_large":
            return {"outcome": "too_large", "amount_cop": None}
        log.error("[receipts] no se pudo descargar el archivo | workspace=%s | err=%s", workspace_id, e.error)
        return {"outcome": "error", "amount_cop": None}

    content_type = attachment_service.detect_content_type(data) if data else None
    if not content_type:
        return {"outcome": "unsupported", "amount_cop": None}

    read = await receipt_ocr.extract(data, content_type, llm=llm)
    if read is not None and not read.is_receipt:
        return {"outcome": "not_receipt", "amount_cop": None}
    # read is None: PDF o fallo del lector → se guarda igual para que el negocio lo revise a mano.

    storage_key = await attachment_service.store_file(workspace_id, data, content_type, folder="receipts")
    fields = read.model_dump() if read else {}
    try:
        async with AsyncSessionLocal() as db:
            inserted = (await db.execute(
                text("""
                    INSERT INTO payment_receipts (workspace_id, customer_id, conversation_id, message_id,
                        storage_key, content_type, size_bytes, amount_cop, paid_on, method, reference,
                        bank, payer_name, raw)
                    VALUES (:w, :c, :conv, :msg, :key, :ctype, :size, :amount, :paid_on, :method,
                            :reference, :bank, :payer, CAST(:raw AS jsonb))
                    ON CONFLICT (message_id) WHERE message_id IS NOT NULL DO NOTHING
                    RETURNING id
                """),
                {"w": workspace_id, "c": customer_id, "conv": conversation_id, "msg": message_id,
                 "key": storage_key, "ctype": content_type, "size": len(data),
                 "amount": fields.get("amount_cop"), "paid_on": fields.get("paid_on"),
                 "method": fields.get("method"), "reference": fields.get("reference"),
                 "bank": fields.get("bank"), "payer": fields.get("payer_name"),
                 "raw": read.model_dump_json() if read else "{}"},
            )).scalar_one_or_none()
            await db.commit()
    except Exception:
        attachment_service.remove_file(storage_key)  # no dejar archivos huérfanos si la BD falla
        raise
    if inserted is None:  # reintento del webhook: ya estaba guardado
        attachment_service.remove_file(storage_key)
    log.info("[receipts] comprobante recibido | workspace=%s | leido=%s", workspace_id, read is not None)
    return {"outcome": "receipt", "amount_cop": fields.get("amount_cop")}


# ── Consulta ──────────────────────────────────────────────────────────────────

async def list_receipts(db: AsyncSession, workspace_id: str, status_filter: Optional[str], limit: int = 100) -> list[dict]:
    """Comprobantes del negocio, más recientes primero."""
    where = "r.workspace_id = :w" + (" AND r.status = :status" if status_filter else "")
    params: dict = {"w": workspace_id, "limit": limit}
    if status_filter:
        params["status"] = status_filter
    rows = (await db.execute(
        text(f"{_SELECT} WHERE {where} ORDER BY r.created_at DESC LIMIT :limit"), params,
    )).mappings().fetchall()
    return [dict(r) for r in rows]


async def count_pending(db: AsyncSession, workspace_id: str) -> int:
    """Cuántos comprobantes esperan revisión."""
    return (await db.execute(
        text("SELECT COUNT(*) FROM payment_receipts WHERE workspace_id = :w AND status = 'pending'"),
        {"w": workspace_id},
    )).scalar_one()


async def _get(db: AsyncSession, workspace_id: str, receipt_id: str) -> dict:
    row = (await db.execute(
        text(f"{_SELECT} WHERE r.id = :id AND r.workspace_id = :w"), {"id": receipt_id, "w": workspace_id},
    )).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comprobante no encontrado.")
    return dict(row)


async def get_receipt(db: AsyncSession, workspace_id: str, receipt_id: str) -> dict:
    """Comprobante + ventas abiertas a las que se puede aplicar (primero las del cliente que lo envió)."""
    receipt = await _get(db, workspace_id, receipt_id)
    rows = (await db.execute(
        text("""
            SELECT o.id, o.number, tp.name AS third_party_name, o.issued_at, o.total_cop,
                   o.total_cop - COALESCE((SELECT SUM(m.amount_cop) FROM movements m
                        WHERE m.sales_order_id = o.id AND m.voided_at IS NULL), 0) AS balance_cop,
                   (SELECT l.description FROM sales_order_lines l WHERE l.order_id = o.id
                    ORDER BY l.created_at LIMIT 1) AS description,
                   COALESCE(tp.customer_id = CAST(:c AS uuid), FALSE) AS is_customer
            FROM sales_orders o LEFT JOIN third_parties tp ON tp.id = o.third_party_id
            WHERE o.workspace_id = :w AND o.status = 'open'
            ORDER BY is_customer DESC, o.issued_at DESC LIMIT 50
        """),
        {"w": workspace_id, "c": receipt["customer_id"]},
    )).mappings().fetchall()
    orders = [dict(r) for r in rows if r["balance_cop"] > 0]
    own = [o for o in orders if o["is_customer"]]
    exact = [o for o in own if receipt["amount_cop"] and o["balance_cop"] == receipt["amount_cop"]]
    suggested = exact[0] if exact else (own[0] if len(own) == 1 else None)
    receipt["orders"] = orders
    receipt["suggested_order_id"] = suggested["id"] if suggested else None
    return receipt


async def get_file(db: AsyncSession, workspace_id: str, receipt_id: str):
    """Metadato + ruta en disco del archivo. 404 si no existe o falta en disco."""
    row = (await db.execute(
        text("SELECT id, content_type, storage_key FROM payment_receipts WHERE id = :id AND workspace_id = :w"),
        {"id": receipt_id, "w": workspace_id},
    )).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comprobante no encontrado.")
    path = attachment_service.resolve_path(row["storage_key"])
    if not path.is_file():
        log.error("[receipts] archivo ausente en disco | receipt=%s", receipt_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El archivo ya no está disponible.")
    return dict(row), path


# ── Revisión ──────────────────────────────────────────────────────────────────

async def approve(
    db: AsyncSession, workspace_id: str, receipt_id: str, body: ReceiptApprove, user_id: Optional[str]
) -> dict:
    """Aprueba el comprobante: registra el cobro en la venta elegida y adjunta el archivo a ese movimiento.

    El cambio de estado y el cobro van en la misma transacción (register_payment hace el commit):
    si el cobro falla (orden cerrada, monto mayor al saldo) el comprobante sigue pendiente.
    """
    order_id = str(body.sales_order_id)
    claimed = (await db.execute(
        text("""
            UPDATE payment_receipts
            SET status = 'approved', reviewed_by = :by, reviewed_at = NOW(), sales_order_id = :order
            WHERE id = :id AND workspace_id = :w AND status = 'pending'
            RETURNING storage_key, content_type
        """),
        {"id": receipt_id, "w": workspace_id, "by": user_id, "order": order_id},
    )).mappings().fetchone()
    if not claimed:
        await db.rollback()
        await _get(db, workspace_id, receipt_id)  # 404 si no existe
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Este comprobante ya fue revisado.")
    try:
        order = await sales_service.register_payment(
            db, workspace_id, order_id,
            PaymentCreate(amount_cop=body.amount_cop, method=body.method, occurred_on=body.occurred_on), user_id,
        )
    except Exception:
        await db.rollback()
        raise

    movement_id = order["movement_id"]
    await db.execute(
        text("UPDATE payment_receipts SET movement_id = :m WHERE id = :id"), {"m": movement_id, "id": receipt_id},
    )
    await db.commit()
    try:  # el cobro ya quedó registrado: si adjuntar falla, no se revierte
        data = await attachment_service.read_file(claimed["storage_key"])
        await attachment_service.save_attachment(
            db, workspace_id, movement_id, _FILE_NAMES[claimed["content_type"]], data, user_id)
    except Exception as e:
        await db.rollback()
        log.error("[receipts] cobro registrado pero no se pudo adjuntar el archivo | receipt=%s | err=%s",
                  receipt_id, type(e).__name__)
    log.info("[receipts] aprobado | workspace=%s | receipt=%s | order=%s", workspace_id, receipt_id, order_id)
    return await _get(db, workspace_id, receipt_id)


async def reject(db: AsyncSession, workspace_id: str, receipt_id: str, reason: Optional[str],
                 user_id: Optional[str]) -> dict:
    """Rechaza un comprobante pendiente. El archivo se conserva como registro."""
    updated = (await db.execute(
        text("""
            UPDATE payment_receipts SET status = 'rejected', reviewed_by = :by, reviewed_at = NOW(),
                   reject_reason = :reason
            WHERE id = :id AND workspace_id = :w AND status = 'pending' RETURNING id
        """),
        {"id": receipt_id, "w": workspace_id, "by": user_id, "reason": (reason or "").strip() or None},
    )).scalar_one_or_none()
    await db.commit()
    if not updated:
        await _get(db, workspace_id, receipt_id)  # 404 si no existe
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Este comprobante ya fue revisado.")
    return await _get(db, workspace_id, receipt_id)
