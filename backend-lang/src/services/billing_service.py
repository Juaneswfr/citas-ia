"""
BillingService — qué incluye el plan de cada negocio y cuánto lleva usado.

Una sola fuente de verdad para el agente, las rutas y el panel (ver documentation/zumit-plan-de-pagos-y-sus.md).
Las funciones puras (ciclo, prorrateo, descuento, nivel de cupo) no tocan la BD y tienen pruebas propias.

Un negocio sin fila en `subscriptions` es «sin plan asignado» (los que existían antes de la 022): no tiene
límites y el agente responde igual que siempre. Nada se bloquea hasta que alguien le asigna un plan.
"""
import calendar
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import text

log = logging.getLogger(__name__)

DEFAULT_TZ = "America/Bogota"

# Parámetros por defecto: en producción se leen de `platform_settings` (ver `get_settings`).
DEFAULTS = {
    "trial_days": 7,
    "launch_discount_pct": 58,
    "launch_discount_cycles": 3,
    "quota_warn_pct": 80,
    "quota_margin": 20,
    "grace_days": 5,
    "retention_days": 30,
    "upcoming_notice_days": 3,
    "low_usage_pct": 40,
    "founder_cap": 30,
    "fixed_costs_cop_month": 0,
}

# Estados en los que el asistente atiende. `past_due` sigue atendiendo durante los días de gracia.
SERVING = {"trial", "active", "past_due"}

# Precio estimado de Claude Haiku 4.5 en USD por millón de tokens. Es una estimación para medir margen,
# no una factura: si Anthropic cambia la tarifa, se ajusta aquí.
AI_USD_PER_MTOK_IN = 1.0
AI_USD_PER_MTOK_OUT = 5.0

QUOTA_BLOCKED_REPLY = "Por ahora no puedo agendar más citas por este medio. El negocio te atenderá directamente."


# ── Funciones puras ──────────────────────────────────────────────────────────

def _clamp_day(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


def cycle_bounds(anchor_day: int, today: date) -> tuple[date, date]:
    """Inicio del ciclo que contiene `today` y el inicio del siguiente.

    Los ciclos empiezan el día `anchor_day` de cada mes; si el mes no tiene ese día, el último del mes.
    El ancla no se desplaza: con ancla 31 los ciclos empiezan 31 ene, 28 feb, 31 mar…
    """
    start = _clamp_day(today.year, today.month, anchor_day)
    if start > today:
        start = _clamp_day(*_shift_month(today.year, today.month, -1), anchor_day)
    nxt = _clamp_day(*_shift_month(start.year, start.month, 1), anchor_day)
    return start, nxt


def prorate_upgrade(old_price: int, new_price: int, days_left: int, cycle_days: int) -> int:
    """(plan nuevo − plan actual) × días restantes ÷ días del ciclo. Nunca negativo."""
    if cycle_days <= 0:
        return 0
    return max(0, round(max(0, new_price - old_price) * max(0, days_left) / cycle_days))


def launch_price(real_price: int, discount_pct: int = 58) -> int:
    """Precio de lanzamiento: valor real menos el descuento, redondeado a los mil más cercanos."""
    return int(real_price * (100 - discount_pct) / 100 / 1000 + 0.5) * 1000


def professional_prorata(price: int, days_left: int, cycle_days: int) -> int:
    """Profesional adicional creado a mitad de ciclo: paga los días que le quedan."""
    if cycle_days <= 0:
        return 0
    return round(price * max(0, min(days_left, cycle_days)) / cycle_days)


def extra_professionals(active: int, limit: Optional[int]) -> int:
    return max(0, active - limit) if limit is not None else 0


def quota_level(used: int, total: int, margin: int, warn_pct: int) -> str:
    """ok → warn (80 %) → over (se pasó del total, aún agenda dentro del margen) → blocked."""
    if total <= 0:
        return "blocked" if used >= margin else "over"
    if used >= total + margin:
        return "blocked"
    if used >= total:
        return "over"
    if used * 100 >= total * warn_pct:
        return "warn"
    return "ok"


def price_for_cycle(plan_price: int, plan_launch_price: Optional[int], discount_cycles_remaining: int,
                    frozen_price: Optional[int]) -> int:
    """Lo que paga el plan en el ciclo que empieza: descuento de lanzamiento si le quedan ciclos; si no,
    el valor real (o el congelado del fundador)."""
    if discount_cycles_remaining > 0 and plan_launch_price is not None:
        return plan_launch_price
    return frozen_price if frozen_price is not None else plan_price


def normalize_phone(raw: Optional[str]) -> str:
    """Solo dígitos: la prueba y el descuento se reclaman una vez por número."""
    return "".join(ch for ch in (raw or "") if ch.isdigit())


def ai_cost_usd(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * AI_USD_PER_MTOK_IN + output_tokens * AI_USD_PER_MTOK_OUT) / 1_000_000


def effective_status(sub: dict, now: datetime, covered_until: Optional[date], today: date, grace_days: int) -> str:
    """Estado real aunque el worker no haya corrido: el agente no depende de él para dejar de atender.

    `covered_until` es el fin del último ciclo facturado: una cancelación pedida tiene efecto cuando llega ahí.
    (No el fin del ciclo en curso: ese siempre es posterior a hoy.)"""
    status = sub["status"]
    if status == "trial" and sub.get("trial_ends_at") and sub["trial_ends_at"] <= now:
        return "expired"
    if status == "past_due" and sub.get("past_due_since") \
            and sub["past_due_since"] + timedelta(days=grace_days) <= now:
        return "paused"
    if status == "active" and sub.get("cancel_at_period_end") and covered_until and today >= covered_until:
        return "cancelled"
    return status


# ── Entitlements ─────────────────────────────────────────────────────────────

@dataclass
class Entitlements:
    workspace_id: str
    has_subscription: bool = False
    status: str = "none"                 # estado efectivo; «none» = sin plan asignado
    serving: bool = True                 # el asistente puede responder
    plan_code: Optional[str] = None
    plan_name: Optional[str] = None
    trial_ends_at: Optional[datetime] = None
    cycle_start: Optional[date] = None
    cycle_end: Optional[date] = None
    included_appointments: Optional[int] = None
    extra_appointments: int = 0
    used_appointments: int = 0
    quota_level: str = "ok"
    can_book: bool = True                # el asistente puede crear citas nuevas
    professionals_limit: Optional[int] = None
    professionals_active: int = 0
    extra_professionals: int = 0
    tz: str = DEFAULT_TZ
    settings: dict = field(default_factory=dict)

    @property
    def total_appointments(self) -> Optional[int]:
        return None if self.included_appointments is None else self.included_appointments + self.extra_appointments

    @property
    def remaining_appointments(self) -> Optional[int]:
        total = self.total_appointments
        return None if total is None else max(0, total - self.used_appointments)


async def get_settings(db) -> dict:
    rows = (await db.execute(text("SELECT key, value FROM platform_settings"))).mappings().fetchall()
    return {**DEFAULTS, **{r["key"]: r["value"] for r in rows}}


def _local_midnight(day: date, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, time.min, tzinfo=tz)


async def get_entitlements(db, workspace_id: str, now: Optional[datetime] = None) -> Entitlements:
    """Plan, estado real, ciclo, cupo de citas y profesionales del negocio. Solo lee."""
    now = now or datetime.now(timezone.utc)
    ent = Entitlements(workspace_id=str(workspace_id))
    sub = (await db.execute(
        text("""
        SELECT s.id, s.status, s.trial_ends_at, s.past_due_since, s.cancel_at_period_end, s.cycle_anchor_day,
               s.activated_at, s.created_at, p.code AS plan_code, p.name AS plan_name,
               p.max_appointments, p.max_professionals, w.timezone AS tz
        FROM subscriptions s
        JOIN billing_plans p ON p.id = s.billing_plan_id
        JOIN workspaces w ON w.id = s.workspace_id
        WHERE s.workspace_id = :w
        ORDER BY s.created_at DESC LIMIT 1
        """),
        {"w": workspace_id},
    )).mappings().fetchone()
    if not sub:
        return ent  # sin plan asignado: sin límites

    ent.settings = await get_settings(db)
    try:
        tz = ZoneInfo(sub["tz"] or DEFAULT_TZ)
    except Exception:
        tz = ZoneInfo(DEFAULT_TZ)
    ent.tz = str(tz)
    today = now.astimezone(tz).date()

    # En la prueba el ciclo cuenta desde que empezó; con plan activo, desde el ancla de la activación.
    anchor = sub["cycle_anchor_day"] or (sub["activated_at"] or sub["created_at"]).astimezone(tz).day
    start, end = cycle_bounds(anchor, today)
    ent.has_subscription = True
    ent.plan_code, ent.plan_name = sub["plan_code"], sub["plan_name"]
    ent.trial_ends_at = sub["trial_ends_at"]
    ent.cycle_start, ent.cycle_end = start, end
    covered = None
    if sub["cancel_at_period_end"]:
        covered = (await db.execute(
            text("SELECT MAX(period_end) FROM billing_invoices WHERE subscription_id = :s AND kind = 'cycle' AND status <> 'void'"),
            {"s": sub["id"]},
        )).scalar_one_or_none()
    ent.status = effective_status(dict(sub), now, covered, today, ent.settings["grace_days"])
    ent.serving = ent.status in SERVING

    ent.included_appointments = sub["max_appointments"]
    ent.professionals_limit = sub["max_professionals"]
    ent.extra_appointments = int((await db.execute(
        text("""
        SELECT COALESCE(SUM(quantity), 0) FROM subscription_addons
        WHERE subscription_id = :s AND valid_from < :end AND (valid_until IS NULL OR valid_until > :start)
        """),
        {"s": sub["id"], "start": start, "end": end},
    )).scalar_one() or 0)
    ent.used_appointments = int((await db.execute(
        text("""
        SELECT COUNT(*) FROM appointments
        WHERE workspace_id = :w AND created_by IS NULL AND created_at >= :start AND created_at < :end
        """),
        {"w": workspace_id, "start": _local_midnight(start, tz), "end": _local_midnight(end, tz)},
    )).scalar_one() or 0)
    ent.professionals_active = int((await db.execute(
        text("SELECT COUNT(*) FROM calendars WHERE workspace_id = :w AND sync_status = 'active' AND member_id IS NOT NULL"),
        {"w": workspace_id},
    )).scalar_one() or 0)
    ent.extra_professionals = extra_professionals(ent.professionals_active, ent.professionals_limit)

    if ent.included_appointments is not None:
        ent.quota_level = quota_level(ent.used_appointments, ent.total_appointments,
                                      ent.settings["quota_margin"], ent.settings["quota_warn_pct"])
    ent.can_book = ent.serving and ent.quota_level != "blocked"
    return ent


async def safe_entitlements(db, workspace_id: str, now: Optional[datetime] = None) -> Entitlements:
    """Como `get_entitlements`, pero nunca tumba al agente ni a la creación de citas.

    Si la facturación no está lista (migración 022 sin aplicar) o la consulta falla, devuelve «sin límites» y deja
    el error en el log: el producto sigue funcionando como antes. Va en un SAVEPOINT para que el fallo no deje
    abortada la transacción de quien llama.
    """
    try:
        async with db.begin_nested():
            return await get_entitlements(db, workspace_id, now)
    except Exception as exc:
        log.error("[billing] no se pudo leer el plan; se atiende sin límites | ws=%s | err=%s: %s",
                  workspace_id, type(exc).__name__, exc)
        return Entitlements(workspace_id=str(workspace_id))


async def safe_is_serving(db, workspace_id: str, now: Optional[datetime] = None) -> bool:
    """¿El plan del negocio permite mensajes automáticos? Solo lee el estado (no cuenta citas ni profesionales).

    Igual que `safe_entitlements`, falla «abierto»: sin plan asignado, o si la facturación no se puede leer
    (migración 022 sin aplicar), devuelve True y el producto sigue como antes.
    """
    now = now or datetime.now(timezone.utc)
    try:
        async with db.begin_nested():
            sub = (await db.execute(
                text("""
                SELECT id, status, trial_ends_at, past_due_since, cancel_at_period_end
                FROM subscriptions WHERE workspace_id = :w ORDER BY created_at DESC LIMIT 1
                """),
                {"w": workspace_id},
            )).mappings().fetchone()
            if not sub:
                return True
            covered = None
            if sub["cancel_at_period_end"]:
                covered = (await db.execute(
                    text("SELECT MAX(period_end) FROM billing_invoices "
                         "WHERE subscription_id = :s AND kind = 'cycle' AND status <> 'void'"),
                    {"s": sub["id"]},
                )).scalar_one_or_none()
            grace = (await get_settings(db))["grace_days"]
            status = effective_status(dict(sub), now, covered, now.date(), grace)
            return status in SERVING
    except Exception as exc:
        log.error("[billing] no se pudo leer el plan; se envía sin límites | ws=%s | err=%s: %s",
                  workspace_id, type(exc).__name__, exc)
        return True


# ── Registro: eventos, consumo de IA, alertas de cupo ────────────────────────

async def log_event(db, workspace_id: str, type_: str, payload: Optional[dict] = None,
                    subscription_id: Optional[str] = None) -> None:
    """Línea de tiempo del negocio y base del embudo. No hace commit: lo hace quien llama."""
    import json
    await db.execute(
        text("""
        INSERT INTO billing_events (workspace_id, subscription_id, type, payload)
        VALUES (:w, :s, :t, CAST(:p AS JSONB))
        """),
        {"w": workspace_id, "s": subscription_id, "t": type_, "p": json.dumps(payload or {}, default=str)},
    )


async def record_usage(db, workspace_id: str, input_tokens: int, output_tokens: int, calls: int = 1) -> None:
    """Suma una llamada al modelo al consumo del día del negocio. Nunca lanza: medir no puede tumbar al agente."""
    try:
        await db.execute(
            text("""
            INSERT INTO agent_usage (workspace_id, day, calls, input_tokens, output_tokens, cost_usd)
            VALUES (:w, (NOW() AT TIME ZONE 'America/Bogota')::date, :n, :i, :o, :c)
            ON CONFLICT (workspace_id, day) DO UPDATE SET
                calls = agent_usage.calls + EXCLUDED.calls,
                input_tokens = agent_usage.input_tokens + EXCLUDED.input_tokens,
                output_tokens = agent_usage.output_tokens + EXCLUDED.output_tokens,
                cost_usd = agent_usage.cost_usd + EXCLUDED.cost_usd
            """),
            {"w": workspace_id, "n": calls, "i": input_tokens, "o": output_tokens, "c": ai_cost_usd(input_tokens, output_tokens)},
        )
        await db.commit()
    except Exception as exc:
        # Sin el rollback la transacción queda abortada y revienta lo siguiente que haga quien llamó.
        await db.rollback()
        log.warning("[billing] no se pudo registrar el consumo | ws=%s | err=%s", workspace_id, type(exc).__name__)


_QUOTA_EVENT = {"warn": "quota_80", "over": "quota_limit", "blocked": "quota_blocked"}
_QUOTA_TEXT = {
    "warn": "Llevas el {pct} % de las citas de tu plan este ciclo ({used} de {total}).",
    "over": "Se acabaron las citas de tu plan ({used} de {total}). El asistente sigue agendando unas pocas más de margen.",
    "blocked": "El asistente dejó de agendar: se acabaron las citas del ciclo. Carga citas adicionales o espera al siguiente ciclo.",
}


async def notify_quota(db, ent: Entitlements) -> None:
    """Una alerta y un evento por nivel y por ciclo. Nunca lanza."""
    event = _QUOTA_EVENT.get(ent.quota_level)
    if not event or not ent.cycle_start:
        return
    try:
        seen = (await db.execute(
            text("SELECT 1 FROM billing_events WHERE workspace_id = :w AND type = :t AND created_at >= :since LIMIT 1"),
            {"w": ent.workspace_id, "t": event,
             "since": _local_midnight(ent.cycle_start, ZoneInfo(ent.tz))},
        )).scalar_one_or_none()
        if seen:
            return
        total = ent.total_appointments or 0
        pct = round(ent.used_appointments * 100 / total) if total else 100
        reason = _QUOTA_TEXT[ent.quota_level].format(pct=pct, used=ent.used_appointments, total=total)
        await db.execute(
            text("INSERT INTO agent_alerts (workspace_id, severity, reason, resolved) VALUES (:w, :sev, :r, FALSE)"),
            {"w": ent.workspace_id, "sev": "warning" if ent.quota_level != "blocked" else "error", "r": reason},
        )
        await log_event(db, ent.workspace_id, event, {"used": ent.used_appointments, "total": total})
        await db.commit()
    except Exception as exc:
        await db.rollback()
        log.warning("[billing] no se pudo avisar el cupo | ws=%s | err=%s", ent.workspace_id, type(exc).__name__)
