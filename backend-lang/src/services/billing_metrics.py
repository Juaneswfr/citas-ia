"""
Métricas de facturación para el panel de plataforma (solo super_admin; cruza todos los negocios).

Responde cuatro preguntas: cuánto ingreso tengo y cuánto regalo en descuentos, de dónde vienen y dónde se caen los
negocios, quién me debe y a quién tengo que llamar (riesgo y oportunidad). Cuánto cuesta cada negocio y cuánto se gana
con él NO se calcula aquí sino en `billing_costs` (una sola fuente: dos cálculos darían dos márgenes distintos).

Las cuentas puras (cubetas, margen, MRR) van aparte de las consultas para poder probarlas sin BD.
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text

from services import billing_service as bs

log = logging.getLogger(__name__)

LIVE = ("trial", "active", "past_due", "paused")
PAYING = ("active", "past_due")


# ── Cuentas puras ────────────────────────────────────────────────────────────

def aging_bucket(days_overdue: int) -> str:
    if days_overdue <= 0:
        return "por_vencer"
    if days_overdue <= 5:
        return "1_5"
    if days_overdue <= 30:
        return "6_30"
    return "mas_30"


def usage_bucket(pct: float) -> str:
    if pct < 25:
        return "0_25"
    if pct < 50:
        return "25_50"
    if pct < 80:
        return "50_80"
    if pct <= 100:
        return "80_100"
    return "mas_100"


def subscription_money(sub: dict, block_addons_cop: int = 0) -> dict:
    """Lo que vale un negocio que paga: valor real, lo que paga este ciclo y lo que regala en descuento."""
    real = sub.get("frozen_price_cop") if sub.get("frozen_price_cop") is not None else sub["price_cop"]
    paying = bs.price_for_cycle(sub["price_cop"], sub["launch_price_cop"],
                                sub["discount_cycles_remaining"], sub.get("frozen_price_cop"))
    return {"list": real + block_addons_cop, "actual": paying + block_addons_cop, "discount": max(0, real - paying)}


def pct(part: int, whole: int) -> Optional[float]:
    return round(part * 100 / whole, 1) if whole else None


# ── Consultas ────────────────────────────────────────────────────────────────

async def _latest_subscriptions(db) -> list[dict]:
    rows = (await db.execute(text("""
        SELECT DISTINCT ON (s.workspace_id)
               s.id, s.workspace_id, s.status, s.trial_ends_at, s.trial_started_at, s.activated_at, s.past_due_since,
               s.cycle_anchor_day, s.discount_cycles_remaining, s.frozen_price_cop, s.is_founder, s.founder_number,
               s.cancel_at_period_end, s.created_at, p.code AS plan_code, p.name AS plan_name, p.price_cop,
               p.launch_price_cop, w.name AS workspace_name, w.timezone AS tz,
               (SELECT u.email FROM workspace_members m JOIN users u ON u.id = m.user_id
                 WHERE m.workspace_id = w.id AND m.member_role = 'workspace_owner'
                 ORDER BY m.created_at LIMIT 1) AS owner_email
        FROM subscriptions s
        JOIN billing_plans p ON p.id = s.billing_plan_id
        JOIN workspaces w ON w.id = s.workspace_id
        ORDER BY s.workspace_id, s.created_at DESC
    """))).mappings().fetchall()
    return [dict(r) for r in rows]


async def _block_addons(db) -> dict:
    rows = (await db.execute(text("""
        SELECT subscription_id, SUM(price_cop) AS total FROM subscription_addons
        WHERE kind = 'appointments_block' AND valid_from <= CURRENT_DATE
          AND (valid_until IS NULL OR valid_until > CURRENT_DATE)
        GROUP BY subscription_id
    """))).mappings().fetchall()
    return {str(r["subscription_id"]): int(r["total"]) for r in rows}


async def _income(db, subs: list[dict]) -> dict:
    addons = await _block_addons(db)
    total = {"mrr_list": 0, "mrr_actual": 0, "discount_given": 0, "paying": 0}
    blocks = 0
    by_plan: dict[str, dict] = {}
    for s in subs:
        if s["status"] not in PAYING:
            continue
        block = addons.get(str(s["id"]), 0)
        blocks += block
        m = subscription_money(s, block)
        total["mrr_list"] += m["list"]
        total["mrr_actual"] += m["actual"]
        total["discount_given"] += m["discount"]
        total["paying"] += 1
        row = by_plan.setdefault(s["plan_code"], {"plan": s["plan_name"], "negocios": 0, "mrr_actual": 0})
        row["negocios"] += 1
        row["mrr_actual"] += m["actual"]
    return {**total, "arpa": round(total["mrr_actual"] / total["paying"]) if total["paying"] else 0,
            "addons_mrr": blocks, "by_plan": list(by_plan.values())}


async def _funnel(db, days: int, sandbox_phone_id: str) -> dict:
    row = (await db.execute(text("""
        SELECT count(*) AS registered,
          count(*) FILTER (WHERE EXISTS (SELECT 1 FROM subscriptions s WHERE s.workspace_id = w.id AND s.trial_started_at IS NOT NULL)) AS trial,
          count(*) FILTER (WHERE EXISTS (SELECT 1 FROM channels c WHERE c.workspace_id = w.id AND c.status = 'active'
                                           AND c.phone_number_id <> :sandbox)) AS connected,
          count(*) FILTER (WHERE EXISTS (SELECT 1 FROM subscriptions s WHERE s.workspace_id = w.id AND s.activated_at IS NOT NULL)) AS activated,
          count(*) FILTER (WHERE EXISTS (SELECT 1 FROM billing_invoices i WHERE i.workspace_id = w.id AND i.status = 'paid')) AS paid,
          AVG(EXTRACT(EPOCH FROM (SELECT min(s.activated_at) FROM subscriptions s WHERE s.workspace_id = w.id) - w.created_at) / 86400.0) AS days_to_activate
        FROM workspaces w
        WHERE w.created_at >= NOW() - make_interval(days => :d)
    """), {"d": days, "sandbox": sandbox_phone_id})).mappings().fetchone() or {}
    reg = int(row.get("registered") or 0)
    steps = [("registered", "Se registraron", reg)]
    for key, label in (("trial", "Empezaron la prueba"), ("connected", "Conectaron su número"),
                       ("activated", "Se activaron"), ("paid", "Pagaron")):
        steps.append((key, label, int(row.get(key) or 0)))
    d = row.get("days_to_activate")
    return {"days": days,
            "steps": [{"key": k, "label": l, "count": n, "pct_of_registered": pct(n, reg)} for k, l, n in steps],
            "avg_days_to_activate": round(float(d), 1) if d is not None else None}


async def _expiring_trials(db, subs: list[dict], now: datetime) -> list[dict]:
    out = [{"workspace_id": str(s["workspace_id"]), "workspace": s["workspace_name"], "owner_email": s["owner_email"],
            "trial_ends_at": s["trial_ends_at"]}
           for s in subs if s["status"] == "trial" and s["trial_ends_at"] and now <= s["trial_ends_at"] <= now + timedelta(days=7)]
    return sorted(out, key=lambda r: r["trial_ends_at"])


async def _collections(db) -> dict:
    rows = (await db.execute(text("""
        SELECT i.id, i.workspace_id, w.name AS workspace, i.amount_cop, i.due_date, i.status, i.kind,
               (CURRENT_DATE - i.due_date) AS days_overdue
        FROM billing_invoices i JOIN workspaces w ON w.id = i.workspace_id
        WHERE i.status IN ('pending','overdue')
        ORDER BY i.due_date
    """))).mappings().fetchall()
    buckets = {k: {"count": 0, "amount_cop": 0} for k in ("por_vencer", "1_5", "6_30", "mas_30")}
    overdue = []
    for r in rows:
        b = aging_bucket(int(r["days_overdue"]))
        buckets[b]["count"] += 1
        buckets[b]["amount_cop"] += r["amount_cop"]
        if b != "por_vencer":
            overdue.append({"invoice_id": str(r["id"]), "workspace_id": str(r["workspace_id"]), "workspace": r["workspace"],
                            "amount_cop": r["amount_cop"], "days_overdue": int(r["days_overdue"])})
    flow = (await db.execute(text("""
        SELECT
          COALESCE(SUM(amount_cop) FILTER (WHERE created_at >= NOW() - interval '30 days' AND status <> 'void'), 0) AS billed_30d,
          COALESCE(SUM(amount_cop) FILTER (WHERE paid_at >= NOW() - interval '30 days' AND status = 'paid'), 0) AS collected_30d,
          AVG(paid_at::date - due_date) FILTER (WHERE status = 'paid' AND paid_at >= NOW() - interval '90 days') AS avg_days_to_pay
        FROM billing_invoices
    """))).mappings().fetchone() or {}
    billed, collected = int(flow.get("billed_30d") or 0), int(flow.get("collected_30d") or 0)
    avg = flow.get("avg_days_to_pay")
    return {"aging": buckets, "overdue": overdue[:20], "billed_30d": billed, "collected_30d": collected,
            "collection_rate_pct": pct(collected, billed), "avg_days_to_pay": round(float(avg), 1) if avg is not None else None}


async def _usage_for_cycles(db, workspace_id: str, anchor: int, today: date, tz_name: str, cycles_back: int) -> list[int]:
    """Citas del asistente en los `cycles_back` ciclos completos anteriores al actual (el más reciente primero)."""
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(tz_name or bs.DEFAULT_TZ)
    out, ref = [], bs.cycle_bounds(anchor, today)[0]
    for _ in range(cycles_back):
        start, end = bs.cycle_bounds(anchor, ref - timedelta(days=1))
        n = (await db.execute(text("""
            SELECT COUNT(*) FROM appointments WHERE workspace_id = :w AND created_by IS NULL
              AND created_at >= :s AND created_at < :e
        """), {"w": workspace_id, "s": bs._local_midnight(start, tz), "e": bs._local_midnight(end, tz)})).scalar_one()
        out.append(int(n or 0))
        ref = start
    return out


async def _risk_and_opportunity(db, subs: list[dict], now: datetime, settings: dict) -> dict:
    buckets = {k: 0 for k in ("0_25", "25_50", "50_80", "80_100", "mas_100")}
    near, low, upsell_pros = [], [], []
    for s in subs:
        if s["status"] not in ("trial", "active", "past_due") or not s.get("plan_code"):
            continue
        ent = await bs.get_entitlements(db, str(s["workspace_id"]), now)
        if ent.total_appointments:
            p = ent.used_appointments * 100 / ent.total_appointments
            buckets[usage_bucket(p)] += 1
            if ent.quota_level != "ok":
                near.append({"workspace_id": str(s["workspace_id"]), "workspace": s["workspace_name"],
                             "plan": s["plan_name"], "used": ent.used_appointments, "total": ent.total_appointments,
                             "pct": round(p), "level": ent.quota_level})
        if ent.extra_professionals:
            upsell_pros.append({"workspace_id": str(s["workspace_id"]), "workspace": s["workspace_name"],
                                "professionals": ent.professionals_active, "limit": ent.professionals_limit})
        if s["status"] == "active" and s["activated_at"] and ent.included_appointments:
            from zoneinfo import ZoneInfo
            today = now.astimezone(ZoneInfo(s["tz"] or bs.DEFAULT_TZ)).date()
            past = await _usage_for_cycles(db, str(s["workspace_id"]), s["cycle_anchor_day"] or s["activated_at"].day,
                                           today, s["tz"], 2)
            full_cycles = (now - s["activated_at"]).days >= 60
            if full_cycles and all(n * 100 < ent.included_appointments * settings["low_usage_pct"] for n in past):
                low.append({"workspace_id": str(s["workspace_id"]), "workspace": s["workspace_name"],
                            "plan": s["plan_name"], "last_cycles": past, "included": ent.included_appointments})
    cliff = (await db.execute(text("""
        SELECT s.workspace_id, w.name AS workspace, p.name AS plan, p.price_cop, p.launch_price_cop
        FROM subscriptions s
        JOIN billing_plans p ON p.id = s.billing_plan_id
        JOIN workspaces w ON w.id = s.workspace_id
        WHERE s.status = 'active' AND s.discount_cycles_remaining = 0 AND NOT s.is_founder
          AND EXISTS (
              SELECT 1 FROM billing_invoice_lines l
              JOIN billing_invoices i ON i.id = l.invoice_id
              WHERE i.subscription_id = s.id AND i.kind = 'cycle' AND l.kind = 'plan'
                AND l.description LIKE '%lanzamiento%'
                AND i.period_start = (SELECT max(i2.period_start) FROM billing_invoices i2
                                       WHERE i2.subscription_id = s.id AND i2.kind = 'cycle' AND i2.status <> 'void'))
    """))).mappings().fetchall()
    churn = (await db.execute(text("""
        SELECT count(DISTINCT workspace_id) FROM billing_events
        WHERE type IN ('cancel_requested','cancelled') AND created_at >= NOW() - interval '30 days'
    """))).scalar_one()
    return {
        "usage_distribution": buckets,
        "near_quota": sorted(near, key=lambda r: -r["pct"])[:20],
        "extra_professionals": upsell_pros[:20],
        "low_usage": low[:20],
        "discount_cliff": [{"workspace_id": str(r["workspace_id"]), "workspace": r["workspace"], "plan": r["plan"],
                            "from_cop": r["launch_price_cop"], "to_cop": r["price_cop"]} for r in cliff],
        "cancellations_30d": int(churn or 0),
    }


async def _founders(db, subs: list[dict], settings: dict) -> dict:
    items = sorted([{"workspace_id": str(s["workspace_id"]), "workspace": s["workspace_name"], "number": s["founder_number"]}
                    for s in subs if s["is_founder"]], key=lambda r: r["number"] or 0)
    return {"cap": settings["founder_cap"], "taken": len(items), "items": items}


async def overview(db, sandbox_phone_id: str = "", funnel_days: int = 90, now: Optional[datetime] = None) -> dict:
    """Todo el tablero de Facturación del panel de plataforma."""
    now = now or datetime.now(timezone.utc)
    settings = await bs.get_settings(db)
    subs = await _latest_subscriptions(db)
    by_status: dict[str, int] = {}
    for s in subs:
        by_status[s["status"]] = by_status.get(s["status"], 0) + 1
    without = int((await db.execute(text("""
        SELECT count(*) FROM workspaces w WHERE w.is_active AND NOT EXISTS (SELECT 1 FROM subscriptions s WHERE s.workspace_id = w.id)
    """))).scalar_one() or 0)
    return {
        "generated_at": now,
        "status_counts": by_status, "without_subscription": without,
        "income": await _income(db, subs),
        "funnel": await _funnel(db, funnel_days, sandbox_phone_id),
        "expiring_trials": await _expiring_trials(db, subs, now),
        "collections": await _collections(db),
        "risk": await _risk_and_opportunity(db, subs, now, settings),
        "founders": await _founders(db, subs, settings),
        "settings": settings,
    }


async def invoices_for_export(db, status: Optional[str] = None, limit: int = 5000) -> list[dict]:
    """Facturas para la contadora, con los datos de cobro de cada negocio."""
    rows = (await db.execute(text("""
        SELECT i.id, w.name AS workspace, bp.legal_name, bp.tax_id, bp.billing_email, i.kind, i.period_start,
               i.period_end, i.due_date, i.amount_cop, i.status, i.paid_at, i.payment_method, i.payment_reference,
               i.document_number
        FROM billing_invoices i
        JOIN workspaces w ON w.id = i.workspace_id
        LEFT JOIN billing_profiles bp ON bp.workspace_id = i.workspace_id
        WHERE (CAST(:st AS TEXT) IS NULL OR i.status = CAST(:st AS TEXT))
        ORDER BY i.period_start DESC, w.name LIMIT :l
    """), {"st": status, "l": limit})).mappings().fetchall()
    return [dict(r) for r in rows]
