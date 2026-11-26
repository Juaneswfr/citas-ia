"""
SubscriptionService — operaciones que cambian el estado de una suscripción (cobro manual, sin pasarela).

Las usan las rutas de /billing y /zmanager/billing y el worker de facturación. Ninguna hace commit: lo hace quien
llama, para que una operación y su evento queden juntos o no queden. Cada operación deja un evento en
`billing_events` (base de las métricas del panel).
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import text

from services import billing_service as bs

log = logging.getLogger(__name__)

PLAN_FOR_TRIAL = "emprendedor"  # la prueba permite hasta 3 profesionales


class BillingError(Exception):
    """Operación de facturación no permitida (el router la convierte en 409 o 422)."""


class BillingNotFound(BillingError):
    """El negocio, la suscripción o la factura no existen."""


def _tz(name: Optional[str]) -> ZoneInfo:
    try:
        return ZoneInfo(name or bs.DEFAULT_TZ)
    except Exception:
        return ZoneInfo(bs.DEFAULT_TZ)


async def _plan(db, code: str) -> dict:
    row = (await db.execute(
        text("SELECT * FROM billing_plans WHERE code = :c AND is_active = TRUE"), {"c": code},
    )).mappings().fetchone()
    if not row:
        raise BillingNotFound(f"El plan «{code}» no existe o está inactivo.")
    return dict(row)


async def get_live_subscription(db, workspace_id: str) -> dict:
    """La suscripción vigente del negocio (trial, active, past_due o paused) con el plan y la zona horaria."""
    row = (await db.execute(
        text("""
        SELECT s.*, p.code AS plan_code, p.name AS plan_name, p.price_cop AS plan_price_cop,
               p.launch_price_cop, p.max_appointments, p.max_professionals,
               p.extra_professional_price_cop, w.timezone AS tz
        FROM subscriptions s
        JOIN billing_plans p ON p.id = s.billing_plan_id
        JOIN workspaces w ON w.id = s.workspace_id
        WHERE s.workspace_id = :w AND s.status IN ('trial','active','past_due','paused','pending_payment')
        ORDER BY s.created_at DESC LIMIT 1
        """),
        {"w": workspace_id},
    )).mappings().fetchone()
    if not row:
        raise BillingNotFound("El negocio no tiene una suscripción vigente.")
    return dict(row)


# ── Prueba ───────────────────────────────────────────────────────────────────

async def create_trial(db, workspace_id: str, now: Optional[datetime] = None) -> Optional[str]:
    """Prueba de 7 días sin tarjeta al crear la cuenta. Va en un SAVEPOINT y nunca hace fallar el registro:
    si la migración 022 aún no está aplicada, el negocio queda «sin plan asignado» como hasta ahora."""
    now = now or datetime.now(timezone.utc)
    try:
        async with db.begin_nested():
            plan = await _plan(db, PLAN_FOR_TRIAL)
            days = (await bs.get_settings(db))["trial_days"]
            sub_id = str((await db.execute(
                text("""
                INSERT INTO subscriptions (workspace_id, billing_plan_id, status, trial_started_at, trial_ends_at)
                VALUES (:w, :p, 'trial', :now, :ends) RETURNING id
                """),
                {"w": workspace_id, "p": plan["id"], "now": now, "ends": now + timedelta(days=days)},
            )).scalar_one())
            await bs.log_event(db, workspace_id, "trial_started", {"days": days}, sub_id)
        return sub_id
    except Exception as exc:
        log.warning("[billing] no se pudo crear la prueba | ws=%s | err=%s: %s", workspace_id, type(exc).__name__, exc)
        return None


async def extend_trial(db, workspace_id: str, days: int, now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    sub = await get_live_subscription(db, workspace_id)
    if sub["status"] not in ("trial", "paused") or sub.get("activated_at"):
        raise BillingError("Solo se extiende la prueba de un negocio que aún no se activó.")
    ends = max(sub["trial_ends_at"] or now, now) + timedelta(days=days)
    await db.execute(
        text("""UPDATE subscriptions SET status='trial', trial_ends_at=:e, paused_at=NULL, data_purge_after=NULL,
                updated_at=NOW() WHERE id=:id"""),
        {"e": ends, "id": sub["id"]},
    )
    await bs.log_event(db, workspace_id, "trial_extended", {"days": days, "ends": ends.isoformat()}, str(sub["id"]))
    return {"trial_ends_at": ends}


# ── Oferta de lanzamiento: una vez por número de WhatsApp ────────────────────

async def claim_discount(db, phone: str, workspace_id: str) -> bool:
    """True si este número puede usar el descuento de lanzamiento (no lo había usado otro negocio)."""
    key = bs.normalize_phone(phone)
    if not key:
        return False
    row = (await db.execute(
        text("SELECT workspace_id, discount_claimed_at FROM offer_claims WHERE claim_key = :k"), {"k": key},
    )).mappings().fetchone()
    if row and row["discount_claimed_at"] and str(row["workspace_id"]) != str(workspace_id):
        return False
    await db.execute(
        text("""
        INSERT INTO offer_claims (claim_key, workspace_id, discount_claimed_at) VALUES (:k, :w, NOW())
        ON CONFLICT (claim_key) DO UPDATE SET workspace_id = :w,
            discount_claimed_at = COALESCE(offer_claims.discount_claimed_at, NOW())
        """),
        {"k": key, "w": workspace_id},
    )
    return True


# ── Facturas ─────────────────────────────────────────────────────────────────

async def _invoice_lines(db, sub: dict, period_start: date, period_end: date) -> list[dict]:
    """Líneas del cobro de un ciclo: plan (con descuento si le quedan ciclos), citas adicionales y profesionales extra."""
    price = bs.price_for_cycle(sub["plan_price_cop"], sub["launch_price_cop"],
                               sub["discount_cycles_remaining"], sub.get("frozen_price_cop"))
    discounted = sub["discount_cycles_remaining"] > 0 and sub["launch_price_cop"] is not None
    lines = [{"kind": "plan", "quantity": 1, "amount": price,
              "description": f"Plan {sub['plan_name']}" + (" · precio de lanzamiento" if discounted else "")}]
    addons = (await db.execute(
        text("""
        SELECT kind, quantity, price_cop FROM subscription_addons
        WHERE subscription_id = :s AND valid_from < :end AND (valid_until IS NULL OR valid_until > :start)
        ORDER BY created_at
        """),
        {"s": sub["id"], "start": period_start, "end": period_end},
    )).mappings().fetchall()
    for a in addons:
        what = "Recarga" if a["kind"] == "appointments_topup" else "Bloque"
        lines.append({"kind": "appointments", "quantity": a["quantity"], "amount": a["price_cop"],
                      "description": f"{what} de {a['quantity']} citas adicionales"})
    active = int((await db.execute(
        text("SELECT COUNT(*) FROM calendars WHERE workspace_id = :w AND sync_status='active' AND member_id IS NOT NULL"),
        {"w": sub["workspace_id"]},
    )).scalar_one() or 0)
    extra = bs.extra_professionals(active, sub["max_professionals"])
    if extra:
        lines.append({"kind": "professional", "quantity": extra, "amount": extra * sub["extra_professional_price_cop"],
                      "description": f"{extra} profesional(s) adicional(es)"})
    return lines


async def issue_cycle_invoice(db, sub: dict, period_start: date, period_end: date, due: Optional[date] = None,
                              paid: Optional[dict] = None) -> Optional[str]:
    """Genera el cobro del ciclo que empieza en `period_start`. Idempotente: si ya existe, no hace nada y
    no consume un ciclo de descuento. Devuelve el id de la factura nueva o None."""
    lines = await _invoice_lines(db, sub, period_start, period_end)
    total = sum(l["amount"] for l in lines)
    inv_id = (await db.execute(
        text("""
        INSERT INTO billing_invoices (workspace_id, subscription_id, kind, period_start, period_end, due_date,
                                      amount_cop, status, paid_at, payment_method, payment_reference, verified_by)
        VALUES (:w, :s, 'cycle', :ps, :pe, :due, :amt, :status, :paid_at, :pm, :pr, :vb)
        ON CONFLICT (workspace_id, period_start) WHERE status <> 'void' AND kind = 'cycle' DO NOTHING
        RETURNING id
        """),
        {"w": sub["workspace_id"], "s": sub["id"], "ps": period_start, "pe": period_end,
         "due": due or period_start, "amt": total,
         "status": "paid" if paid else "pending",
         "paid_at": datetime.now(timezone.utc) if paid else None,
         "pm": (paid or {}).get("method"), "pr": (paid or {}).get("reference"), "vb": (paid or {}).get("actor")},
    )).scalar_one_or_none()
    if not inv_id:
        return None
    inv_id = str(inv_id)
    for l in lines:
        await db.execute(
            text("""INSERT INTO billing_invoice_lines (invoice_id, kind, description, quantity, amount_cop)
                    VALUES (:i, :k, :d, :q, :a)"""),
            {"i": inv_id, "k": l["kind"], "d": l["description"], "q": l["quantity"], "a": l["amount"]},
        )
    if sub["discount_cycles_remaining"] > 0:
        await db.execute(
            text("UPDATE subscriptions SET discount_cycles_remaining = discount_cycles_remaining - 1 WHERE id = :id"),
            {"id": sub["id"]},
        )
    await bs.log_event(db, str(sub["workspace_id"]), "invoice_issued",
                       {"invoice_id": inv_id, "amount": total, "period_start": period_start.isoformat()},
                       str(sub["id"]))
    return inv_id


async def charge_extra_professionals(db, sub: dict, now: Optional[datetime] = None) -> Optional[dict]:
    """Cobra, prorrateado, el profesional que se agregó a mitad de ciclo por encima de lo que incluye el plan.

    Compara los profesionales extra de hoy con los que ya se facturaron en el ciclo en curso (el cobro del ciclo más los
    prorrateos de este mismo tipo) y cobra la diferencia por los días que quedan. Idempotente: tras cobrar, lo
    facturado iguala lo extra y la siguiente pasada no hace nada. No devuelve dinero si un profesional se quita.
    El cobro vence al cierre del ciclo, junto con la renovación: no pausa el servicio por un monto pequeño.
    """
    now = now or datetime.now(timezone.utc)
    tz = _tz(sub["tz"])
    today = now.astimezone(tz).date()
    start, end = bs.cycle_bounds(sub["cycle_anchor_day"] or sub["activated_at"].astimezone(tz).day, today)
    active = int((await db.execute(
        text("SELECT COUNT(*) FROM calendars WHERE workspace_id = :w AND sync_status='active' AND member_id IS NOT NULL"),
        {"w": sub["workspace_id"]},
    )).scalar_one() or 0)
    extra = bs.extra_professionals(active, sub["max_professionals"])
    if extra == 0:
        return None
    billed = int((await db.execute(
        text("""
        SELECT COALESCE(SUM(l.quantity), 0) FROM billing_invoice_lines l
        JOIN billing_invoices i ON i.id = l.invoice_id
        WHERE i.workspace_id = :w AND i.status <> 'void' AND l.kind = 'professional'
          AND i.period_start >= :start AND i.period_start < :end
        """),
        {"w": sub["workspace_id"], "start": start, "end": end},
    )).scalar_one() or 0)
    missing = extra - billed
    if missing <= 0:
        return None
    each = bs.professional_prorata(sub["extra_professional_price_cop"], (end - today).days, (end - start).days)
    amount = missing * each
    if amount <= 0:
        return None  # último día del ciclo: lo cubre la renovación
    inv = str((await db.execute(
        text("""
        INSERT INTO billing_invoices (workspace_id, subscription_id, kind, period_start, period_end, due_date, amount_cop)
        VALUES (:w, :s, 'proration', :ps, :pe, :due, :a) RETURNING id
        """),
        {"w": sub["workspace_id"], "s": sub["id"], "ps": today, "pe": end, "due": end, "a": amount},
    )).scalar_one())
    await db.execute(
        text("""INSERT INTO billing_invoice_lines (invoice_id, kind, description, quantity, amount_cop)
                VALUES (:i, 'professional', :d, :q, :a)"""),
        {"i": inv, "d": f"{missing} profesional(s) adicional(es), {(end - today).days} de {(end - start).days} días del ciclo",
         "q": missing, "a": amount},
    )
    await bs.log_event(db, str(sub["workspace_id"]), "professional_billed",
                       {"invoice_id": inv, "quantity": missing, "amount": amount, "days_left": (end - today).days},
                       str(sub["id"]))
    return {"invoice_id": inv, "quantity": missing, "amount_cop": amount, "due_date": end}


async def request_activation(db, workspace_id: str, plan_code: str, whatsapp_phone: str,
                             payment_reference: Optional[str], actor_user_id: Optional[str]) -> dict:
    """El dueño avisa que quiere activar su plan (o que ya pagó). No activa nada: lo hace el super_admin al ver el pago.

    Solo vale para quien aún no pagó (prueba o pausado). Una solicitud abierta a la vez: repetirla la actualiza.
    Devuelve `{"created": bool, "workspace_name", "plan_name"}` para que quien llama avise al equipo de Zumit.
    """
    sub = await get_live_subscription(db, workspace_id)
    if sub["status"] not in ("trial", "paused"):
        raise BillingError("El negocio ya tiene un plan activo.")
    plan = await _plan(db, plan_code)
    if not bs.normalize_phone(whatsapp_phone):
        raise BillingError("Escribe el número de WhatsApp con el que atiende el negocio.")
    open_req = (await db.execute(
        text("""
        SELECT 1 FROM billing_events e
        WHERE e.workspace_id = :w AND e.type = 'activation_requested'
          AND e.created_at > COALESCE((SELECT MAX(a.created_at) FROM billing_events a
                                        WHERE a.workspace_id = :w AND a.type = 'activated'), 'epoch')
        LIMIT 1
        """),
        {"w": workspace_id},
    )).scalar_one_or_none()
    await bs.log_event(db, workspace_id, "activation_requested",
                       {"plan": plan_code, "phone": bs.normalize_phone(whatsapp_phone),
                        "reference": payment_reference, "by": actor_user_id}, str(sub["id"]))
    name = (await db.execute(text("SELECT name FROM workspaces WHERE id = :w"), {"w": workspace_id})).scalar_one_or_none()
    return {"created": not open_req, "workspace_name": name or "Negocio", "plan_name": plan["name"]}


async def list_activation_requests(db) -> list[dict]:
    """Solicitudes de activación sin atender (la última de cada negocio que aún no se activó), la más antigua primero."""
    rows = (await db.execute(text("""
        SELECT DISTINCT ON (e.workspace_id)
               e.workspace_id, w.name AS workspace, e.created_at AS requested_at,
               e.payload->>'plan' AS plan, e.payload->>'phone' AS phone, e.payload->>'reference' AS reference,
               s.status
        FROM billing_events e
        JOIN workspaces w ON w.id = e.workspace_id
        JOIN subscriptions s ON s.id = e.subscription_id
        WHERE e.type = 'activation_requested' AND s.status IN ('trial', 'paused')
          AND e.created_at > COALESCE((SELECT MAX(a.created_at) FROM billing_events a
                                        WHERE a.workspace_id = e.workspace_id AND a.type = 'activated'), 'epoch')
        ORDER BY e.workspace_id, e.created_at DESC
    """))).mappings().fetchall()
    return sorted((dict(r) for r in rows), key=lambda r: r["requested_at"])


async def activate_plan(db, workspace_id: str, plan_code: str, whatsapp_phone: str, payment_method: str,
                        payment_reference: Optional[str], actor_user_id: Optional[str],
                        now: Optional[datetime] = None) -> dict:
    """El negocio pagó el primer ciclo y el asistente empieza a atender clientes reales.

    El ciclo y los ciclos con descuento cuentan desde hoy (la activación), no desde el registro ni la prueba.
    """
    now = now or datetime.now(timezone.utc)
    sub = await get_live_subscription(db, workspace_id)
    if sub["status"] in ("active", "past_due"):
        raise BillingError("El negocio ya tiene un plan activo. Para cambiarlo usa el cambio de plan.")
    plan = await _plan(db, plan_code)
    settings = await bs.get_settings(db)
    discount = await claim_discount(db, whatsapp_phone, workspace_id)
    today = now.astimezone(_tz(sub["tz"])).date()
    await db.execute(
        text("""
        UPDATE subscriptions SET billing_plan_id=:p, status='active', activated_at=:now, cycle_anchor_day=:anchor,
               discount_cycles_remaining=:dc, paused_at=NULL, past_due_since=NULL, data_purge_after=NULL,
               cancel_at_period_end=FALSE, payment_method=:pm, payment_verified_by=:by, updated_at=NOW()
        WHERE id=:id
        """),
        {"p": plan["id"], "now": now, "anchor": today.day, "id": sub["id"], "pm": payment_method, "by": actor_user_id,
         "dc": settings["launch_discount_cycles"] if discount else 0},
    )
    sub = await get_live_subscription(db, workspace_id)
    start, end = bs.cycle_bounds(today.day, today)
    invoice_id = await issue_cycle_invoice(
        db, sub, start, end, due=start,
        paid={"method": payment_method, "reference": payment_reference, "actor": actor_user_id})
    await bs.log_event(db, workspace_id, "activated",
                       {"plan": plan_code, "discount": discount, "phone": bs.normalize_phone(whatsapp_phone)},
                       str(sub["id"]))
    return {"invoice_id": invoice_id, "discount_applied": discount, "cycle_start": start, "cycle_end": end}


async def register_payment(db, invoice_id: str, method: str, reference: Optional[str],
                           actor_user_id: Optional[str]) -> dict:
    """El super_admin confirma que llegó un pago. Si el negocio estaba en mora o pausado, vuelve a atender."""
    inv = (await db.execute(
        text("SELECT * FROM billing_invoices WHERE id = :i"), {"i": invoice_id},
    )).mappings().fetchone()
    if not inv:
        raise BillingNotFound("La factura no existe.")
    if inv["status"] in ("paid", "void"):
        raise BillingError(f"La factura ya está {'pagada' if inv['status'] == 'paid' else 'anulada'}.")
    await db.execute(
        text("""UPDATE billing_invoices SET status='paid', paid_at=NOW(), payment_method=:m, payment_reference=:r,
                verified_by=:by, updated_at=NOW() WHERE id=:i"""),
        {"m": method, "r": reference, "by": actor_user_id, "i": invoice_id},
    )
    reactivated = False
    if inv["subscription_id"]:
        res = (await db.execute(
            text("""
            UPDATE subscriptions SET status='active', past_due_since=NULL, paused_at=NULL, data_purge_after=NULL,
                   paid_this_month=TRUE, payment_method=:m, payment_verified_by=:by, updated_at=NOW()
            WHERE id=:s AND status IN ('past_due','paused')
            RETURNING id
            """),
            {"m": method, "by": actor_user_id, "s": inv["subscription_id"]},
        )).scalar_one_or_none()
        reactivated = res is not None
    ws = str(inv["workspace_id"])
    await bs.log_event(db, ws, "payment_registered",
                       {"invoice_id": invoice_id, "amount": inv["amount_cop"], "method": method,
                        "days_late": max(0, (datetime.now(timezone.utc).date() - inv["due_date"]).days)},
                       str(inv["subscription_id"]) if inv["subscription_id"] else None)
    if reactivated:
        await bs.log_event(db, ws, "reactivated", {"invoice_id": invoice_id})
    return {"amount_cop": inv["amount_cop"], "reactivated": reactivated}


async def void_invoice(db, invoice_id: str, reason: Optional[str]) -> None:
    n = (await db.execute(
        text("""UPDATE billing_invoices SET status='void', notes=COALESCE(:r, notes), updated_at=NOW()
                WHERE id=:i AND status IN ('pending','overdue') RETURNING id"""),
        {"i": invoice_id, "r": reason},
    )).scalar_one_or_none()
    if not n:
        raise BillingError("Solo se anula una factura pendiente o vencida que exista.")


# ── Estado ───────────────────────────────────────────────────────────────────

async def pause(db, workspace_id: str, now: Optional[datetime] = None, reason: str = "manual") -> None:
    now = now or datetime.now(timezone.utc)
    sub = await get_live_subscription(db, workspace_id)
    days = (await bs.get_settings(db))["retention_days"]
    await db.execute(
        text("UPDATE subscriptions SET status='paused', paused_at=:n, data_purge_after=:p, updated_at=NOW() WHERE id=:id"),
        {"n": now, "p": now + timedelta(days=days), "id": sub["id"]},
    )
    await bs.log_event(db, workspace_id, "paused", {"reason": reason}, str(sub["id"]))


async def reactivate(db, workspace_id: str) -> None:
    """Reactivación manual sin pago (cortesía). Con pago se reactiva sola al registrarlo."""
    sub = await get_live_subscription(db, workspace_id)
    if sub["status"] not in ("paused", "past_due"):
        raise BillingError("Solo se reactiva un negocio pausado o en mora.")
    await db.execute(
        text("""UPDATE subscriptions SET status='active', past_due_since=NULL, paused_at=NULL, data_purge_after=NULL,
                updated_at=NOW() WHERE id=:id"""),
        {"id": sub["id"]},
    )
    await bs.log_event(db, workspace_id, "reactivated", {"reason": "manual"}, str(sub["id"]))


async def request_cancel(db, workspace_id: str, undo: bool = False) -> dict:
    """La cancelación tiene efecto al final del ciclo pagado: el servicio sigue hasta esa fecha."""
    sub = await get_live_subscription(db, workspace_id)
    if sub["status"] not in ("active", "past_due", "trial"):
        raise BillingError("Este negocio no tiene un plan que cancelar.")
    await db.execute(
        text("UPDATE subscriptions SET cancel_at_period_end=:c, updated_at=NOW() WHERE id=:id"),
        {"c": not undo, "id": sub["id"]},
    )
    if not undo:
        # Si ya se había generado el cobro del ciclo siguiente y no lo pagó, deja de deberse. Al deshacer, el worker
        # lo vuelve a generar cuando toque.
        today = datetime.now(timezone.utc).astimezone(_tz(sub["tz"])).date()
        await db.execute(
            text("""UPDATE billing_invoices SET status='void', notes='Cancelación pedida', updated_at=NOW()
                    WHERE subscription_id=:s AND kind='cycle' AND status='pending' AND period_start > :today"""),
            {"s": sub["id"], "today": today},
        )
    await bs.log_event(db, workspace_id, "cancel_reverted" if undo else "cancel_requested", {}, str(sub["id"]))
    return {"cancel_at_period_end": not undo}


async def mark_cancelled(db, workspace_id: str) -> None:
    """Fin del ciclo pagado de una cancelación pedida (lo llama el worker)."""
    sub = await get_live_subscription(db, workspace_id)
    days = (await bs.get_settings(db))["retention_days"]
    await db.execute(
        text("""UPDATE subscriptions SET status='cancelled', updated_at=NOW(), data_purge_after=NOW() + make_interval(days => :d)
                WHERE id=:id"""),
        {"id": sub["id"], "d": days},
    )
    await bs.log_event(db, workspace_id, "cancelled", {}, str(sub["id"]))


# ── Cambios de plan ──────────────────────────────────────────────────────────

async def preview_plan_change(db, workspace_id: str, new_code: str, now: Optional[datetime] = None) -> dict:
    """Qué pasaría al cambiar de plan: si sube, cuánto paga hoy por los días que quedan; si baja, qué le falta cumplir."""
    now = now or datetime.now(timezone.utc)
    sub = await get_live_subscription(db, workspace_id)
    new = await _plan(db, new_code)
    if new["id"] == sub["billing_plan_id"]:
        raise BillingError("El negocio ya está en ese plan.")
    ent = await bs.get_entitlements(db, workspace_id, now)
    today = now.astimezone(_tz(sub["tz"])).date()
    start, end = bs.cycle_bounds(sub["cycle_anchor_day"] or today.day, today)
    cycle_days, left = (end - start).days, (end - today).days
    discounted = sub["discount_cycles_remaining"] > 0
    cur_price = (sub["launch_price_cop"] if discounted and sub["launch_price_cop"] is not None
                 else sub.get("frozen_price_cop") or sub["plan_price_cop"])
    new_price = new["launch_price_cop"] if discounted and new["launch_price_cop"] is not None else new["price_cop"]
    is_upgrade = new_price > cur_price
    in_trial = sub["status"] == "trial"  # en la prueba no se cobra nada y el cambio vale de una vez
    now_applies = is_upgrade or in_trial
    out = {"direction": "up" if is_upgrade else "down", "from_plan": sub["plan_code"], "to_plan": new_code,
           "applies": "now" if now_applies else "next_cycle", "effective_date": today if now_applies else end,
           "charge_now_cop": bs.prorate_upgrade(cur_price, new_price, left, cycle_days) if is_upgrade and not in_trial else 0,
           "next_cycle_price_cop": bs.price_for_cycle(new["price_cop"], new["launch_price_cop"],
                                                      sub["discount_cycles_remaining"], None),
           "keeps_discount_cycles": sub["discount_cycles_remaining"], "blockers": []}
    if not is_upgrade:
        if ent.professionals_active > new["max_professionals"]:
            out["blockers"].append(f"Tiene {ent.professionals_active} profesionales y el plan {new['name']} permite {new['max_professionals']}.")
        if ent.used_appointments > new["max_appointments"]:
            out["blockers"].append(f"Ya usó {ent.used_appointments} citas este ciclo y el plan {new['name']} incluye {new['max_appointments']}.")
    return out


async def change_plan(db, workspace_id: str, new_code: str, actor_user_id: Optional[str],
                      now: Optional[datetime] = None) -> dict:
    """Subir: inmediato, con una factura de prorrateo. Bajar: se agenda para el siguiente ciclo y solo si cumple
    los límites del plan menor. En los dos casos conserva los ciclos de descuento que le falten."""
    now = now or datetime.now(timezone.utc)
    prev = await preview_plan_change(db, workspace_id, new_code, now)
    sub = await get_live_subscription(db, workspace_id)
    new = await _plan(db, new_code)
    if prev["direction"] == "down" and prev["blockers"]:
        raise BillingError("No cumple los límites del plan menor: " + " ".join(prev["blockers"]))
    if prev["applies"] == "next_cycle":
        await db.execute(text("UPDATE subscriptions SET pending_plan_id=:p, updated_at=NOW() WHERE id=:id"),
                         {"p": new["id"], "id": sub["id"]})
    else:
        await db.execute(
            text("UPDATE subscriptions SET billing_plan_id=:p, pending_plan_id=NULL, updated_at=NOW() WHERE id=:id"),
            {"p": new["id"], "id": sub["id"]})
        if prev["charge_now_cop"] > 0:
            today = prev["effective_date"]
            _, end = bs.cycle_bounds(sub["cycle_anchor_day"] or today.day, today)
            inv = str((await db.execute(
                text("""
                INSERT INTO billing_invoices (workspace_id, subscription_id, kind, period_start, period_end, due_date, amount_cop)
                VALUES (:w, :s, 'proration', :ps, :pe, :ps, :a) RETURNING id
                """),
                {"w": workspace_id, "s": sub["id"], "ps": today, "pe": end, "a": prev["charge_now_cop"]},
            )).scalar_one())
            await db.execute(
                text("""INSERT INTO billing_invoice_lines (invoice_id, kind, description, quantity, amount_cop)
                        VALUES (:i, 'proration', :d, 1, :a)"""),
                {"i": inv, "d": f"Cambio de plan {sub['plan_code']} → {new_code}, días restantes del ciclo",
                 "a": prev["charge_now_cop"]},
            )
            prev["invoice_id"] = inv
    await bs.log_event(db, workspace_id, "plan_changed",
                       {"from": prev["from_plan"], "to": new_code, "direction": prev["direction"],
                        "applies": prev["applies"], "by": actor_user_id}, str(sub["id"]))
    return prev


# ── Citas adicionales y fundadores ───────────────────────────────────────────

ADDON_PRICE_PER_APPOINTMENT = 500  # [Propuesta] del documento: sin descuento de lanzamiento
ADDON_BLOCKS = (50, 100, 200, 300)  # bloques de citas adicionales que se ofrecen (documento de planes §5)


async def add_addon(db, workspace_id: str, kind: str, quantity: int, actor_user_id: Optional[str],
                    now: Optional[datetime] = None) -> dict:
    """`appointments_block`: vale desde el siguiente ciclo y se repite hasta quitarlo.
    `appointments_topup`: recarga puntual, vale desde hoy y vence al cierre del ciclo."""
    if kind not in ("appointments_block", "appointments_topup"):
        raise BillingError("Tipo de adicional no válido.")
    now = now or datetime.now(timezone.utc)
    sub = await get_live_subscription(db, workspace_id)
    today = now.astimezone(_tz(sub["tz"])).date()
    start, end = bs.cycle_bounds(sub["cycle_anchor_day"] or today.day, today)
    price = quantity * ADDON_PRICE_PER_APPOINTMENT
    valid_from, valid_until = (end, None) if kind == "appointments_block" else (today, end)
    row_id = str((await db.execute(
        text("""
        INSERT INTO subscription_addons (subscription_id, workspace_id, kind, quantity, price_cop, valid_from, valid_until, created_by)
        VALUES (:s, :w, :k, :q, :p, :vf, :vu, :by) RETURNING id
        """),
        {"s": sub["id"], "w": workspace_id, "k": kind, "q": quantity, "p": price, "vf": valid_from, "vu": valid_until,
         "by": actor_user_id},
    )).scalar_one())
    await bs.log_event(db, workspace_id, "addon_added",
                       {"kind": kind, "quantity": quantity, "price": price}, str(sub["id"]))
    return {"id": row_id, "price_cop": price, "valid_from": valid_from, "valid_until": valid_until}


async def request_extra_appointments(db, workspace_id: str, quantity: int, actor_user_id: Optional[str],
                                     now: Optional[datetime] = None) -> dict:
    """El dueño pide más citas para el ciclo en curso: se acreditan YA y queda un saldo pendiente de pago.

    Es una recarga puntual (`appointments_topup`, $500 por cita, sin descuento): vale desde hoy y vence al cierre del
    ciclo. Crea de una vez el cobro pendiente (factura `proration` con una línea de citas) que vence en 7 días, o al
    cierre del ciclo si llega antes; el super_admin lo confirma como cualquier otro pago.

    Topes para que no sea una línea de crédito abierta: solo planes activos (la prueba no paga extras), solo bloques de
    la oferta y **una sola solicitud sin pagar a la vez**. Si el cobro vence sin pago, el ciclo de mora de siempre
    (aviso, gracia, pausa) aplica sin cambios.
    """
    if quantity not in ADDON_BLOCKS:
        raise BillingError(f"Elige un bloque de {', '.join(str(b) for b in ADDON_BLOCKS)} citas.")
    now = now or datetime.now(timezone.utc)
    ent = await bs.get_entitlements(db, workspace_id, now)
    if not ent.has_subscription:
        raise BillingNotFound("Este negocio no tiene un plan asignado: no tiene límite de citas que ampliar.")
    if ent.status != "active":
        raise BillingError("Las citas adicionales se piden con el plan activo. "
                           "Activa tu plan o ponte al día con tus pagos y vuelve a intentarlo.")
    open_request = (await db.execute(
        text("""
        SELECT 1 FROM billing_invoices i
        WHERE i.workspace_id = :w AND i.kind = 'proration' AND i.status IN ('pending','overdue')
          AND EXISTS (SELECT 1 FROM billing_invoice_lines l WHERE l.invoice_id = i.id AND l.kind = 'appointments')
        LIMIT 1
        """),
        {"w": workspace_id},
    )).scalar_one_or_none()
    if open_request:
        raise BillingError("Ya tienes una solicitud de citas adicionales pendiente de pago. "
                           "Págala y podrás pedir más.")

    sub = await get_live_subscription(db, workspace_id)
    addon = await add_addon(db, workspace_id, "appointments_topup", quantity, actor_user_id, now)
    today = now.astimezone(_tz(sub["tz"])).date()
    end = addon["valid_until"]
    due = min(end, today + timedelta(days=7))
    amount = addon["price_cop"]
    inv = str((await db.execute(
        text("""
        INSERT INTO billing_invoices (workspace_id, subscription_id, kind, period_start, period_end, due_date, amount_cop)
        VALUES (:w, :s, 'proration', :ps, :pe, :due, :a) RETURNING id
        """),
        {"w": workspace_id, "s": sub["id"], "ps": today, "pe": end, "due": due, "a": amount},
    )).scalar_one())
    await db.execute(
        text("""INSERT INTO billing_invoice_lines (invoice_id, kind, description, quantity, amount_cop)
                VALUES (:i, 'appointments', :d, :q, :a)"""),
        {"i": inv, "d": f"Recarga de {quantity} citas adicionales (vencen el {end.isoformat()})", "q": quantity, "a": amount},
    )
    await bs.log_event(db, workspace_id, "extra_appointments_requested",
                       {"invoice_id": inv, "quantity": quantity, "amount": amount, "due_date": due.isoformat()},
                       str(sub["id"]))
    return {"invoice_id": inv, "quantity": quantity, "amount_cop": amount, "due_date": due, "valid_until": end}


async def remove_addon(db, workspace_id: str, addon_id: str, now: Optional[datetime] = None) -> None:
    """Quita el bloque para el ciclo siguiente: sigue valiendo hasta el cierre del ciclo en curso."""
    now = now or datetime.now(timezone.utc)
    sub = await get_live_subscription(db, workspace_id)
    today = now.astimezone(_tz(sub["tz"])).date()
    _, end = bs.cycle_bounds(sub["cycle_anchor_day"] or today.day, today)
    n = (await db.execute(
        text("""UPDATE subscription_addons SET valid_until = GREATEST(valid_from, :end)
                WHERE id = :i AND workspace_id = :w AND (valid_until IS NULL OR valid_until > :end) RETURNING id"""),
        {"i": addon_id, "w": workspace_id, "end": end},
    )).scalar_one_or_none()
    if not n:
        raise BillingNotFound("El adicional no existe o ya está terminado.")
    await bs.log_event(db, workspace_id, "addon_removed", {"addon_id": addon_id}, str(sub["id"]))


async def grant_founder(db, workspace_id: str) -> dict:
    """Marca al negocio como fundador (valor real congelado). Respeta el cupo de `platform_settings.founder_cap`."""
    sub = await get_live_subscription(db, workspace_id)
    if sub["is_founder"]:
        raise BillingError("El negocio ya es fundador.")
    cap = (await bs.get_settings(db))["founder_cap"]
    if cap <= 0:
        raise BillingError("Define primero el cupo de fundadores (founder_cap).")
    taken = int((await db.execute(text("SELECT COUNT(*) FROM subscriptions WHERE is_founder"))).scalar_one() or 0)
    if taken >= cap:
        raise BillingError(f"El cupo de fundadores ({cap}) está completo.")
    number = int((await db.execute(
        text("SELECT COALESCE(MAX(founder_number), 0) + 1 FROM subscriptions"))).scalar_one())
    await db.execute(
        text("UPDATE subscriptions SET is_founder=TRUE, founder_number=:n, frozen_price_cop=:p, updated_at=NOW() WHERE id=:id"),
        {"n": number, "p": sub["plan_price_cop"], "id": sub["id"]},
    )
    await bs.log_event(db, workspace_id, "founder_granted", {"number": number}, str(sub["id"]))
    return {"founder_number": number, "frozen_price_cop": sub["plan_price_cop"]}


# ── Vistas ───────────────────────────────────────────────────────────────────

def _money_next_cycle(sub: dict) -> int:
    """Lo que paga el plan en el próximo ciclo (sin adicionales): descuento de lanzamiento si le quedan ciclos."""
    return bs.price_for_cycle(sub["plan_price_cop"], sub["launch_price_cop"],
                              sub["discount_cycles_remaining"], sub.get("frozen_price_cop"))


async def list_invoices(db, workspace_id: str, limit: int = 24) -> list[dict]:
    rows = (await db.execute(
        text("""
        SELECT id, kind, period_start, period_end, due_date, amount_cop, status, paid_at, payment_method,
               payment_reference, document_number, document_issued_at, last_sent_at, last_sent_to, send_count, created_at
        FROM billing_invoices WHERE workspace_id = :w AND status <> 'void'
        ORDER BY period_start DESC, created_at DESC LIMIT :l
        """),
        {"w": workspace_id, "l": limit},
    )).mappings().fetchall()
    return [dict(r) for r in rows]


async def workspace_billing_view(db, workspace_id: str, now: Optional[datetime] = None) -> dict:
    """Todo lo que el dueño (y el admin) necesita ver de su plan: estado, uso, próximo cobro y facturas."""
    ent = await bs.get_entitlements(db, workspace_id, now)
    base = {"has_subscription": ent.has_subscription, "status": ent.status, "serving": ent.serving}
    if not ent.has_subscription:
        return base
    sub = await get_live_subscription(db, workspace_id)
    profile = (await db.execute(
        text("SELECT 1 FROM billing_profiles WHERE workspace_id = :w"), {"w": workspace_id},
    )).scalar_one_or_none()
    pending = pending_name = None
    if sub.get("pending_plan_id"):
        row = (await db.execute(
            text("SELECT code, name FROM billing_plans WHERE id = :p"), {"p": sub["pending_plan_id"]},
        )).mappings().fetchone()
        if row:
            pending, pending_name = row["code"], row["name"]
    return {
        **base,
        "plan": {"code": ent.plan_code, "name": ent.plan_name, "price_cop": sub["plan_price_cop"],
                 "launch_price_cop": sub["launch_price_cop"]},
        "trial_ends_at": ent.trial_ends_at,
        "cycle_start": ent.cycle_start, "cycle_end": ent.cycle_end,
        "next_cycle_plan_price_cop": _money_next_cycle(sub) if sub.get("activated_at") else None,
        "discount_cycles_remaining": sub["discount_cycles_remaining"],
        "is_founder": sub["is_founder"], "founder_number": sub["founder_number"],
        "cancel_at_period_end": sub["cancel_at_period_end"], "pending_plan": pending, "pending_plan_name": pending_name,
        "appointments": {"included": ent.included_appointments, "extra": ent.extra_appointments,
                         "total": ent.total_appointments, "used": ent.used_appointments,
                         "remaining": ent.remaining_appointments, "level": ent.quota_level,
                         "can_book": ent.can_book},
        "professionals": {"limit": ent.professionals_limit, "active": ent.professionals_active,
                          "extra": ent.extra_professionals,
                          "extra_price_cop": sub["extra_professional_price_cop"]},
        "profile_complete": bool(profile),
        "invoices": await list_invoices(db, workspace_id),
    }


async def workspace_usage_view(db, workspace_id: str, now: Optional[datetime] = None) -> dict:
    """Saldo de citas del asistente y de profesionales, para todo el equipo.

    A diferencia de `workspace_billing_view` (solo el dueño) no trae precios, facturas ni datos de cobro:
    cualquier miembro puede ver cuánto lleva consumido el negocio.
    """
    ent = await bs.get_entitlements(db, workspace_id, now)
    base = {"has_subscription": ent.has_subscription, "status": ent.status, "serving": ent.serving}
    if not ent.has_subscription:
        return base
    return {
        **base,
        "plan_name": ent.plan_name,
        "cycle_end": ent.cycle_end,
        "appointments": {"included": ent.included_appointments, "extra": ent.extra_appointments,
                         "total": ent.total_appointments, "used": ent.used_appointments,
                         "remaining": ent.remaining_appointments, "level": ent.quota_level,
                         "can_book": ent.can_book},
        "professionals": {"limit": ent.professionals_limit, "active": ent.professionals_active,
                          "extra": ent.extra_professionals},
    }
