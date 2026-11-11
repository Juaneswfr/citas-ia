"""
Router /workspaces/{workspace_id}/accounting/receipts — Comprobantes de pago recibidos por WhatsApp.

El cliente los envía por el chat; aquí el negocio los revisa: aprobar registra el cobro en una venta,
rechazar los descarta. Solo owner/manager. La descarga exige el JWT (no hay URLs públicas).
Rechazar exige confirmed=true (Principio IX).
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import require_workspace_access
from schemas.receipts import (
    ReceiptApprove, ReceiptCountOut, ReceiptDetailOut, ReceiptOut, ReceiptReject, ReceiptStatus,
)
from services import receipt_service
from services.audit_service import AuditService

router = APIRouter(tags=["accounting"])
_manager = require_workspace_access("manager")
_BASE = "/workspaces/{workspace_id}/accounting/receipts"


@router.get(_BASE, response_model=list[ReceiptOut], summary="Listar comprobantes recibidos")
async def list_receipts(
    workspace_id: str, status_filter: Optional[ReceiptStatus] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=200),
    _user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    return await receipt_service.list_receipts(db, workspace_id, status_filter, limit)


@router.get(f"{_BASE}/count", response_model=ReceiptCountOut, summary="Comprobantes pendientes de revisión")
async def count_receipts(workspace_id: str, _user: dict = Depends(_manager), db: AsyncSession = Depends(get_db)):
    return {"pending": await receipt_service.count_pending(db, workspace_id)}


@router.get(f"{_BASE}/{{receipt_id}}", response_model=ReceiptDetailOut,
            summary="Comprobante con las ventas abiertas a las que se puede aplicar")
async def get_receipt(
    workspace_id: str, receipt_id: str, _user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    return await receipt_service.get_receipt(db, workspace_id, receipt_id)


@router.get(f"{_BASE}/{{receipt_id}}/file", summary="Ver el archivo del comprobante")
async def download_receipt(
    workspace_id: str, receipt_id: str, _user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    meta, path = await receipt_service.get_file(db, workspace_id, receipt_id)
    return FileResponse(
        path, media_type=meta["content_type"], content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=300"},
    )


@router.post(f"{_BASE}/{{receipt_id}}/approve", response_model=ReceiptOut,
             summary="Aprobar: registra el cobro en la venta y adjunta el comprobante")
async def approve_receipt(
    workspace_id: str, receipt_id: str, body: ReceiptApprove,
    user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    receipt = await receipt_service.approve(db, workspace_id, receipt_id, body, user.get("sub"))
    await AuditService.log(
        workspace_id=workspace_id, actor_user_id=user.get("sub"), action="receipt.approve",
        entity_type="payment_receipt", entity_id=receipt_id,
        after_data={"sales_order_id": str(body.sales_order_id), "amount_cop": body.amount_cop,
                    "method": body.method, "movement_id": receipt.get("movement_id")},
    )
    return receipt


@router.post(f"{_BASE}/{{receipt_id}}/reject", response_model=ReceiptOut, summary="Rechazar comprobante")
async def reject_receipt(
    workspace_id: str, receipt_id: str, body: ReceiptReject, confirmed: bool = Query(False),
    user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    if not confirmed:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Esta acción requiere confirmación explícita. Pasa confirmed=true.")
    receipt = await receipt_service.reject(db, workspace_id, receipt_id, body.reason, user.get("sub"))
    await AuditService.log(
        workspace_id=workspace_id, actor_user_id=user.get("sub"), action="receipt.reject",
        entity_type="payment_receipt", entity_id=receipt_id,
    )
    return receipt
