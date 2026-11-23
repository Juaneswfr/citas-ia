"""
Planes de Zumit: tablero de estadísticas por plan y edición con vista previa del impacto.

Solo lectura salvo `update_plan`. Cada plan se identifica por su `code` (`emprendedor`, `equipo`); el código no se edita:
lo usa el resto del sistema (la prueba arranca en `emprendedor`, las rutas validan el código).

**Qué pasa al cambiar un plan** (lo que `preview` calcula y la pantalla muestra antes de aplicar):
- Un precio nuevo rige en el PRÓXIMO cobro de cada negocio: las facturas ya emitidas no cambian. El fundador con valor
  congelado (`frozen_price_cop`) no se ve afectado, salvo por el precio de lanzamiento mientras le queden ciclos con descuento.
- Un límite menor rige YA: el cupo de citas y de profesionales se calcula en vivo con el plan. Un negocio que ya pasó el nuevo
  límite aparece en la vista previa.
- Los términos piden avisar 30 días antes de subir precios (documentation/zumit-plan-de-pagos-y-sus.md §13).
"""
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text

from integrations import langsmith_costs as ls
from services import billing_costs
from services import billing_metrics as bm
from services import billing_service as bs
from services.subscription_service import (
    ADDON_BLOCKS, ADDON_PRICE_PER_APPOINTMENT, BillingError, BillingNotFound, PLAN_FOR_TRIAL,
)

log = logging.getLogger(__name__)

LIVE = ("trial", "active", "past_due", "paused")
SERVING = ("trial", "active", "past_due")
PAYING = ("active", "past_due")
STATUSES = ("trial", "active", "past_due", "paused", "cancelled", "expired")
USAGE_BUCKETS = ("0_25", "25_50", "50_80", "80_100", "mas_100")

# Campos editables y su tope. El código del plan no se edita.
EDITABLE = ("name", "description", "price_cop", "launch_price_cop", "max_appointments", "max_professionals",
            "extra_professional_price_cop", "is_active")


# ── Cuentas puras ────────────────────────────────────────────────────────────

def week_start(day: date) -> date:
    """El lunes de la semana de `day`."""
    return day - timedelta(days=day.weekday())


def week_range(today: date, weeks: int) -> list[date]:
    """Los lunes de las últimas `weeks` semanas, de la más antigua a la actual."""
    first = week_start(today) - timedelta(days=7 * (weeks - 1))
    return [first + timedelta(days=7 * i) for i in range(weeks)]


def fill_weeks(rows: list[dict], monday_list: list[date]) -> list[dict]:
    """Una fila por semana (con ceros donde no hubo nada): [{week, total, by_plan:{código: n}}]."""
    by_week: dict[date, dict[str, int]] = {m: {} for m in monday_list}
    for r in rows:
        week = r["week"]
        if week in by_week:
            code = r["plan"] or "otro"
            by_week[week][code] = by_week[week].get(code, 0) + int(r["n"])
    return [{"week": m, "total": sum(by_week[m].values()), "by_plan": by_week[m]} for m in monday_list]


def effective_price(plan: dict, discount_cycles_remaining: int, frozen: Optional[int]) -> int:
    """Lo que paga un negocio por el plan en el ciclo que viene (mismo criterio que la factura)."""
    return bs.price_for_cycle(plan["price_cop"], plan["launch_price_cop"], discount_cycles_remaining, frozen)


class PlanError(BillingError):
    """El cambio pedido a un plan no es válido."""


def validate_changes(current: dict, changes: dict) -> dict:
    """Los cambios ya limpios, o `PlanError` en español. Solo acepta campos de `EDITABLE`."""
    unknown = set(changes) - set(EDITABLE)
    if unknown:
        raise PlanError(f"No se puede editar: {', '.join(sorted(unknown))}.")
    out = dict(changes)
    for key in ("name", "description"):
        if key in out and out[key] is not None:
            out[key] = out[key].strip()
    if "name" in out and len(out["name"] or "") < 2:
        raise PlanError("El nombre del plan necesita al menos 2 letras.")
    if "description" in out and not out["description"]:
        out["description"] = None
    price = out.get("price_cop", current["price_cop"])
    launch = out["launch_price_cop"] if "launch_price_cop" in out else current["launch_price_cop"]
    if launch is not None and launch > price:
        raise PlanError("El precio de lanzamiento no puede ser mayor que el precio normal.")
    if "is_active" in out and out["is_active"] is False and current["is_active"]:
        if current["code"] == PLAN_FOR_TRIAL:
            raise PlanError(f"El plan «{current['name']}» no se puede desactivar: es donde empieza la prueba de cada negocio nuevo.")
    # solo cuenta lo que de verdad cambia
    return {k: v for k, v in out.items() if v != current.get(k)}


def _uuid(plan_id: str) -> str:
    try:
        return str(uuid.UUID(str(plan_id)))
    except ValueError:
        raise BillingNotFound("El plan no existe.")


# ── Datos ────────────────────────────────────────────────────────────────────

async def _plans(db) -> list[dict]:
    """Los planes vigentes y los antiguos que aún tengan negocios."""
    rows = (await db.execute(text("""
        SELECT id, code, name, description, price_cop, launch_price_cop, max_appointments, max_professionals,
               extra_professional_price_cop, is_active
        FROM billing_plans
        WHERE code IS NOT NULL OR id IN (SELECT billing_plan_id FROM subscriptions WHERE status IN ('trial','active','past_due','paused'))
        ORDER BY (code IS NULL), price_cop, name"""))).mappings().fetchall()
    return [dict(r) for r in rows]


async def _latest_subs(db) -> list[dict]:
    rows = (await db.execute(text("""
        SELECT DISTINCT ON (s.workspace_id) s.id, s.workspace_id, s.billing_plan_id, s.status, s.activated_at,
               s.trial_started_at, s.cancel_at_period_end, s.discount_cycles_remaining, s.frozen_price_cop,
               s.is_founder, s.updated_at, w.name AS workspace
        FROM subscriptions s JOIN workspaces w ON w.id = s.workspace_id
        ORDER BY s.workspace_id, s.created_at DESC"""))).mappings().fetchall()
    return [dict(r) for r in rows]


def _empty_stats() -> dict:
    return {
        "subscribers": {s: 0 for s in STATUSES}, "paying": 0, "trials": 0,
        "mrr_plan_cop": 0, "mrr_list_cop": 0, "discount_cop": 0, "addons_cop": 0, "arpa_cop": 0,
        "usage": {"avg_pct": None, "near": 0, "blocked": 0, "distribution": {b: 0 for b in USAGE_BUCKETS}},
        "professionals": {"avg": None, "extra": 0},
        "cancelled_30d": 0, "cancelling": 0,
        "conversion": {"trials": 0, "converted": 0, "pct": None},
        "margin": {"revenue_cop": 0, "cost_cop": None, "margin_cop": None, "margin_pct": None},
    }


async def dashboard(db, days: int = 30, now: Optional[datetime] = None) -> dict:
    """Todo el tablero de planes: cada plan con su configuración y sus estadísticas, y las series para los gráficos."""
    days = max(7, min(days, 90))
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(ls.BOGOTA).date()
    plans = await _plans(db)
    by_id = {str(p["id"]): p for p in plans}
    stats = {pid: _empty_stats() for pid in by_id}
    addons = await bm._block_addons(db)
    usage_sum: dict[str, list[float]] = {pid: [] for pid in by_id}
    pros_sum: dict[str, list[int]] = {pid: [] for pid in by_id}

    for sub in await _latest_subs(db):
        pid = str(sub["billing_plan_id"])
        plan, st = by_id.get(pid), stats.get(pid)
        if not plan or st is None:
            continue
        status = sub["status"] if sub["status"] in STATUSES else None
        if status:
            st["subscribers"][status] += 1
        if status in PAYING:
            paid = effective_price(plan, sub["discount_cycles_remaining"], sub["frozen_price_cop"])
            full = sub["frozen_price_cop"] if sub["frozen_price_cop"] is not None else plan["price_cop"]
            st["paying"] += 1
            st["mrr_plan_cop"] += paid
            st["mrr_list_cop"] += full
            st["discount_cop"] += max(0, full - paid)
            st["addons_cop"] += addons.get(str(sub["id"]), 0)
        if status == "trial":
            st["trials"] += 1
        if status == "cancelled" and sub["updated_at"] and sub["updated_at"] >= now - timedelta(days=30):
            st["cancelled_30d"] += 1
        if status == "active" and sub["cancel_at_period_end"]:
            st["cancelling"] += 1
        if sub["trial_started_at"] and sub["trial_started_at"] >= now - timedelta(days=90):
            st["conversion"]["trials"] += 1
            st["conversion"]["converted"] += 1 if sub["activated_at"] else 0
        if status in SERVING and plan["max_appointments"]:
            ent = await bs.get_entitlements(db, str(sub["workspace_id"]), now)
            if ent.total_appointments:
                pct = ent.used_appointments * 100 / ent.total_appointments
                usage_sum[pid].append(pct)
                st["usage"]["distribution"][bm.usage_bucket(pct)] += 1
                if ent.quota_level in ("warn", "over", "blocked"):
                    st["usage"]["near"] += 1
                if ent.quota_level == "blocked":
                    st["usage"]["blocked"] += 1
            pros_sum[pid].append(ent.professionals_active)
            st["professionals"]["extra"] += ent.extra_professionals

    # margen por plan: el mismo cálculo de Costos (una sola fuente), agrupado por el plan actual de cada negocio
    costs = await billing_costs.costs(db, days, today)
    for item in costs["items"]:
        # por id y no por nombre: el nombre se puede cambiar (o repetirse en un plan antiguo); el id no
        plan = by_id.get(item.get("plan_id") or "")
        if not plan:
            continue
        m = stats[str(plan["id"])]["margin"]
        m["revenue_cop"] += item["revenue_cop"]
        if item["cost_cop"] is None:
            m["cost_cop"] = m["margin_cop"] = None
            m["_unknown"] = True
        elif not m.get("_unknown"):
            m["cost_cop"] = (m["cost_cop"] or 0) + item["cost_cop"]
            m["margin_cop"] = m["revenue_cop"] - m["cost_cop"]

    for pid, st in stats.items():
        paying = st["paying"]
        st["arpa_cop"] = round((st["mrr_plan_cop"] + st["addons_cop"]) / paying) if paying else 0
        if usage_sum[pid]:
            st["usage"]["avg_pct"] = round(sum(usage_sum[pid]) / len(usage_sum[pid]), 1)
        if pros_sum[pid]:
            st["professionals"]["avg"] = round(sum(pros_sum[pid]) / len(pros_sum[pid]), 1)
        c = st["conversion"]
        c["pct"] = bm.pct(c["converted"], c["trials"])
        m = st["margin"]
        m.pop("_unknown", None)
        m["margin_pct"] = round(m["margin_cop"] * 100 / m["revenue_cop"], 1) if m["margin_cop"] is not None and m["revenue_cop"] > 0 else None

    weeks = min(13, max(4, days // 7))
    mondays = week_range(today, weeks)
    since = datetime.combine(mondays[0], datetime.min.time(), tzinfo=ls.BOGOTA)
    events = (await db.execute(
        text("""
        SELECT (date_trunc('week', e.created_at AT TIME ZONE 'America/Bogota'))::date AS week,
               e.payload->>'plan' AS plan, COUNT(*) AS n
        FROM billing_events e WHERE e.type = 'activated' AND e.created_at >= :since
        GROUP BY 1, 2 ORDER BY 1"""),
        {"since": since},
    )).mappings().fetchall()

    paying_total = sum(s["paying"] for s in stats.values())
    mrr_total = sum(s["mrr_plan_cop"] + s["addons_cop"] for s in stats.values())
    return {
        "days": days, "since": costs["since"], "until": costs["until"], "usd_cop": costs["usd_cop"],
        "plans": [{**{k: v for k, v in p.items()}, "id": str(p["id"]), "stats": stats[str(p["id"])]} for p in plans],
        "series": {"activations_by_week": fill_weeks([dict(r) for r in events], mondays)},
        "totals": {
            "plans_active": sum(1 for p in plans if p["is_active"]), "paying": paying_total,
            "trials": sum(s["trials"] for s in stats.values()), "mrr_cop": mrr_total,
            "discount_cop": sum(s["discount_cop"] for s in stats.values()),
            "arpa_cop": round(mrr_total / paying_total) if paying_total else 0,
            "margin_cop": costs["totals"]["margin_cop"], "margin_pct": costs["totals"]["margin_pct"],
            "revenue_cop": costs["totals"]["revenue_cop"],
        },
    }


# ── Edición con vista previa ─────────────────────────────────────────────────

async def _get_plan(db, plan_id: str) -> dict:
    row = (await db.execute(text("""
        SELECT id, code, name, description, price_cop, launch_price_cop, max_appointments, max_professionals,
               extra_professional_price_cop, is_active FROM billing_plans WHERE id = :i"""),
        {"i": _uuid(plan_id)})).mappings().fetchone()
    if not row:
        raise BillingNotFound("El plan no existe.")
    return dict(row)


async def preview(db, plan_id: str, changes: dict, now: Optional[datetime] = None) -> dict:
    """Qué pasaría al aplicar `changes`: quién paga distinto desde su próximo cobro y quién ya pasó el nuevo límite.
    No cambia nada."""
    now = now or datetime.now(timezone.utc)
    plan = await _get_plan(db, plan_id)
    clean = validate_changes(plan, changes)
    if "name" in clean:
        taken = (await db.execute(
            text("SELECT 1 FROM billing_plans WHERE lower(name) = lower(:n) AND id <> :i LIMIT 1"),
            {"n": clean["name"], "i": str(plan["id"])},
        )).scalar_one_or_none()
        if taken:
            raise PlanError(f"Ya existe otro plan llamado «{clean['name']}». Cada plan necesita un nombre distinto.")
    new = {**plan, **clean}
    subs = [s for s in await _latest_subs(db) if str(s["billing_plan_id"]) == str(plan["id"]) and s["status"] in LIVE]

    delta, affected, protected, paying = 0, 0, 0, 0
    over_appointments, over_professionals = [], []
    for sub in subs:
        if sub["status"] in PAYING:
            paying += 1
            old = effective_price(plan, sub["discount_cycles_remaining"], sub["frozen_price_cop"])
            now_price = effective_price(new, sub["discount_cycles_remaining"], sub["frozen_price_cop"])
            if now_price != old:
                affected += 1
                delta += now_price - old
            elif sub["is_founder"] and ({"price_cop", "launch_price_cop"} & set(clean)):
                protected += 1
        if sub["status"] in SERVING and ({"max_appointments", "max_professionals"} & set(clean)):
            ent = await bs.get_entitlements(db, str(sub["workspace_id"]), now)
            if "max_appointments" in clean and ent.used_appointments > new["max_appointments"]:
                over_appointments.append({"workspace_id": str(sub["workspace_id"]), "workspace": sub["workspace"],
                                          "used": ent.used_appointments, "limit": new["max_appointments"]})
            if "max_professionals" in clean and ent.professionals_active > new["max_professionals"]:
                over_professionals.append({"workspace_id": str(sub["workspace_id"]), "workspace": sub["workspace"],
                                           "active": ent.professionals_active, "limit": new["max_professionals"]})

    warnings = []
    if "price_cop" in clean and clean["price_cop"] > plan["price_cop"]:
        warnings.append("Subes el precio: los términos piden avisar a los negocios 30 días antes. "
                        "Rige desde el próximo cobro de cada uno; lo ya facturado no cambia.")
    elif {"price_cop", "launch_price_cop"} & set(clean):
        warnings.append("El precio nuevo rige desde el próximo cobro de cada negocio; lo ya facturado no cambia.")
    if over_appointments or over_professionals:
        warnings.append("El límite menor rige ya: los negocios de abajo ya lo pasaron. El asistente seguirá agendando solo "
                        "dentro del margen de 20 citas; los profesionales de más se cobrarán como adicionales.")
    if clean.get("is_active") is False:
        warnings.append("Un plan desactivado deja de ofrecerse a negocios nuevos. Los que ya lo tienen siguen igual.")
    return {
        "plan_id": str(plan["id"]), "code": plan["code"], "has_changes": bool(clean),
        "changes": {k: {"from": plan[k], "to": v} for k, v in clean.items()},
        "subscribers": len(subs), "paying": paying,
        "price": {"affected": affected, "protected_founders": protected, "mrr_delta_cop": delta},
        "limits": {"over_appointments": over_appointments[:10], "over_professionals": over_professionals[:10]},
        "warnings": warnings,
    }


async def update_plan(db, plan_id: str, changes: dict, now: Optional[datetime] = None) -> dict:
    """Aplica los cambios y devuelve el plan nuevo junto con el impacto que tuvo (calculado antes de aplicar).

    No hace commit ni audita: lo hace el router. Desactivar un plan con negocios vivos no se permite.
    """
    plan = await _get_plan(db, plan_id)
    impact = await preview(db, plan_id, changes, now)
    clean = {k: v["to"] for k, v in impact["changes"].items()}
    if not clean:
        raise PlanError("No hay nada que cambiar: los valores son los mismos.")
    if clean.get("is_active") is False and impact["subscribers"] > 0:
        raise PlanError(f"No se puede desactivar: {impact['subscribers']} negocio(s) lo tienen. Muévelos de plan primero.")
    if "max_professionals" in clean:
        clean["max_calendars"] = clean["max_professionals"]  # columna heredada: se mantiene igual para no confundir
    # solo se asignan columnas de una lista fija (nunca nombres que vengan del cliente)
    allowed = EDITABLE + ("max_calendars",)
    sets = ", ".join(f"{col} = :{col}" for col in clean if col in allowed)
    row = (await db.execute(
        text(f"UPDATE billing_plans SET {sets}, updated_at = NOW() WHERE id = :_id RETURNING id, code, name, description, "
             "price_cop, launch_price_cop, max_appointments, max_professionals, extra_professional_price_cop, is_active"),
        {**{k: v for k, v in clean.items() if k in allowed}, "_id": str(plan["id"])},
    )).mappings().fetchone()
    return {"plan": {**dict(row), "id": str(row["id"])}, "before": {k: plan[k] for k in impact["changes"]},
            "impact": impact}


# ── Lo que ve la landing (público) ───────────────────────────────────────────

async def public_pricing(db) -> dict:
    """Los precios tal como se muestran en la landing: planes que se pueden vender y las reglas que los rodean.

    Es público: solo trae lo que ya se publica (nombre, precios, límites, días de prueba, cupo de fundadores, citas
    adicionales). Nada de negocios, ingresos ni estadísticas. Se calcula con los mismos datos que cobra el sistema, así la
    landing nunca promete un precio distinto al que se factura.
    """
    rows = (await db.execute(text("""
        SELECT code, name, description, price_cop, launch_price_cop, max_appointments, max_professionals,
               extra_professional_price_cop
        FROM billing_plans WHERE is_active = TRUE AND code IS NOT NULL ORDER BY price_cop, name"""))).mappings().fetchall()
    settings = await bs.get_settings(db)
    return {
        "plans": [dict(r) for r in rows],
        "trial_days": settings["trial_days"],
        "launch_discount_cycles": settings["launch_discount_cycles"],
        "founder_cap": settings["founder_cap"],
        "addons": {"appointment_price_cop": ADDON_PRICE_PER_APPOINTMENT, "blocks": list(ADDON_BLOCKS)},
    }
