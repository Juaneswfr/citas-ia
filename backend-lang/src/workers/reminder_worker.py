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
    Busca citas confirmadas próximas y envía recordatorios WhatsApp.
    Diseñado para ejecutarse cada 30 minutos via scheduler.
    """
    from core.supabase_client import get_supabase
    from services.whatsapp_service import WhatsAppService

    supabase = get_supabase()
    now = datetime.now(timezone.utc)

    for hours_before, label in _REMINDER_WINDOWS:
        target_start = now + timedelta(hours=hours_before)
        window_from = target_start - timedelta(minutes=_TOLERANCE_MINUTES)
        window_to = target_start + timedelta(minutes=_TOLERANCE_MINUTES)

        # Citas confirmadas dentro de la ventana de recordatorio
        result = (
            supabase.table("appointments")
            .select(
                "id, workspace_id, start_at, customer_id, service_id, calendar_id, "
                "reminder_24h_sent, reminder_2h_sent"
            )
            .eq("status", "confirmed")
            .gte("start_at", window_from.isoformat())
            .lte("start_at", window_to.isoformat())
            .execute()
        )

        appointments = result.data or []
        if not appointments:
            continue

        log.info("[reminders] ventana %s | citas encontradas=%d", label, len(appointments))

        for appt in appointments:
            appt_id = appt["id"]
            already_sent_field = f"reminder_{label.replace('h', '')}h_sent"

            # Evitar reenvíos
            if appt.get(already_sent_field):
                continue

            # Obtener canal activo del workspace
            channel = (
                supabase.table("channels")
                .select("phone_number_id")
                .eq("workspace_id", appt["workspace_id"])
                .eq("status", "active")
                .limit(1)
                .execute()
            )
            if not channel.data:
                log.warning("[reminders] sin canal activo | workspace=%s | appt=%s",
                            appt["workspace_id"], appt_id)
                continue

            phone_number_id = channel.data[0]["phone_number_id"]

            # Obtener teléfono del cliente
            customer = (
                supabase.table("customers")
                .select("phone, name")
                .eq("id", appt["customer_id"])
                .single()
                .execute()
            )
            if not customer.data or not customer.data.get("phone"):
                log.warning("[reminders] cliente sin teléfono | appt=%s", appt_id)
                continue

            customer_phone = customer.data["phone"]
            customer_name = customer.data.get("name", "")

            # Obtener nombre del servicio
            service = (
                supabase.table("services")
                .select("name")
                .eq("id", appt["service_id"])
                .single()
                .execute()
            )
            service_name = service.data.get("name", "tu cita") if service.data else "tu cita"

            # Formatear hora de la cita
            start_at = datetime.fromisoformat(appt["start_at"])
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

            if sent:
                # Marcar recordatorio como enviado
                supabase.table("appointments").update(
                    {already_sent_field: True}
                ).eq("id", appt_id).execute()
                log.info("[reminders] enviado | appt=%s | to=%s | ventana=%s",
                         appt_id, customer_phone, label)
            else:
                log.warning("[reminders] fallo envío | appt=%s | to=%s | ventana=%s",
                            appt_id, customer_phone, label)


async def _reminder_loop() -> None:
    """Loop asíncrono que ejecuta run_reminders() cada 30 minutos."""
    log.info("[reminders] scheduler iniciado — cada 30 minutos")
    while True:
        try:
            await run_reminders()
        except Exception as e:
            log.error("[reminders] error en ciclo | err=%s", e, exc_info=True)
        await asyncio.sleep(30 * 60)  # 30 minutos


def start_reminder_scheduler() -> asyncio.Task:
    """
    Lanza el loop de recordatorios como tarea asyncio en background.
    Llamar desde el lifespan de FastAPI.
    """
    return asyncio.create_task(_reminder_loop())
