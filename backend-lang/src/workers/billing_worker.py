"""
Billing Worker — ciclo de vida automático de las suscripciones (ver documentation/zumit-plan-de-pagos-y-sus.md).

Corre cada hora dentro del proceso del API, con un candado en la BD para que solo un proceso lo haga. Cada
paso es idempotente: si el proceso se reinicia a la mitad, la siguiente pasada continúa sin duplicar nada.

Qué hace, en orden:
  1. Pausa las pruebas vencidas (día 8 sin plan pago). Los datos se conservan 30 días.
  2. Cobra, prorrateado, el profesional que se agregó a mitad de ciclo por encima del plan.
  3. Genera el cobro del ciclo siguiente y avisa `upcoming_notice_days` días antes. Aplica ahí la bajada de plan
     agendada y descuenta un ciclo de descuento de lanzamiento. Cierra las cancelaciones al final del ciclo.
  4. Marca vencidas las facturas pasada su fecha y pone al negocio en mora (avisa al día siguiente).
  5. Avisa que se va a pausar y, pasados los días de gracia, pausa el asistente.
  6. Al fundador con más de `retention_days` de mora le quita el valor real congelado.
  7. Anota (no borra) los negocios cuyos datos ya pasaron el plazo de retención: borrar lo decide una persona.

No envía WhatsApp: Zumit aún no tiene un número propio para escribir a sus clientes. Los avisos salen por correo
(Resend) y quedan como alerta en el panel del negocio.
"""
import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import text

from services import billing_service as bs
from services import subscription_service as ss

log = logging.getLogger(__name__)

_INTERVAL_SECONDS = 60 * 60
_LOCK_KEY = 815_022  # candado de la pasada (arbitrario, fijo)


def _cop(n: int) -> str:
    return "$" + f"{n:,}".replace(",", ".")


# ── Avisos ───────────────────────────────────────────────────────────────────

async def _recipient(db, workspace_id: str) -> Optional[str]:
    """Correo de cobro si el negocio lo dio; si no, el del dueño."""
    row = (await db.execute(text("""
        SELECT COALESCE(
            (SELECT billing_email FROM billing_profiles WHERE workspace_id = :w),
            (SELECT u.email FROM workspace_members m JOIN users u ON u.id = m.user_id
              WHERE m.workspace_id = :w AND m.member_role = 'workspace_owner' ORDER BY m.created_at LIMIT 1)
        ) AS email
    """), {"w": workspace_id})).mappings().fetchone()
    return row["email"] if row else None


async def notify(db, workspace_id: str, kind: str, ref: str, subject: str, message: str,
                 severity: str = "warning") -> bool:
    """Un aviso por tipo y referencia: alerta en el panel y correo. Devuelve False si ya se había enviado."""
    seen = (await db.execute(
        text("""SELECT 1 FROM billing_events WHERE workspace_id = :w AND type = :t AND payload->>'ref' = :r LIMIT 1"""),
        {"w": workspace_id, "t": f"notice_{kind}", "r": ref},
    )).scalar_one_or_none()
    if seen:
        return False
    emailed = False
    to = await _recipient(db, workspace_id)
    if to:
        try:
            from services.email_service import EmailService, _base_template
            html = _base_template(f"<h2 style='margin:0 0 12px'>{subject}</h2><p style='line-height:1.6'>{message}</p>",
                                  "Si ya pagaste, ignora este mensaje: se actualiza apenas confirmamos el pago.")
            emailed = await EmailService._send(to, subject, html)
        except Exception as exc:
            log.warning("[billing-worker] correo falló | ws=%s | err=%s", workspace_id, type(exc).__name__)
    await db.execute(
        text("INSERT INTO agent_alerts (workspace_id, severity, reason, resolved) VALUES (:w, :s, :r, FALSE)"),
        {"w": workspace_id, "s": severity, "r": f"{subject}. {message}"[:500]},
    )
    await bs.log_event(db, workspace_id, f"notice_{kind}", {"ref": ref, "emailed": emailed})
    return True


# ── Pasos ────────────────────────────────────────────────────────────────────

async def expire_trials(db, now: datetime) -> int:
    rows = (await db.execute(
        text("SELECT workspace_id, id FROM subscriptions WHERE status = 'trial' AND trial_ends_at <= :now"),
        {"now": now},
    )).mappings().fetchall()
    for r in rows:
        ws = str(r["workspace_id"])
        await ss.pause(db, ws, now, reason="trial_ended")
        await notify(db, ws, "trial_ended", str(r["id"]), "Terminó tu prueba de Zumit",
                     "Tu prueba gratis de 7 días terminó y el asistente quedó en pausa. Tus datos se conservan 30 días: "
                     "activa un plan y el asistente vuelve a atender al instante.", "warning")
    return len(rows)


async def issue_renewals(db, now: datetime) -> int:
    """Genera el cobro del siguiente ciclo `upcoming_notice_days` antes. Aplica la bajada de plan agendada."""
    settings = await bs.get_settings(db)
    rows = (await db.execute(
        text("SELECT workspace_id FROM subscriptions WHERE status = 'active' AND activated_at IS NOT NULL"),
    )).mappings().fetchall()
    issued = 0
    for r in rows:
        ws = str(r["workspace_id"])
        sub = await ss.get_live_subscription(db, ws)
        today = now.astimezone(ss._tz(sub["tz"])).date()
        anchor = sub["cycle_anchor_day"] or sub["activated_at"].astimezone(ss._tz(sub["tz"])).day
        start, end = bs.cycle_bounds(anchor, today)
        if sub["cancel_at_period_end"]:
            # Se cancela cuando termina lo que ya pagó: el fin del último ciclo facturado (no el del ciclo en curso).
            covered = (await db.execute(
                text("SELECT MAX(period_end) FROM billing_invoices WHERE subscription_id = :s AND kind = 'cycle' AND status <> 'void'"),
                {"s": sub["id"]})).scalar_one_or_none()
            if covered and today >= covered:
                await ss.mark_cancelled(db, ws)
            continue
        if (end - today).days > settings["upcoming_notice_days"]:
            continue
        if sub.get("pending_plan_id"):  # bajada de plan: vale desde el ciclo que se cobra ahora
            await db.execute(
                text("UPDATE subscriptions SET billing_plan_id = pending_plan_id, pending_plan_id = NULL WHERE id = :id"),
                {"id": sub["id"]})
            sub = await ss.get_live_subscription(db, ws)
        _, next_end = bs.cycle_bounds(anchor, end)
        inv = await ss.issue_cycle_invoice(db, sub, end, next_end, due=end)
        if inv:
            issued += 1
            amount = (await db.execute(text("SELECT amount_cop FROM billing_invoices WHERE id = :i"), {"i": inv})).scalar_one()
            await notify(db, ws, "upcoming", inv, "Tu próximo cobro de Zumit",
                         f"El {end:%d/%m/%Y} se renueva tu plan {sub['plan_name']} por {_cop(int(amount))}. "
                         "Se renueva solo hasta que lo canceles; puedes hacerlo desde el panel.", "info")
    return issued


async def bill_extra_professionals(db, now: datetime) -> int:
    """Cobra el profesional adicional que se agregó a mitad de ciclo (prorrateado) y avisa al dueño."""
    rows = (await db.execute(
        text("SELECT workspace_id FROM subscriptions WHERE status IN ('active','past_due') AND activated_at IS NOT NULL"),
    )).mappings().fetchall()
    billed = 0
    for r in rows:
        ws = str(r["workspace_id"])
        res = await ss.charge_extra_professionals(db, await ss.get_live_subscription(db, ws), now)
        if not res:
            continue
        billed += 1
        await notify(db, ws, "extra_professional", res["invoice_id"], "Agregaste un profesional por encima de tu plan",
                     f"Tu plan incluye menos profesionales de los que tienes con calendario. Sumamos {_cop(res['amount_cop'])} "
                     f"(prorrateado por los días que quedan del ciclo), que se cobra el {res['due_date']:%d/%m/%Y} con tu renovación.",
                     "info")
    return billed


async def mark_overdue(db, now: datetime) -> int:
    rows = (await db.execute(text("""
        UPDATE billing_invoices SET status = 'overdue', updated_at = NOW()
        WHERE status = 'pending' AND due_date < (NOW() AT TIME ZONE 'America/Bogota')::date
        RETURNING id, workspace_id, subscription_id, amount_cop
    """))).mappings().fetchall()
    for r in rows:
        ws = str(r["workspace_id"])
        if r["subscription_id"]:
            moved = (await db.execute(text("""
                UPDATE subscriptions SET status = 'past_due', past_due_since = COALESCE(past_due_since, :now), updated_at = NOW()
                WHERE id = :s AND status = 'active' RETURNING id
            """), {"s": r["subscription_id"], "now": now})).scalar_one_or_none()
            if moved:
                await bs.log_event(db, ws, "past_due", {"invoice_id": str(r["id"])}, str(r["subscription_id"]))
        grace = (await bs.get_settings(db))["grace_days"]
        await notify(db, ws, "overdue", str(r["id"]), "Tu pago de Zumit está vencido",
                     f"No recibimos el pago de {_cop(r['amount_cop'])}. Tienes {grace} días para ponerte al día "
                     "antes de que el asistente se pause.", "warning")
    return len(rows)


async def pause_overdue(db, now: datetime) -> int:
    grace = (await bs.get_settings(db))["grace_days"]
    rows = (await db.execute(
        text("SELECT workspace_id, id, past_due_since FROM subscriptions WHERE status = 'past_due' AND past_due_since IS NOT NULL"),
    )).mappings().fetchall()
    paused = 0
    for r in rows:
        ws, due = str(r["workspace_id"]), r["past_due_since"] + timedelta(days=grace)
        if now >= due:
            await ss.pause(db, ws, now, reason="mora")
            await notify(db, ws, "paused", str(r["id"]), "El asistente de Zumit quedó en pausa",
                         "Pasaron los días de gracia sin recibir el pago. El asistente dejó de atender a tus clientes; "
                         "se reactiva apenas confirmemos el pago. Tus datos se conservan 30 días.", "error")
            paused += 1
        elif now >= due - timedelta(days=1):
            await notify(db, ws, "pause_warning", str(r["id"]), "Mañana se pausa tu asistente",
                         "Si no recibimos el pago hoy, mañana el asistente dejará de atender a tus clientes.", "warning")
    return paused


async def drop_founder_price(db, now: datetime) -> int:
    days = (await bs.get_settings(db))["retention_days"]
    rows = (await db.execute(text("""
        UPDATE subscriptions SET frozen_price_cop = NULL, updated_at = NOW()
        WHERE is_founder AND frozen_price_cop IS NOT NULL AND status IN ('past_due','paused')
          AND past_due_since IS NOT NULL AND past_due_since <= :cut
        RETURNING workspace_id, id
    """), {"cut": now - timedelta(days=days)})).mappings().fetchall()
    for r in rows:
        await bs.log_event(db, str(r["workspace_id"]), "founder_price_lost", {}, str(r["id"]))
    return len(rows)


async def sync_langsmith(db, now: datetime) -> int:
    """Guarda el costo real de la IA (LangSmith) de hoy y ayer. LangSmith conserva los trazos poco tiempo, así que se
    copian a nuestra BD cada hora. Sin clave configurada no hace nada; si falla, queda el error en el registro de
    sincronización (Zumit Manager lo muestra) y no frena los demás pasos."""
    from integrations import langsmith_costs
    from services import billing_costs
    if not langsmith_costs.is_configured():
        return 0
    result = await billing_costs.sync(db, days=2)
    return result["runs"] if result["ok"] else 0


async def flag_purge_due(db, now: datetime) -> int:
    """Solo anota: borrar datos de un negocio lo decide y confirma una persona."""
    rows = (await db.execute(text("""
        SELECT workspace_id, id FROM subscriptions
        WHERE status IN ('paused','cancelled') AND data_purge_after IS NOT NULL AND data_purge_after <= :now
          AND NOT EXISTS (SELECT 1 FROM billing_events e WHERE e.workspace_id = subscriptions.workspace_id
                          AND e.type = 'purge_due' AND e.subscription_id = subscriptions.id)
    """), {"now": now})).mappings().fetchall()
    for r in rows:
        await bs.log_event(db, str(r["workspace_id"]), "purge_due", {}, str(r["id"]))
    return len(rows)


_STEPS = (
    ("trials_paused", expire_trials),
    ("invoices_issued", issue_renewals),
    ("professionals_billed", bill_extra_professionals),
    ("marked_overdue", mark_overdue),
    ("paused_for_debt", pause_overdue),
    ("founder_price_lost", drop_founder_price),
    ("purge_due", flag_purge_due),
    ("langsmith_runs", sync_langsmith),
)


async def run_billing(now: Optional[datetime] = None, session_factory=None) -> dict:
    """Una pasada completa. Devuelve cuántas cosas hizo cada paso ({} si otro proceso ya estaba en ello)."""
    from core.database import AsyncSessionLocal
    now = now or datetime.now(timezone.utc)
    factory = session_factory or AsyncSessionLocal

    async with factory() as lock_session:
        got = (await lock_session.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": _LOCK_KEY})).scalar_one()
        if not got:
            return {}
        try:
            totals = {}
            for name, step in _STEPS:
                try:
                    async with factory() as db:  # una sesión por paso: si uno falla, los demás siguen
                        totals[name] = await step(db, now)
                        await db.commit()
                except Exception as e:
                    log.error("[billing-worker] error en %s | err=%s", name, e, exc_info=True)
                    totals[name] = 0
            if any(totals.values()):
                log.info("[billing-worker] pasada | %s", totals)
            return totals
        finally:
            await lock_session.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _LOCK_KEY})
            await lock_session.commit()


async def _billing_loop() -> None:
    log.info("[billing-worker] iniciado — primera pasada en 90s, luego cada hora")
    await asyncio.sleep(90)
    while True:
        try:
            await run_billing()
        except Exception as e:
            log.error("[billing-worker] error en ciclo | err=%s", e, exc_info=True)
        await asyncio.sleep(_INTERVAL_SECONDS)


def start_billing_scheduler() -> asyncio.Task:
    """Lanza el loop de facturación como tarea asyncio en background."""
    return asyncio.create_task(_billing_loop())
