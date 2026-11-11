"""
Router /workspaces/{workspace_id}/accounting — Finanzas simples del negocio.

Terceros, órdenes de venta/compra, movimientos de caja, regla de pago y liquidaciones de
barberos, y reportes. Solo owner/manager (staff y viewer no ven finanzas).
Las rutas solo validan entrada y delegan en `services/`; la lógica vive allí.
Anular algo requiere confirmación explícita (Principio IX).
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import require_workspace_access
from schemas.accounting import (
    CategoryCreate, CategoryOut, CommissionRow, CompensationOut, CompensationUpsert,
    FlowKind, MovementCreate, MovementOut, PaymentCreate, PayoutCreate, PayoutOut, PayoutPay,
    PurchaseOrderCreate, PurchaseOrderOut, SalesOrderCreate, SalesOrderOut, SummaryOut,
    ThirdPartyCreate, ThirdPartyKind, ThirdPartyOut, ThirdPartyUpdate,
)
from services import (
    movement_service, payout_service, purchase_service, report_service, sales_service,
    third_party_service,
)
from services.audit_service import AuditService

router = APIRouter(tags=["accounting"])
_manager = require_workspace_access("manager")
_BASE = "/workspaces/{workspace_id}/accounting"


def _require_confirmed(confirmed: bool) -> None:
    if not confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Esta acción requiere confirmación explícita. Pasa confirmed=true.",
        )


async def _audit(workspace_id: str, user: dict, action: str, entity: str, entity_id: str, after: dict) -> None:
    """Registra en audit_logs solo datos simples (ids y montos), nunca PII."""
    await AuditService.log(
        workspace_id=workspace_id, actor_user_id=user.get("sub"), action=action,
        entity_type=entity, entity_id=entity_id, after_data=after,
    )


# ── Terceros y categorías ─────────────────────────────────────────────────────

@router.get(f"{_BASE}/third-parties", response_model=list[ThirdPartyOut], summary="Listar terceros")
async def list_third_parties(
    workspace_id: str, kind: Optional[ThirdPartyKind] = Query(None), active_only: bool = Query(True),
    _user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    return await third_party_service.list_third_parties(db, workspace_id, kind, active_only)


@router.post(f"{_BASE}/third-parties", response_model=ThirdPartyOut, status_code=201, summary="Crear tercero")
async def create_third_party(
    workspace_id: str, body: ThirdPartyCreate, user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    row = await third_party_service.create_third_party(db, workspace_id, body)
    await _audit(workspace_id, user, "third_party.create", "third_party", row["id"], {"kind": row["kind"]})
    return row


@router.patch(f"{_BASE}/third-parties/{{third_party_id}}", response_model=ThirdPartyOut, summary="Editar tercero")
async def update_third_party(
    workspace_id: str, third_party_id: str, body: ThirdPartyUpdate,
    user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    row = await third_party_service.update_third_party(db, workspace_id, third_party_id, body)
    await _audit(workspace_id, user, "third_party.update", "third_party", third_party_id, {})
    return row


@router.get(f"{_BASE}/categories", response_model=list[CategoryOut], summary="Listar categorías")
async def list_categories(
    workspace_id: str, kind: Optional[FlowKind] = Query(None),
    _user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    return await third_party_service.list_categories(db, workspace_id, kind)


@router.post(f"{_BASE}/categories", response_model=CategoryOut, status_code=201, summary="Crear categoría")
async def create_category(
    workspace_id: str, body: CategoryCreate, _user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    return await third_party_service.create_category(db, workspace_id, body)


# ── Órdenes de venta ──────────────────────────────────────────────────────────

@router.get(f"{_BASE}/sales-orders", response_model=list[SalesOrderOut], summary="Listar órdenes de venta")
async def list_sales_orders(
    workspace_id: str, order_status: Optional[str] = Query(None, alias="status", pattern="^(open|paid|void)$"),
    from_date: Optional[date] = Query(None), to_date: Optional[date] = Query(None),
    limit: int = Query(100, ge=1, le=500), _user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    return await sales_service.list_orders(db, workspace_id, order_status, from_date, to_date, limit)


@router.get(f"{_BASE}/sales-orders/by-appointment/{{appointment_id}}", response_model=Optional[SalesOrderOut],
            summary="Venta de una cita (null si la cita aún no se completó)")
async def get_sales_order_by_appointment(
    workspace_id: str, appointment_id: str, _user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    return await sales_service.get_order_by_appointment(db, workspace_id, appointment_id)


@router.get(f"{_BASE}/sales-orders/{{order_id}}", response_model=SalesOrderOut, summary="Detalle de venta")
async def get_sales_order(
    workspace_id: str, order_id: str, _user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    return await sales_service.get_order(db, workspace_id, order_id)


@router.post(f"{_BASE}/sales-orders", response_model=SalesOrderOut, status_code=201, summary="Crear venta manual")
async def create_sales_order(
    workspace_id: str, body: SalesOrderCreate, user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    order = await sales_service.create_order(db, workspace_id, body, user.get("sub"))
    await _audit(workspace_id, user, "sales_order.create", "sales_order", order["id"], {"total_cop": order["total_cop"]})
    return order


@router.post(f"{_BASE}/sales-orders/{{order_id}}/payments", response_model=SalesOrderOut, summary="Cobrar venta")
async def pay_sales_order(
    workspace_id: str, order_id: str, body: PaymentCreate,
    user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    order = await sales_service.register_payment(db, workspace_id, order_id, body, user.get("sub"))
    await _audit(workspace_id, user, "sales_order.payment", "sales_order", order_id, {"amount_cop": body.amount_cop})
    return order


@router.post(f"{_BASE}/sales-orders/{{order_id}}/void", response_model=SalesOrderOut, summary="Anular venta")
async def void_sales_order(
    workspace_id: str, order_id: str, confirmed: bool = Query(False),
    user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    _require_confirmed(confirmed)
    order = await sales_service.void_order(db, workspace_id, order_id)
    await _audit(workspace_id, user, "sales_order.void", "sales_order", order_id, {})
    return order


# ── Órdenes de compra ─────────────────────────────────────────────────────────

@router.get(f"{_BASE}/purchase-orders", response_model=list[PurchaseOrderOut], summary="Listar órdenes de compra")
async def list_purchase_orders(
    workspace_id: str, order_status: Optional[str] = Query(None, alias="status", pattern="^(open|paid|void)$"),
    limit: int = Query(100, ge=1, le=500), _user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    return await purchase_service.list_orders(db, workspace_id, order_status, limit)


@router.post(f"{_BASE}/purchase-orders", response_model=PurchaseOrderOut, status_code=201, summary="Crear compra")
async def create_purchase_order(
    workspace_id: str, body: PurchaseOrderCreate, user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    order = await purchase_service.create_order(db, workspace_id, body, user.get("sub"))
    await _audit(workspace_id, user, "purchase_order.create", "purchase_order", order["id"], {"total_cop": order["total_cop"]})
    return order


@router.post(f"{_BASE}/purchase-orders/{{order_id}}/payments", response_model=PurchaseOrderOut, summary="Pagar compra")
async def pay_purchase_order(
    workspace_id: str, order_id: str, body: PaymentCreate,
    user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    order = await purchase_service.register_payment(db, workspace_id, order_id, body, user.get("sub"))
    await _audit(workspace_id, user, "purchase_order.payment", "purchase_order", order_id, {"amount_cop": body.amount_cop})
    return order


@router.post(f"{_BASE}/purchase-orders/{{order_id}}/void", response_model=PurchaseOrderOut, summary="Anular compra")
async def void_purchase_order(
    workspace_id: str, order_id: str, confirmed: bool = Query(False),
    user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    _require_confirmed(confirmed)
    order = await purchase_service.void_order(db, workspace_id, order_id)
    await _audit(workspace_id, user, "purchase_order.void", "purchase_order", order_id, {})
    return order


# ── Movimientos ───────────────────────────────────────────────────────────────

@router.get(f"{_BASE}/movements", response_model=list[MovementOut], summary="Listar movimientos")
async def list_movements(
    workspace_id: str, kind: Optional[FlowKind] = Query(None), category_id: Optional[str] = Query(None),
    from_date: Optional[date] = Query(None), to_date: Optional[date] = Query(None),
    include_voided: bool = Query(False), limit: int = Query(200, ge=1, le=1000),
    _user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    return await movement_service.list_movements(
        db, workspace_id, kind, category_id, from_date, to_date, include_voided, limit)


@router.post(f"{_BASE}/movements", response_model=MovementOut, status_code=201, summary="Registrar movimiento")
async def create_movement(
    workspace_id: str, body: MovementCreate, user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    row = await movement_service.create_movement(db, workspace_id, body, user.get("sub"))
    await _audit(workspace_id, user, "movement.create", "movement", row["id"],
                 {"kind": row["kind"], "amount_cop": row["amount_cop"]})
    return row


@router.post(f"{_BASE}/movements/{{movement_id}}/void", response_model=MovementOut, summary="Anular movimiento")
async def void_movement(
    workspace_id: str, movement_id: str, confirmed: bool = Query(False),
    user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    _require_confirmed(confirmed)
    row = await movement_service.void_movement(db, workspace_id, movement_id)
    await _audit(workspace_id, user, "movement.void", "movement", movement_id, {})
    return row


# ── Compensación y liquidaciones ──────────────────────────────────────────────

@router.get(f"{_BASE}/compensation", response_model=list[CompensationOut], summary="Regla de pago por miembro")
async def list_compensation(workspace_id: str, _user: dict = Depends(_manager), db: AsyncSession = Depends(get_db)):
    return await payout_service.list_compensation(db, workspace_id)


@router.put(f"{_BASE}/compensation/{{member_id}}", response_model=CompensationOut, summary="Definir regla de pago")
async def put_compensation(
    workspace_id: str, member_id: str, body: CompensationUpsert,
    user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    row = await payout_service.upsert_compensation(db, workspace_id, member_id, body)
    await _audit(workspace_id, user, "compensation.update", "workspace_member", member_id,
                 {"model": body.model, "commission_bps": body.commission_bps})
    return row


@router.get(f"{_BASE}/payouts", response_model=list[PayoutOut], summary="Listar liquidaciones")
async def list_payouts(
    workspace_id: str, member_id: Optional[str] = Query(None),
    _user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    return await payout_service.list_payouts(db, workspace_id, member_id)


@router.get(f"{_BASE}/payouts/preview", response_model=PayoutOut, summary="Vista previa de liquidación")
async def preview_payout(
    workspace_id: str, member_id: str, period_start: date, period_end: date,
    _user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    return await payout_service.preview(db, workspace_id, member_id, period_start, period_end)


@router.post(f"{_BASE}/payouts", response_model=PayoutOut, status_code=201, summary="Crear liquidación (borrador)")
async def create_payout(
    workspace_id: str, body: PayoutCreate, user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    row = await payout_service.create_draft(db, workspace_id, body, user.get("sub"))
    await _audit(workspace_id, user, "payout.create", "payout", str(row["id"]), {"net_cop": row["net_cop"]})
    return row


@router.post(f"{_BASE}/payouts/{{payout_id}}/pay", response_model=PayoutOut, summary="Pagar liquidación")
async def pay_payout(
    workspace_id: str, payout_id: str, body: PayoutPay,
    user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    row = await payout_service.pay(db, workspace_id, payout_id, body, user.get("sub"))
    await _audit(workspace_id, user, "payout.pay", "payout", payout_id, {"net_cop": row["net_cop"]})
    return row


@router.post(f"{_BASE}/payouts/{{payout_id}}/cancel", response_model=PayoutOut, summary="Cancelar liquidación")
async def cancel_payout(
    workspace_id: str, payout_id: str, confirmed: bool = Query(False),
    user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    _require_confirmed(confirmed)
    row = await payout_service.cancel(db, workspace_id, payout_id)
    await _audit(workspace_id, user, "payout.cancel", "payout", payout_id, {})
    return row


# ── Reportes ──────────────────────────────────────────────────────────────────

@router.get(f"{_BASE}/reports/summary", response_model=SummaryOut, summary="Resumen mensual")
async def summary(
    workspace_id: str, month: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    _user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    return await report_service.monthly_summary(db, workspace_id, month)


@router.get(f"{_BASE}/reports/receivables", response_model=list[SalesOrderOut], summary="Cuentas por cobrar")
async def receivables(workspace_id: str, _user: dict = Depends(_manager), db: AsyncSession = Depends(get_db)):
    return [o for o in await sales_service.list_orders(db, workspace_id, "open", limit=500) if o["balance_cop"] > 0]


@router.get(f"{_BASE}/reports/payables", response_model=list[PurchaseOrderOut], summary="Cuentas por pagar")
async def payables(workspace_id: str, _user: dict = Depends(_manager), db: AsyncSession = Depends(get_db)):
    return [o for o in await purchase_service.list_orders(db, workspace_id, "open", limit=500) if o["balance_cop"] > 0]


@router.get(f"{_BASE}/reports/commissions", response_model=list[CommissionRow], summary="Comisiones por barbero")
async def commissions(
    workspace_id: str, from_date: Optional[date] = Query(None), to_date: Optional[date] = Query(None),
    _user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    return await report_service.commissions_report(db, workspace_id, from_date, to_date)
