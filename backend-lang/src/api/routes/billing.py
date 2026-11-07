"""
Router /billing — Planes de suscripción del SaaS.
Solo super_admin puede gestionar planes; workspace_owner ve su suscripción.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from core.database import get_db
from core.security import require_role, require_workspace_access

log = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])


class BillingPlanOut(BaseModel):
    id: str
    name: str
    description: Optional[str]
    price_cop: int
    billing_interval: str
    max_channels: int
    max_calendars: int
    max_services: int
    max_messages: int
    is_active: bool
    created_at: datetime


class SubscriptionOut(BaseModel):
    id: str
    workspace_id: str
    billing_plan_id: str
    status: str
    payment_method: Optional[str]
    paid_this_month: bool
    current_period_start: Optional[datetime]
    current_period_end: Optional[datetime]
    next_billing_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime


@router.get(
    "/plans",
    response_model=list[BillingPlanOut],
    summary="Listar planes disponibles (público)",
)
async def list_plans(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        text("SELECT * FROM billing_plans WHERE is_active = TRUE"),
    )).mappings().fetchall()
    return [dict(r) for r in rows]


@router.get(
    "/workspaces/{workspace_id}/subscription",
    response_model=SubscriptionOut,
    summary="Ver suscripción activa del workspace",
    dependencies=[Depends(require_workspace_access("owner"))],
)
async def get_subscription(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(
        text("SELECT * FROM subscriptions WHERE workspace_id = :workspace_id AND status = 'active'"),
        {"workspace_id": workspace_id},
    )).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Suscripción activa no encontrada.")
    return dict(row)


@router.patch(
    "/workspaces/{workspace_id}/subscription/status",
    response_model=SubscriptionOut,
    summary="Actualizar estado de suscripción (solo super_admin)",
    dependencies=[Depends(require_role("super_admin"))],
)
async def update_subscription_status(
    workspace_id: str,
    new_status: str,
    notes: Optional[str] = None,
    current_user: dict = Depends(require_role("super_admin")),
    db: AsyncSession = Depends(get_db),
):
    allowed = {"active", "pending_payment", "suspended", "cancelled", "expired"}
    if new_status not in allowed:
        raise HTTPException(status_code=422, detail=f"Estado inválido. Permitidos: {allowed}")

    if notes:
        row = (await db.execute(
            text("UPDATE subscriptions SET status=:new_status, notes=:notes WHERE workspace_id=:workspace_id RETURNING *"),
            {"new_status": new_status, "notes": notes, "workspace_id": workspace_id},
        )).mappings().fetchone()
    else:
        row = (await db.execute(
            text("UPDATE subscriptions SET status=:new_status WHERE workspace_id=:workspace_id RETURNING *"),
            {"new_status": new_status, "workspace_id": workspace_id},
        )).mappings().fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada.")
    await db.commit()
    log.info("[billing] status=%s | workspace=%s | by=%s", new_status, workspace_id, current_user.get("sub"))
    return dict(row)
