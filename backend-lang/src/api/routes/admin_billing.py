"""
Router /zmanager/billing — cobro manual y métricas de facturación (solo super_admin; 404 para el resto).

No hay pasarela de pago: el super_admin confirma cada pago y activa o cambia los planes desde aquí.
Toda acción que cambia estado exige `confirmed=true` y queda en `audit_logs` y en `billing_events`.
"""
import csv
import io
import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.routes.appointment_history import csv_cell
from core.config import get_settings
from core.database import get_db
from core.security import require_platform_admin
from integrations import langsmith_costs
from services import (
    billing_cartera, billing_costs, billing_documents, billing_insights, billing_metrics, billing_plans, billing_service,
    subscription_service as subs,
)
from services.audit_service import AuditService

log = logging.getLogger(__name__)
router = APIRouter(
    prefix="/zmanager/billing",
    tags=["admin-billing"],
    dependencies=[Depends(require_platform_admin)],
)


def _confirm(confirmed: bool, what: str) -> None:
    if not confirmed:
        raise HTTPException(status_code=422, detail=f"{what} requiere confirmación explícita (confirmed=true).")


async def _do(db: AsyncSession, actor: dict, workspace_id: Optional[str], action: str, entity: str, entity_id: str, op):
    """Ejecuta una operación del servicio, la confirma en BD y la deja en la auditoría."""
    try:
        res = await op
        await db.commit()
    except subs.BillingNotFound as e:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except subs.BillingError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    await AuditService.log(workspace_id=workspace_id, actor_user_id=actor.get("sub"), action=action,
                           entity_type=entity, entity_id=entity_id, after_data=jsonable(res))
    log.info("[admin-billing] %s | ws=%s | by=%s", action, workspace_id, actor.get("sub"))
    return res


def jsonable(value):
    from fastapi.encoders import jsonable_encoder
    return jsonable_encoder(value) if value is not None else None


# ── Tablero ──────────────────────────────────────────────────────────────────

@router.get("/overview", summary="Tablero: ingresos, embudo, cobranza, riesgo y margen")
async def overview(funnel_days: int = Query(90, ge=7, le=365), db: AsyncSession = Depends(get_db)):
    return await billing_metrics.overview(
        db, sandbox_phone_id=get_settings().kapso_sandbox_phone_number_id, funnel_days=funnel_days)


@router.get("/workspaces/{workspace_id}", summary="Facturación de un negocio: resumen y línea de tiempo")
async def workspace_billing(workspace_id: str, db: AsyncSession = Depends(get_db)):
    view = await subs.workspace_billing_view(db, workspace_id)
    events = (await db.execute(
        text("SELECT type, payload, created_at FROM billing_events WHERE workspace_id=:w ORDER BY created_at DESC LIMIT 50"),
        {"w": workspace_id},
    )).mappings().fetchall()
    profile = (await db.execute(
        text("SELECT legal_name, tax_id, billing_email, address FROM billing_profiles WHERE workspace_id=:w"),
        {"w": workspace_id},
    )).mappings().fetchone()
    return {**view, "events": [dict(e) for e in events], "profile": dict(profile) if profile else None}


# ── Activación y cobro ───────────────────────────────────────────────────────

class ActivateIn(BaseModel):
    plan: Literal["emprendedor", "equipo"]
    whatsapp_phone: str = Field(..., min_length=7, max_length=20,
                                description="Número de WhatsApp con el que atiende (reclama el descuento una sola vez)")
    payment_method: str = Field(..., min_length=2, max_length=40)
    payment_reference: Optional[str] = Field(None, max_length=120)


@router.post("/workspaces/{workspace_id}/activate", summary="Activar el plan tras recibir el primer pago")
async def activate(workspace_id: str, body: ActivateIn, confirmed: bool = Query(False),
                   user: dict = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    _confirm(confirmed, "Activar el plan")
    return await _do(db, user, workspace_id, "billing.activate", "subscription", workspace_id,
                     subs.activate_plan(db, workspace_id, body.plan, body.whatsapp_phone, body.payment_method,
                                        body.payment_reference, user.get("sub")))


class PaymentIn(BaseModel):
    payment_method: str = Field(..., min_length=2, max_length=40)
    payment_reference: Optional[str] = Field(None, max_length=120)


@router.post("/invoices/{invoice_id}/payment", summary="Registrar que llegó el pago de una factura")
async def register_payment(invoice_id: str, body: PaymentIn, confirmed: bool = Query(False),
                           user: dict = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    _confirm(confirmed, "Registrar un pago")
    ws = (await db.execute(text("SELECT workspace_id FROM billing_invoices WHERE id=:i"), {"i": invoice_id})
          ).scalar_one_or_none()
    return await _do(db, user, str(ws) if ws else None, "billing.payment", "billing_invoice", invoice_id,
                     subs.register_payment(db, invoice_id, body.payment_method, body.payment_reference, user.get("sub")))


class VoidIn(BaseModel):
    reason: Optional[str] = Field(None, max_length=300)


@router.post("/invoices/{invoice_id}/void", summary="Anular una factura pendiente o vencida")
async def void_invoice(invoice_id: str, body: VoidIn, confirmed: bool = Query(False),
                       user: dict = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    _confirm(confirmed, "Anular una factura")
    ws = (await db.execute(text("SELECT workspace_id FROM billing_invoices WHERE id=:i"), {"i": invoice_id})
          ).scalar_one_or_none()
    return await _do(db, user, str(ws) if ws else None, "billing.void", "billing_invoice", invoice_id,
                     subs.void_invoice(db, invoice_id, body.reason))


# ── Estado del negocio ───────────────────────────────────────────────────────

class TrialExtendIn(BaseModel):
    days: int = Field(..., ge=1, le=30)


@router.post("/workspaces/{workspace_id}/trial/extend", summary="Extender la prueba (también reabre una prueba vencida)")
async def extend_trial(workspace_id: str, body: TrialExtendIn, confirmed: bool = Query(False),
                       user: dict = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    _confirm(confirmed, "Extender la prueba")
    return await _do(db, user, workspace_id, "billing.trial_extend", "subscription", workspace_id,
                     subs.extend_trial(db, workspace_id, body.days))


@router.post("/workspaces/{workspace_id}/pause", summary="Pausar el asistente de un negocio")
async def pause(workspace_id: str, confirmed: bool = Query(False),
                user: dict = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    _confirm(confirmed, "Pausar el asistente")

    async def op():
        await subs.pause(db, workspace_id)
        return {"status": "paused"}
    return await _do(db, user, workspace_id, "billing.pause", "subscription", workspace_id, op())


@router.post("/workspaces/{workspace_id}/reactivate", summary="Reactivar sin pago (cortesía)")
async def reactivate(workspace_id: str, confirmed: bool = Query(False),
                     user: dict = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    _confirm(confirmed, "Reactivar")

    async def op():
        await subs.reactivate(db, workspace_id)
        return {"status": "active"}
    return await _do(db, user, workspace_id, "billing.reactivate", "subscription", workspace_id, op())


class PlanChangeIn(BaseModel):
    plan: Literal["emprendedor", "equipo"]


@router.post("/workspaces/{workspace_id}/plan-change", summary="Cambiar de plan (sube: ya, con prorrateo; baja: siguiente ciclo)")
async def change_plan(workspace_id: str, body: PlanChangeIn, confirmed: bool = Query(False),
                      user: dict = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    _confirm(confirmed, "Cambiar de plan")
    return await _do(db, user, workspace_id, "billing.plan_change", "subscription", workspace_id,
                     subs.change_plan(db, workspace_id, body.plan, user.get("sub")))


class AddonIn(BaseModel):
    kind: Literal["appointments_block", "appointments_topup"]
    quantity: int = Field(..., ge=10, le=1000, description="Citas adicionales (bloques de 50, 100, 200, 300 o recarga)")


@router.post("/workspaces/{workspace_id}/addons", summary="Agregar citas adicionales (bloque mensual o recarga puntual)")
async def add_addon(workspace_id: str, body: AddonIn, confirmed: bool = Query(False),
                    user: dict = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    _confirm(confirmed, "Agregar citas adicionales")
    return await _do(db, user, workspace_id, "billing.addon_add", "subscription", workspace_id,
                     subs.add_addon(db, workspace_id, body.kind, body.quantity, user.get("sub")))


@router.delete("/workspaces/{workspace_id}/addons/{addon_id}", summary="Quitar un bloque para el ciclo siguiente")
async def remove_addon(workspace_id: str, addon_id: str, confirmed: bool = Query(False),
                       user: dict = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    _confirm(confirmed, "Quitar un adicional")

    async def op():
        await subs.remove_addon(db, workspace_id, addon_id)
        return {"ok": True}
    return await _do(db, user, workspace_id, "billing.addon_remove", "subscription", workspace_id, op())


@router.post("/workspaces/{workspace_id}/founder", summary="Marcar al negocio como fundador (valor real congelado)")
async def grant_founder(workspace_id: str, confirmed: bool = Query(False),
                        user: dict = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    _confirm(confirmed, "Marcar como fundador")
    return await _do(db, user, workspace_id, "billing.founder", "subscription", workspace_id,
                     subs.grant_founder(db, workspace_id))


# ── Parámetros de la plataforma ──────────────────────────────────────────────

class SettingIn(BaseModel):
    value: int = Field(..., ge=0, le=100000)


@router.put("/settings/{key}", summary="Cambiar un parámetro (días de gracia, margen de citas, cupo de fundadores…)")
async def put_setting(key: str, body: SettingIn, user: dict = Depends(require_platform_admin),
                      db: AsyncSession = Depends(get_db)):
    if key not in billing_service.DEFAULTS:
        raise HTTPException(status_code=404, detail="Parámetro desconocido.")
    await db.execute(
        text("""INSERT INTO platform_settings (key, value) VALUES (:k, :v)
                ON CONFLICT (key) DO UPDATE SET value=:v, updated_at=NOW()"""),
        {"k": key, "v": body.value})
    await db.commit()
    await AuditService.log(workspace_id=None, actor_user_id=user.get("sub"), action="billing.setting",
                           entity_type="platform_setting", entity_id=key, after_data={"value": body.value})
    return {"key": key, "value": body.value}


class FxIn(BaseModel):
    day: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    usd_cop: float = Field(..., gt=0, lt=100000)


@router.put("/fx", summary="Registrar la tasa USD→COP de un día (para pasar los costos en dólares a pesos)")
async def put_fx(body: FxIn, user: dict = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    from datetime import date
    await db.execute(
        text("""INSERT INTO fx_rates (day, usd_cop) VALUES (:d, :r)
                ON CONFLICT (day) DO UPDATE SET usd_cop=:r"""),
        {"d": date.fromisoformat(body.day), "r": body.usd_cop})
    await db.commit()
    await AuditService.log(workspace_id=None, actor_user_id=user.get("sub"), action="billing.fx",
                           entity_type="fx_rate", entity_id=body.day, after_data={"usd_cop": body.usd_cop})
    return {"day": body.day, "usd_cop": body.usd_cop}


class MetaRateIn(BaseModel):
    category: Literal["utility", "marketing", "authentication", "service"]
    usd_price: float = Field(..., ge=0, lt=10)
    valid_from: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")


@router.put("/meta-rates", summary="Registrar la tarifa de Meta por categoría de plantilla")
async def put_meta_rate(body: MetaRateIn, user: dict = Depends(require_platform_admin),
                        db: AsyncSession = Depends(get_db)):
    from datetime import date
    await db.execute(
        text("""INSERT INTO meta_template_rates (category, usd_price, valid_from) VALUES (:c, :p, :d)
                ON CONFLICT (category, valid_from) DO UPDATE SET usd_price=:p"""),
        {"c": body.category, "p": body.usd_price, "d": date.fromisoformat(body.valid_from)})
    await db.commit()
    await AuditService.log(workspace_id=None, actor_user_id=user.get("sub"), action="billing.meta_rate",
                           entity_type="meta_template_rate", entity_id=body.category,
                           after_data=body.model_dump())
    return body.model_dump()


# ── Exportar para la contadora ───────────────────────────────────────────────

_STATUS_ES = {"pending": "Pendiente", "paid": "Pagada", "overdue": "Vencida", "void": "Anulada"}


@router.get("/invoices/export", summary="Facturas en CSV, con los datos de cobro de cada negocio")
async def export_invoices(status: Optional[Literal["pending", "paid", "overdue", "void"]] = Query(None),
                          db: AsyncSession = Depends(get_db)):
    rows = await billing_metrics.invoices_for_export(db, status)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Negocio", "Razón social", "NIT / Cédula", "Correo de cobro", "Tipo", "Periodo desde",
                     "Periodo hasta", "Vence", "Valor (COP)", "Estado", "Pagada el", "Medio de pago", "Referencia",
                     "Documento"])
    for r in rows:
        writer.writerow([csv_cell(v) for v in (
            r["workspace"], r["legal_name"], r["tax_id"], r["billing_email"],
            "Ciclo" if r["kind"] == "cycle" else "Cambio de plan", r["period_start"], r["period_end"], r["due_date"],
            r["amount_cop"], _STATUS_ES.get(r["status"], r["status"]),
            r["paid_at"].date().isoformat() if r["paid_at"] else "", r["payment_method"], r["payment_reference"],
            r["document_number"])])
    return Response(
        content="﻿" + out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="facturas-zumit.csv"'},
    )


# ── Cartera: lo que se debe y lo que viene ───────────────────────────────────

@router.get("/invoices", summary="Facturas con su cuenta de cobro y los totales de la cartera")
async def list_invoices(scope: Literal["open", "paid", "all"] = Query("open"),
                        workspace_id: Optional[str] = Query(None, max_length=64),
                        limit: int = Query(200, ge=1, le=500), db: AsyncSession = Depends(get_db)):
    return await billing_cartera.invoices(db, scope, workspace_id, limit)


@router.get("/activation-requests", summary="Negocios que pidieron activar su plan y aún no se activan")
async def list_activation_requests(db: AsyncSession = Depends(get_db)):
    return await subs.list_activation_requests(db)


@router.get("/balances", summary="Saldo por negocio: lo pendiente y lo vencido")
async def list_balances(db: AsyncSession = Depends(get_db)):
    return await billing_cartera.balances(db)


@router.get("/upcoming", summary="Próximos cobros de renovación, con su valor")
async def list_upcoming(days: int = Query(45, ge=1, le=120), db: AsyncSession = Depends(get_db)):
    return await billing_cartera.upcoming(db, days)


# ── Cuenta de cobro: generar, descargar y enviar ─────────────────────────────

async def _invoice_workspace(db: AsyncSession, invoice_id: str) -> Optional[str]:
    ws = (await db.execute(text("SELECT workspace_id FROM billing_invoices WHERE id=:i"), {"i": invoice_id})
          ).scalar_one_or_none()
    return str(ws) if ws else None


@router.post("/invoices/{invoice_id}/document", summary="Generar la cuenta de cobro (asigna el consecutivo)")
async def generate_document(invoice_id: str, confirmed: bool = Query(False),
                            user: dict = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    _confirm(confirmed, "Generar la cuenta de cobro")
    return await _do(db, user, await _invoice_workspace(db, invoice_id), "billing.document", "billing_invoice",
                     invoice_id, billing_documents.issue_document(db, invoice_id))


@router.get("/invoices/{invoice_id}/document.pdf", summary="Descargar la cuenta de cobro en PDF")
async def download_document(invoice_id: str, db: AsyncSession = Depends(get_db)):
    try:
        pdf, filename = await billing_documents.render_pdf(db, invoice_id)
    except subs.BillingNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except subs.BillingError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


class SendIn(BaseModel):
    to: Optional[EmailStr] = Field(None, description="Otro correo; si no, el de cobro del negocio")


@router.post("/invoices/{invoice_id}/send", summary="Enviar la cuenta de cobro por correo (la genera si hace falta)")
async def send_document(invoice_id: str, body: SendIn, confirmed: bool = Query(False),
                        user: dict = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    _confirm(confirmed, "Enviar la cuenta de cobro")
    return await _do(db, user, await _invoice_workspace(db, invoice_id), "billing.document_send", "billing_invoice",
                     invoice_id, billing_documents.send_document(db, invoice_id, body.to))


# ── Quien cobra y los datos de cobro de cada negocio ─────────────────────────

class IssuerIn(BaseModel):
    legal_name: str = Field(..., min_length=2, max_length=200, description="Nombre o razón social de quien cobra")
    id_type: Literal["CC", "NIT", "CE", "PASAPORTE"] = "CC"
    id_number: str = Field(..., min_length=5, max_length=30)
    city: Optional[str] = Field(None, max_length=80)
    address: Optional[str] = Field(None, max_length=200)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=30)
    payment_instructions: Optional[str] = Field(None, max_length=1000, description="Cómo pagar; sale en el PDF y el correo")
    legal_note: Optional[str] = Field(None, max_length=600, description="Texto legal al pie, ej. sobre el IVA (lo define la contadora)")


@router.get("/issuer", summary="Datos de quien emite la cuenta de cobro")
async def get_issuer(db: AsyncSession = Depends(get_db)):
    return await billing_documents.get_issuer(db)


@router.put("/issuer", summary="Guardar los datos de quien emite la cuenta de cobro")
async def put_issuer(body: IssuerIn, user: dict = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    saved = await billing_documents.save_issuer(db, body.model_dump())
    await db.commit()
    await AuditService.log(workspace_id=None, actor_user_id=user.get("sub"), action="billing.issuer",
                           entity_type="platform_issuer", entity_id="1", after_data={"id_number": body.id_number})
    return saved


class ClientProfileIn(BaseModel):
    legal_name: str = Field(..., min_length=2, max_length=200)
    tax_id: str = Field(..., min_length=5, max_length=30)
    billing_email: EmailStr
    address: Optional[str] = Field(None, max_length=300)


@router.put("/workspaces/{workspace_id}/profile", summary="Completar los datos de cobro de un negocio (por si no los dio)")
async def put_client_profile(workspace_id: str, body: ClientProfileIn, user: dict = Depends(require_platform_admin),
                             db: AsyncSession = Depends(get_db)):
    exists = (await db.execute(text("SELECT 1 FROM workspaces WHERE id=:w"), {"w": workspace_id})).scalar_one_or_none()
    if not exists:
        raise HTTPException(status_code=404, detail="El negocio no existe.")
    await billing_documents.save_profile(db, workspace_id, body.model_dump())
    await db.commit()
    await AuditService.log(workspace_id=workspace_id, actor_user_id=user.get("sub"), action="billing.profile",
                           entity_type="billing_profile", entity_id=workspace_id, after_data={"tax_id": body.tax_id})
    return {"ok": True}


# ── Costo por negocio (LangSmith) ───────────────────────────────────────────

@router.get("/costs", summary="Costo de IA por negocio y por cita agendada")
async def get_costs(days: int = Query(30, ge=1, le=90), db: AsyncSession = Depends(get_db)):
    return await billing_costs.costs(db, days)


@router.get("/insights", summary="Análisis semana a semana: ingreso vs costo, citas, plantillas y precipicio de precio")
async def get_insights(weeks: int = Query(12, ge=4, le=26), db: AsyncSession = Depends(get_db)):
    return await billing_insights.insights(db, weeks)


@router.post("/costs/sync", summary="Traer ahora el costo de LangSmith (también corre solo cada hora)")
async def sync_costs(days: int = Query(7, ge=1, le=30), db: AsyncSession = Depends(get_db)):
    return await billing_costs.sync(db, days)


@router.get("/langsmith/ping", summary="Probar la conexión con LangSmith")
async def langsmith_ping():
    return await langsmith_costs.ping()


# ── Planes: tablero, vista previa y edición ──────────────────────────────────

@router.get("/plans", summary="Tablero de planes: configuración y estadísticas de cada plan, y las series para los gráficos")
async def plans_dashboard(days: int = Query(30, ge=7, le=90), db: AsyncSession = Depends(get_db)):
    return await billing_plans.dashboard(db, days)


class PlanChangesIn(BaseModel):
    """Lo que se puede editar de un plan. Todo es opcional; solo se aplica lo que realmente cambia."""
    name: Optional[str] = Field(None, min_length=2, max_length=60)
    description: Optional[str] = Field(None, max_length=200)
    price_cop: Optional[int] = Field(None, ge=0, le=10_000_000)
    launch_price_cop: Optional[int] = Field(None, ge=0, le=10_000_000, description="null = sin precio de lanzamiento")
    max_appointments: Optional[int] = Field(None, ge=1, le=100_000)
    max_professionals: Optional[int] = Field(None, ge=1, le=200)
    extra_professional_price_cop: Optional[int] = Field(None, ge=0, le=1_000_000)
    is_active: Optional[bool] = None


def _plan_http_error(e: Exception) -> HTTPException:
    if isinstance(e, subs.BillingNotFound):
        return HTTPException(status_code=404, detail=str(e))
    if isinstance(e, billing_plans.PlanError):
        return HTTPException(status_code=422, detail=str(e))
    return HTTPException(status_code=409, detail=str(e))


@router.post("/plans/{plan_id}/preview", summary="Qué pasaría al editar un plan (no cambia nada)")
async def preview_plan(plan_id: str, body: PlanChangesIn, db: AsyncSession = Depends(get_db)):
    changes = body.model_dump(exclude_unset=True)
    try:
        return await billing_plans.preview(db, plan_id, changes)
    except subs.BillingError as e:
        raise _plan_http_error(e)


@router.put("/plans/{plan_id}", summary="Editar un plan (precio, límites, nombre). Rige desde el próximo cobro / ya, según el campo")
async def update_plan(plan_id: str, body: PlanChangesIn, confirmed: bool = Query(False),
                      user: dict = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    _confirm(confirmed, "Editar un plan")
    changes = body.model_dump(exclude_unset=True)
    try:
        res = await billing_plans.update_plan(db, plan_id, changes)
        await db.commit()
    except subs.BillingError as e:
        await db.rollback()
        raise _plan_http_error(e)
    await AuditService.log(
        workspace_id=None, actor_user_id=user.get("sub"), action="billing.plan_update", entity_type="billing_plan",
        entity_id=res["plan"]["id"], before_data=jsonable(res["before"]),
        after_data=jsonable({k: res["plan"][k] for k in res["before"]}))
    log.info("[admin-billing] plan editado | plan=%s | cambios=%s | by=%s", res["plan"]["code"], list(res["before"]), user.get("sub"))
    return res
