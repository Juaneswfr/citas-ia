"""
Reminder Worker — Envío de recordatorios de cita por WhatsApp.

FR-011 (Spec): Recordatorios 24h y 2h antes de cada cita confirmada,
enviados únicamente por WhatsApp usando el canal activo del workspace.
Principio II: Toda lógica de negocio vive en el backend.
Responsabilidad única (Principio X): solo gestiona recordatorios.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

# Ventanas de recordatorio: (horas_antes, etiqueta)
_REMINDER_WINDOWS = [
    (24, "24h"),
    (2, "2h"),
]

# Margen de tolerancia para evitar envíos duplicados (±5 minutos)
_TOLERANCE_MINUTES = 5


async def run_reminders() -> None:
    """
    Busca citas confirmadas próximas y envía recordatorios WhatsApp + email.
    Diseñado para ejecutarse cada 30 minutos via scheduler.
    """
    from core.database import _pool
    from services.whatsapp_service import WhatsAppService
    from services.email_service import EmailService

    if _pool is None:
        return

    now = datetime.now(timezone.utc)

    for hours_before, label in _REMINDER_WINDOWS:
        target_start = now + timedelta(hours=hours_before)
        window_from = target_start - timedelta(minutes=_TOLERANCE_MINUTES)
        window_to = target_start + timedelta(minutes=_TOLERANCE_MINUTES)
        sent_field = f"reminder_{label.replace('h', '')}h_sent"

        async with _pool.acquire() as db:
            appointments = await db.fetch(
                f"""
                SELECT id, workspace_id, start_at, customer_id, service_id, {sent_field}
                FROM appointments
                WHERE status = 'confirmed'
                  AND start_at >= $1 AND start_at <= $2
                """,
                window_from,
                window_to,
            )

        if not appointments:
            continue

        log.info("[reminders] ventana %s | citas encontradas=%d", label, len(appointments))

        for appt in appointments:
            appt_id = appt["id"]

            # Evitar reenvíos
            if appt.get(sent_field):
                continue

            async with _pool.acquire() as db:
                channel = await db.fetchrow(
                    "SELECT phone_number_id FROM channels WHERE workspace_id=$1 AND status='active' LIMIT 1",
                    appt["workspace_id"],
                )
                if not channel:
                    log.warning("[reminders] sin canal activo | workspace=%s | appt=%s",
                                appt["workspace_id"], appt_id)
                    continue

                customer = await db.fetchrow(
                    "SELECT phone, name, email FROM customers WHERE id=$1", appt["customer_id"]
                )
                if not customer or not customer["phone"]:
                    log.warning("[reminders] cliente sin teléfono | appt=%s", appt_id)
                    continue

                service = await db.fetchrow(
                    "SELECT name FROM services WHERE id=$1", appt["service_id"]
                )

            phone_number_id = channel["phone_number_id"]
            customer_phone = customer["phone"]
            customer_name = customer["name"] or ""
            customer_email = customer["email"] or ""
            service_name = service["name"] if service else "tu cita"

            start_at = appt["start_at"]
            hora = start_at.strftime("%I:%M %p")
            fecha = start_at.strftime("%d/%m/%Y")

            greeting = f"Hola {customer_name}! " if customer_name else "Hola! "
            text = (
                f"{greeting}Te recordamos que tienes *{service_name}* "
                f"el {fecha} a las {hora}. "
                f"Te esperamos en {label}. ✂️"
            )

            sent = await WhatsAppService.send_message(
                to=customer_phone,
                text=text,
                phone_number_id=phone_number_id,
            )

            if customer_email:
                workspace_row = None
                async with _pool.acquire() as db:
                    workspace_row = await db.fetchrow(
                        "SELECT name FROM workspaces WHERE id=$1", appt["workspace_id"]
                    )
                business_name = workspace_row["name"] if workspace_row else ""
                await EmailService.send_appointment_reminder(
                    customer_email=customer_email,
                    customer_name=customer_name,
                    business_name=business_name,
                    service_name=service_name,
                    start_time=f"{fecha} a las {hora}",
                    hours_before=hours_before,
                )

            if sent or customer_email:
                async with _pool.acquire() as db:
                    await db.execute(
                        f"UPDATE appointments SET {sent_field}=TRUE WHERE id=$1", appt_id
                    )
                log.info("[reminders] enviado | appt=%s | to=%s | ventana=%s",
                         appt_id, customer_phone, label)
            else:
                log.warning("[reminders] fallo envío | appt=%s | to=%s | ventana=%s",
                            appt_id, customer_phone, label)


async def _reminder_loop() -> None:
    """Loop asíncrono que ejecuta run_reminders() cada 30 minutos."""
    log.info("[reminders] scheduler iniciado — primera ejecución en 60s, luego cada 30 minutos")
    await asyncio.sleep(60)  # Esperar que el pool esté listo
    while True:
        try:
            await run_reminders()
        except Exception as e:
            log.error("[reminders] error en ciclo | err=%s", e, exc_info=True)
        try:
            from core.security import rate_limit_purge
            await rate_limit_purge(24 * 3600)  # ventanas de rate_limits con más de 24 h
        except Exception as e:
            log.error("[rate_limits] purge falló | err=%s", type(e).__name__)
        await asyncio.sleep(30 * 60)  # 30 minutos


def start_reminder_scheduler() -> asyncio.Task:
    """
    Lanza el loop de recordatorios como tarea asyncio en background.
    Llamar desde el lifespan de FastAPI.
    """
    return asyncio.create_task(_reminder_loop())
