"""
Router /billing — Planes de suscripción del SaaS.
Solo super_admin puede gestionar planes; workspace_owner ve su suscripción.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from core.database import get_db
from core.security import require_role, require_workspace_access
from services import billing_plans, billing_service, subscription_service as subs
from services.audit_service import AuditService

log = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])


class BillingPlanOut(BaseModel):
    id: str
    code: Optional[str] = None
    name: str
    description: Optional[str]
    price_cop: int
    billing_interval: str
    launch_price_cop: Optional[int] = None
    max_appointments: Optional[int] = None
    max_professionals: Optional[int] = None
    extra_professional_price_cop: int = 0
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
        text("SELECT * FROM billing_plans WHERE is_active = TRUE AND code IS NOT NULL ORDER BY price_cop, name"),
    )).mappings().fetchall()
    return [dict(r) for r in rows]


@router.get(
    "/pricing",
    summary="Precios para la landing (público)",
)
async def public_pricing(response: Response, db: AsyncSession = Depends(get_db)):
    """Nombres, precios y reglas de los planes, listos para la landing.

    Nunca falla hacia afuera: si la base no está lista (migración 022 sin aplicar) o la lectura falla, responde con la
    lista de planes vacía y la landing usa los valores que trae de fábrica. Un minuto de caché: es la página más visitada.
    """
    response.headers["Cache-Control"] = "public, max-age=60"
    try:
        return await billing_plans.public_pricing(db)
    except Exception as exc:
        await db.rollback()
        log.warning("[billing] precios públicos no disponibles; la landing usa los de fábrica | err=%s", type(exc).__name__)
        response.headers["Cache-Control"] = "no-store"
        return {"plans": []}


@router.get(
    "/workspaces/{workspace_id}/subscription",
    response_model=SubscriptionOut,
    summary="Ver la suscripción más reciente del workspace",
    dependencies=[Depends(require_workspace_access("workspace_owner"))],
)
async def get_subscription(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
):
    # La más reciente, sea cual sea su estado: la prueba y los pausados también tienen suscripción.
    row = (await db.execute(
        text("SELECT * FROM subscriptions WHERE workspace_id = :workspace_id ORDER BY created_at DESC LIMIT 1"),
        {"workspace_id": workspace_id},
    )).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="El negocio no tiene suscripción.")
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
    allowed = {"trial", "active", "past_due", "paused", "cancelled", "expired", "pending_payment", "suspended"}
    if new_status not in allowed:
        raise HTTPException(status_code=422, detail=f"Estado inválido. Permitidos: {sorted(allowed)}")

    before = (await db.execute(
        text("SELECT id, status FROM subscriptions WHERE workspace_id=:w ORDER BY created_at DESC LIMIT 1"),
        {"w": workspace_id},
    )).mappings().fetchone()
    if not before:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada.")
    row = (await db.execute(
        text("""UPDATE subscriptions SET status=:s, notes=COALESCE(:n, notes), updated_at=NOW()
                WHERE id=:id RETURNING *"""),
        {"s": new_status, "n": notes, "id": before["id"]},
    )).mappings().fetchone()
    await billing_service.log_event(
        db, workspace_id, "status_changed",
        {"from": before["status"], "to": new_status, "by": current_user.get("sub")}, str(before["id"]))
    await db.commit()
    await AuditService.log(
        workspace_id=workspace_id, actor_user_id=current_user.get("sub"), action="billing.status",
        entity_type="subscription", entity_id=str(before["id"]),
        before_data={"status": before["status"]}, after_data={"status": new_status},
    )
    log.info("[billing] status=%s | workspace=%s | by=%s", new_status, workspace_id, current_user.get("sub"))
    return dict(row)


# ── Dueño del negocio ────────────────────────────────────────────────────────

class BillingProfileIn(BaseModel):
    legal_name: str = Field(..., min_length=2, max_length=200, description="Nombre o razón social")
    tax_id: str = Field(..., min_length=5, max_length=30, description="Cédula o NIT")
    billing_email: EmailStr
    address: Optional[str] = Field(None, max_length=300)


@router.get(
    "/workspaces/{workspace_id}/usage",
    summary="Saldo de citas del asistente y de profesionales (todo el equipo, sin precios)",
    dependencies=[Depends(require_workspace_access("viewer"))],
)
async def billing_usage(workspace_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await subs.workspace_usage_view(db, workspace_id)
    except Exception:
        # Falla «abierto»: si la facturación no está lista, el panel simplemente no muestra el saldo.
        return {"has_subscription": False, "status": "none", "serving": True}


@router.get(
    "/workspaces/{workspace_id}/summary",
    summary="Plan, uso del ciclo, próximo cobro y facturas del negocio",
    dependencies=[Depends(require_workspace_access("workspace_owner"))],
)
async def billing_summary(workspace_id: str, db: AsyncSession = Depends(get_db)):
    return await subs.workspace_billing_view(db, workspace_id)


@router.get(
    "/workspaces/{workspace_id}/profile",
    summary="Datos de cobro del negocio",
    dependencies=[Depends(require_workspace_access("workspace_owner"))],
)
async def get_profile(workspace_id: str, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(
        text("SELECT legal_name, tax_id, billing_email, address FROM billing_profiles WHERE workspace_id=:w"),
        {"w": workspace_id},
    )).mappings().fetchone()
    return dict(row) if row else None


@router.put(
    "/workspaces/{workspace_id}/profile",
    summary="Guardar los datos de cobro (nombre o razón social, cédula o NIT, correo)",
)
async def put_profile(
    workspace_id: str,
    body: BillingProfileIn,
    current_user: dict = Depends(require_workspace_access("workspace_owner")),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        text("""
        INSERT INTO billing_profiles (workspace_id, legal_name, tax_id, billing_email, address)
        VALUES (:w, :n, :t, :e, :a)
        ON CONFLICT (workspace_id) DO UPDATE SET legal_name=:n, tax_id=:t, billing_email=:e, address=:a, updated_at=NOW()
        """),
        {"w": workspace_id, "n": body.legal_name.strip(), "t": body.tax_id.strip(), "e": body.billing_email,
         "a": body.address},
    )
    await db.commit()
    await AuditService.log(
        workspace_id=workspace_id, actor_user_id=current_user.get("sub"), action="billing.profile",
        entity_type="billing_profile", entity_id=workspace_id, after_data={"tax_id": body.tax_id.strip()},
    )
    return {"ok": True}


@router.get(
    "/workspaces/{workspace_id}/plan-change-preview",
    summary="Qué pasaría al cambiar de plan (prorrateo si sube, requisitos si baja)",
    dependencies=[Depends(require_workspace_access("workspace_owner"))],
)
async def plan_change_preview(workspace_id: str, plan: str = Query(..., max_length=40),
                              db: AsyncSession = Depends(get_db)):
    try:
        return await subs.preview_plan_change(db, workspace_id, plan)
    except subs.BillingNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except subs.BillingError as e:
        raise HTTPException(status_code=409, detail=str(e))


class ExtraAppointmentsIn(BaseModel):
    quantity: int = Field(..., description="Bloque de citas adicionales: 50, 100, 200 o 300")


@router.post(
    "/workspaces/{workspace_id}/request-appointments",
    summary="Pedir más citas para el ciclo: se acreditan ya y queda un saldo pendiente de pago",
)
async def request_appointments(
    workspace_id: str,
    body: ExtraAppointmentsIn,
    confirmed: bool = Query(False),
    current_user: dict = Depends(require_workspace_access("workspace_owner")),
    db: AsyncSession = Depends(get_db),
):
    if not confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Pedir citas adicionales genera un cobro: requiere confirmación explícita (confirmed=true).",
        )
    try:
        res = await subs.request_extra_appointments(db, workspace_id, body.quantity, current_user.get("sub"))
    except subs.BillingNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except subs.BillingError as e:
        raise HTTPException(status_code=409, detail=str(e))
    await db.commit()
    await AuditService.log(
        workspace_id=workspace_id, actor_user_id=current_user.get("sub"),
        action="billing.extra_appointments_request",
        entity_type="subscription", entity_id=workspace_id, after_data=res,
    )
    return res


@router.get(
    "/workspaces/{workspace_id}/payment-info",
    summary="Cómo pagar a Zumit: instrucciones y WhatsApp para enviar el comprobante",
    dependencies=[Depends(require_workspace_access("workspace_owner"))],
)
async def payment_info(workspace_id: str, db: AsyncSession = Depends(get_db)):
    """Solo lo que el cliente necesita para pagar. No expone el resto de los datos de quien cobra."""
    from services import billing_documents
    issuer = await billing_documents.get_issuer(db) or {}
    return {"payment_instructions": issuer.get("payment_instructions"), "phone": issuer.get("phone")}


class ActivationRequestIn(BaseModel):
    plan: str = Field(..., max_length=40, description="Código del plan que quiere: emprendedor o equipo")
    whatsapp_phone: str = Field(..., min_length=7, max_length=30)
    payment_reference: Optional[str] = Field(None, max_length=120, description="Referencia o nota del pago, si ya pagó")


async def _email_activation_request(db, workspace_id: str, res: dict, body: ActivationRequestIn) -> None:
    """Correo a los super_admin. Mejor esfuerzo: la solicitud ya quedó guardada y se ve en Zumit Manager › Cobros."""
    try:
        from services.email_service import EmailService, _base_template
        emails = (await db.execute(
            text("SELECT email FROM users WHERE role = 'super_admin' AND is_active = TRUE"))).scalars().all()
        ref = f"<br>Referencia del pago: {body.payment_reference}" if body.payment_reference else ""
        html = _base_template(
            f"<h2 style='margin:0 0 12px'>Solicitud de activación: {res['workspace_name']}</h2>"
            f"<p style='line-height:1.6'>Quiere activar el plan {res['plan_name']}.<br>WhatsApp: {body.whatsapp_phone}{ref}</p>"
            "<p style='line-height:1.6'>Cuando veas el pago, actívalo en Zumit Manager › Cobros.</p>",
            "Aviso automático de Zumit.")
        for to in emails:
            await EmailService._send(to, f"Solicitud de activación: {res['workspace_name']}", html)
    except Exception as exc:
        log.warning("[billing] correo de solicitud de activación falló | ws=%s | err=%s", workspace_id, type(exc).__name__)


@router.post(
    "/workspaces/{workspace_id}/request-activation",
    summary="Avisar que quiere activar el plan (el super_admin lo activa al ver el pago)",
)
async def request_activation(
    workspace_id: str,
    body: ActivationRequestIn,
    confirmed: bool = Query(False),
    current_user: dict = Depends(require_workspace_access("workspace_owner")),
    db: AsyncSession = Depends(get_db),
):
    if not confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Solicitar la activación requiere confirmación explícita (confirmed=true).",
        )
    try:
        res = await subs.request_activation(db, workspace_id, body.plan, body.whatsapp_phone,
                                            body.payment_reference, current_user.get("sub"))
    except subs.BillingNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except subs.BillingError as e:
        raise HTTPException(status_code=409, detail=str(e))
    await db.commit()
    await AuditService.log(
        workspace_id=workspace_id, actor_user_id=current_user.get("sub"), action="billing.activation_request",
        entity_type="subscription", entity_id=workspace_id, after_data={"plan": body.plan},
    )
    if res["created"]:
        await _email_activation_request(db, workspace_id, res, body)
    return {"ok": True, "already_requested": not res["created"]}


@router.post(
    "/workspaces/{workspace_id}/cancel",
    summary="Pedir la cancelación al final del ciclo pagado (o deshacerla con undo=true)",
)
async def cancel_subscription(
    workspace_id: str,
    undo: bool = Query(False),
    confirmed: bool = Query(False),
    current_user: dict = Depends(require_workspace_access("workspace_owner")),
    db: AsyncSession = Depends(get_db),
):
    if not undo and not confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cancelar requiere confirmación explícita (confirmed=true).",
        )
    try:
        res = await subs.request_cancel(db, workspace_id, undo=undo)
    except subs.BillingNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except subs.BillingError as e:
        raise HTTPException(status_code=409, detail=str(e))
    await db.commit()
    await AuditService.log(
        workspace_id=workspace_id, actor_user_id=current_user.get("sub"),
        action="billing.cancel_undo" if undo else "billing.cancel_request",
        entity_type="subscription", entity_id=workspace_id, after_data=res,
    )
    return res
