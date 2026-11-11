"""
Followup Worker — seguimientos por WhatsApp: recordatorio de cita, post-visita, cobro pendiente y reactivación.

Sustituye a reminder_worker. Corre cada 10 minutos dentro del proceso del API. Solo escribe a los
clientes entre las 8:00 y las 20:00 hora del negocio. Cada pasada toma un candado en la BD para que,
si hay varios procesos del API, solo uno envíe.
"""
import asyncio
import logging
from zoneinfo import ZoneInfo

from sqlalchemy import text

from services import followup_templates as ft

log = logging.getLogger(__name__)

_INTERVAL_SECONDS = 10 * 60
_BATCH = 100
_LOCK_KEY = 815_016  # candado de la pasada (arbitrario, fijo)

# Horario en que se puede escribir al cliente, en la zona horaria del negocio.
_QUIET = "EXTRACT(HOUR FROM NOW() AT TIME ZONE w.timezone) BETWEEN 8 AND 19"

_REMINDERS = f"""
    SELECT a.id AS appointment_id, a.workspace_id, a.customer_id, a.start_at, w.name AS business,
           w.timezone, c.name AS customer_name, c.phone, c.email, s.name AS service,
           COALESCE(fs.reminder_hours_before, 24) AS hours_before
    FROM appointments a
    JOIN workspaces w ON w.id = a.workspace_id
    JOIN customers c ON c.id = a.customer_id
    LEFT JOIN services s ON s.id = a.service_id
    LEFT JOIN followup_settings fs ON fs.workspace_id = a.workspace_id
    WHERE a.status IN ('pending', 'confirmed')
      AND COALESCE(fs.reminder_enabled, TRUE)
      AND a.start_at > NOW() + INTERVAL '30 minutes'
      AND a.start_at <= NOW() + make_interval(hours => COALESCE(fs.reminder_hours_before, 24))
      AND a.created_at < NOW() - INTERVAL '2 hours'  -- recién agendada: todavía no hace falta recordarla
      AND c.phone IS NOT NULL AND {_QUIET}
      AND NOT EXISTS (SELECT 1 FROM followup_sends x WHERE x.kind = 'reminder' AND x.appointment_id = a.id)
    ORDER BY a.start_at LIMIT {_BATCH}
"""

_POST_VISITS = f"""
    SELECT a.id AS appointment_id, a.workspace_id, a.customer_id, w.name AS business, w.timezone,
           c.name AS customer_name, c.phone, s.name AS service
    FROM appointments a
    JOIN workspaces w ON w.id = a.workspace_id
    JOIN customers c ON c.id = a.customer_id
    LEFT JOIN services s ON s.id = a.service_id
    JOIN followup_settings fs ON fs.workspace_id = a.workspace_id AND fs.post_visit_enabled
    WHERE a.status = 'completed'
      AND a.end_at <= NOW() - make_interval(hours => fs.post_visit_hours_after)
      AND a.end_at > NOW() - INTERVAL '48 hours'
      AND c.phone IS NOT NULL AND {_QUIET}
      AND NOT EXISTS (SELECT 1 FROM followup_sends x WHERE x.kind = 'post_visit' AND x.appointment_id = a.id)
    ORDER BY a.end_at LIMIT {_BATCH}
"""

# Saldo = total − cobros no anulados (mismo criterio que sales_service). Solo ventas de los últimos 30 días.
_PAYMENTS_DUE = f"""
    SELECT o.id AS sales_order_id, o.workspace_id, c.id AS customer_id, w.name AS business, w.timezone,
           c.name AS customer_name, c.phone, o.issued_at,
           o.total_cop - COALESCE((SELECT SUM(m.amount_cop) FROM movements m
                                   WHERE m.sales_order_id = o.id AND m.voided_at IS NULL), 0) AS balance_cop,
           (SELECT l.description FROM sales_order_lines l WHERE l.order_id = o.id ORDER BY l.created_at LIMIT 1) AS service
    FROM sales_orders o
    JOIN workspaces w ON w.id = o.workspace_id
    JOIN third_parties tp ON tp.id = o.third_party_id
    JOIN customers c ON c.id = tp.customer_id
    JOIN followup_settings fs ON fs.workspace_id = o.workspace_id AND fs.payment_due_enabled
    WHERE o.status = 'open'
      AND (o.issued_at AT TIME ZONE w.timezone)::date
          <= (NOW() AT TIME ZONE w.timezone)::date - fs.payment_due_days
      AND o.issued_at > NOW() - INTERVAL '30 days'
      AND c.phone IS NOT NULL AND {_QUIET}
      AND o.total_cop > COALESCE((SELECT SUM(m.amount_cop) FROM movements m
                                  WHERE m.sales_order_id = o.id AND m.voided_at IS NULL), 0)
      AND NOT EXISTS (SELECT 1 FROM followup_sends x WHERE x.kind = 'payment_due' AND x.sales_order_id = o.id)
    ORDER BY o.issued_at LIMIT {_BATCH}
"""

# Clientes que vinieron alguna vez, llevan `reactivation_days` sin volver, no tienen cita futura,
# no pidieron dejar de recibir mensajes y no recibieron otra reactivación en ese mismo plazo.
_REACTIVATIONS = f"""
    SELECT c.id AS customer_id, c.workspace_id, w.name AS business, w.timezone,
           c.name AS customer_name, c.phone
    FROM customers c
    JOIN workspaces w ON w.id = c.workspace_id
    JOIN followup_settings fs ON fs.workspace_id = c.workspace_id AND fs.reactivation_enabled
    JOIN LATERAL (
        SELECT MAX(a.end_at) AS last_visit FROM appointments a
        WHERE a.customer_id = c.id AND a.status = 'completed'
    ) v ON v.last_visit IS NOT NULL
    WHERE v.last_visit < NOW() - make_interval(days => fs.reactivation_days)
      AND v.last_visit > NOW() - INTERVAL '365 days'
      AND NOT c.marketing_opt_out
      AND c.phone IS NOT NULL AND {_QUIET}
      AND NOT EXISTS (SELECT 1 FROM appointments a WHERE a.customer_id = c.id
                      AND a.status IN ('pending', 'confirmed') AND a.start_at > NOW())
      AND NOT EXISTS (SELECT 1 FROM followup_sends x WHERE x.kind = 'reactivation' AND x.customer_id = c.id
                      AND x.created_at > NOW() - make_interval(days => fs.reactivation_days))
    ORDER BY v.last_visit LIMIT {_BATCH}
"""


def _values(row: dict, **extra) -> dict:
    """Parámetros comunes de las plantillas."""
    return {
        "nombre": ft.first_name(row.get("customer_name")) or "de nuevo",
        "negocio": row.get("business") or "nuestro negocio",
        "servicio": row.get("service") or "servicio",
        **extra,
    }


async def _fetch(sql: str) -> list[dict]:
    from core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        return [dict(r) for r in (await session.execute(text(sql))).mappings().fetchall()]


async def _send_reminders() -> int:
    from services.email_service import EmailService
    from services.followup_service import send_followup

    sent = 0
    for row in await _fetch(_REMINDERS):
        local = row["start_at"].astimezone(ZoneInfo(row["timezone"]))
        fecha, hora = ft.format_date(local), ft.format_time(local)
        result = await send_followup(
            "reminder", str(row["workspace_id"]), str(row["customer_id"]), row["phone"],
            _values(row, fecha=fecha, hora=hora), appointment_id=str(row["appointment_id"]),
        )
        sent += result == "sent"
        if result in ("sent", "failed") and row.get("email"):
            await EmailService.send_appointment_reminder(
                customer_email=row["email"], customer_name=row.get("customer_name") or "",
                business_name=row.get("business") or "", service_name=row.get("service") or "tu cita",
                start_time=f"{fecha} a las {hora}", hours_before=row["hours_before"],
            )
    return sent


async def _send_post_visits() -> int:
    from services.followup_service import send_followup

    sent = 0
    for row in await _fetch(_POST_VISITS):
        result = await send_followup(
            "post_visit", str(row["workspace_id"]), str(row["customer_id"]), row["phone"],
            _values(row), appointment_id=str(row["appointment_id"]),
        )
        sent += result == "sent"
    return sent


async def _send_payments_due() -> int:
    from services.followup_service import send_followup

    sent = 0
    for row in await _fetch(_PAYMENTS_DUE):
        local = row["issued_at"].astimezone(ZoneInfo(row["timezone"]))
        result = await send_followup(
            "payment_due", str(row["workspace_id"]), str(row["customer_id"]), row["phone"],
            _values(row, saldo=ft.format_cop(row["balance_cop"]), fecha=ft.format_date(local)),
            sales_order_id=str(row["sales_order_id"]),
        )
        sent += result == "sent"
    return sent


async def _send_reactivations() -> int:
    from services.followup_service import send_followup

    sent = 0
    for row in await _fetch(_REACTIVATIONS):
        result = await send_followup(
            "reactivation", str(row["workspace_id"]), str(row["customer_id"]), row["phone"], _values(row),
        )
        sent += result == "sent"
    return sent


_JOBS = (
    ("reminder", _send_reminders), ("post_visit", _send_post_visits),
    ("payment_due", _send_payments_due), ("reactivation", _send_reactivations),
)


async def run_followups() -> dict:
    """Una pasada completa. Devuelve cuántos mensajes salieron por tipo ({} si otro proceso ya estaba en ello)."""
    from core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as lock_session:
        got = (await lock_session.execute(
            text("SELECT pg_try_advisory_lock(:k)"), {"k": _LOCK_KEY})).scalar_one()
        if not got:
            return {}
        try:
            totals = {}
            for kind, job in _JOBS:
                try:
                    totals[kind] = await job()
                except Exception as e:  # un tipo que falla no frena a los demás
                    log.error("[followups] error en %s | err=%s", kind, e, exc_info=True)
                    totals[kind] = 0
            if any(totals.values()):
                log.info("[followups] pasada | %s", totals)
            return totals
        finally:
            await lock_session.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _LOCK_KEY})
            await lock_session.commit()


async def _followup_loop() -> None:
    log.info("[followups] scheduler iniciado — primera pasada en 60s, luego cada 10 minutos")
    await asyncio.sleep(60)
    while True:
        try:
            await run_followups()
        except Exception as e:
            log.error("[followups] error en ciclo | err=%s", e, exc_info=True)
        await asyncio.sleep(_INTERVAL_SECONDS)


def start_followup_scheduler() -> asyncio.Task:
    """Lanza el loop de seguimientos como tarea asyncio en background."""
    return asyncio.create_task(_followup_loop())
