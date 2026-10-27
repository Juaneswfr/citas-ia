"""
CalendarService — Integración con Google Calendar.

Principio VI (Constitución): Google Calendar es la fuente de verdad de disponibilidad.
Responsabilidad única (Principio X): solo maneja operaciones de Google Calendar.
"""
import logging
from datetime import datetime
from typing import Optional

log = logging.getLogger(__name__)


class CalendarService:
    """
    Wrapper sobre la API de Google Calendar para un calendario específico.
    Recibe los datos del calendario (con token cifrado) y opera sobre él.
    """

    def __init__(self, calendar_data: dict):
        """
        Args:
            calendar_data: Fila completa de la tabla `calendars` (incluye token cifrado).
        """
        self._calendar_id = calendar_data["google_calendar_id"]
        self._encrypted_token = calendar_data["oauth_refresh_token_encrypted"]
        self._client = None  # inicializado lazy en _get_client()

    async def _get_client(self):
        """Construye el cliente de Google Calendar descifrando el token OAuth."""
        if self._client:
            return self._client
        from integrations.google_calendar import build_calendar_client
        self._client = await build_calendar_client(self._encrypted_token)
        return self._client

    async def check_availability(self, start_at: datetime, end_at: datetime) -> bool:
        """
        Consulta free/busy para el slot dado.

        Returns:
            True si el slot está disponible, False si está ocupado.

        Raises:
            Exception: Si la API de Google no responde (el caller debe manejar).
        """
        client = await self._get_client()
        body = {
            "timeMin": start_at.isoformat(),
            "timeMax": end_at.isoformat(),
            "items": [{"id": self._calendar_id}],
        }
        result = client.freebusy().query(body=body).execute()
        busy = result.get("calendars", {}).get(self._calendar_id, {}).get("busy", [])
        return len(busy) == 0

    async def create_event(
        self,
        appointment_data,
        end_at: datetime,
        service_name: str = "",
        customer_name: str = "",
    ) -> Optional[str]:
        """
        Crea un evento en Google Calendar.

        Returns:
            google_event_id si se creó exitosamente, None si falló.

        Principio VIII: El caller debe verificar que el retorno no sea None
        antes de confirmar la cita.
        """
        client = await self._get_client()
        summary = f"Cita: {service_name}" if service_name else "Cita (CitasIA)"
        description_parts = ["Cita agendada via CitasIA"]
        if customer_name:
            description_parts.append(f"Cliente: {customer_name}")
        event = {
            "summary": summary,
            "start": {"dateTime": appointment_data.start_at.isoformat()},
            "end": {"dateTime": end_at.isoformat()},
            "description": " | ".join(description_parts),
        }
        try:
            result = (
                client.events()
                .insert(calendarId=self._calendar_id, body=event)
                .execute()
            )
            return result.get("id")
        except Exception as e:
            log.error("[calendar] error creando evento | err=%s", e)
            return None

    async def delete_event(self, google_event_id: str) -> bool:
        """
        Elimina un evento de Google Calendar.

        Returns:
            True si se eliminó, False si falló.
        """
        client = await self._get_client()
        try:
            client.events().delete(calendarId=self._calendar_id, eventId=google_event_id).execute()
            return True
        except Exception as e:
            log.error("[calendar] error eliminando evento | event=%s | err=%s", google_event_id, e)
            return False

    async def update_event(self, google_event_id: str, new_start: datetime, new_end: datetime) -> bool:
        """Mueve un evento existente a un nuevo horario."""
        client = await self._get_client()
        try:
            event = client.events().get(calendarId=self._calendar_id, eventId=google_event_id).execute()
            event["start"] = {"dateTime": new_start.isoformat()}
            event["end"] = {"dateTime": new_end.isoformat()}
            client.events().update(calendarId=self._calendar_id, eventId=google_event_id, body=event).execute()
            return True
        except Exception as e:
            log.error("[calendar] error actualizando evento | event=%s | err=%s", google_event_id, e)
            return False

    @staticmethod
    async def sync_from_notification(channel_id: str) -> None:
        """
        Procesa una notificación push de cambio en Google Calendar.
        Usa nextSyncToken incremental para traer solo eventos modificados.
        Principio VI: Mantener BD sincronizada con Calendar.
        """
        from core.database import _pool

        async with _pool.acquire() as db:
            cal_row = await db.fetchrow(
                "SELECT * FROM calendars WHERE google_notification_channel_id = $1",
                channel_id,
            )
        if not cal_row:
            log.warning("[calendar] sync: canal no encontrado | channel=%s", channel_id)
            return

        calendar_data = dict(cal_row)
        service = CalendarService(calendar_data)

        try:
            client = await service._get_client()

            params: dict = {"calendarId": calendar_data["google_calendar_id"]}
            sync_token = calendar_data.get("next_sync_token")
            if sync_token:
                params["syncToken"] = sync_token
            else:
                from datetime import timedelta, timezone
                now = datetime.now(timezone.utc)
                params["timeMin"] = (now - timedelta(days=30)).isoformat()

            events_result = client.events().list(**params).execute()
            next_sync_token = events_result.get("nextSyncToken")
            items = events_result.get("items", [])

            log.info("[calendar] sync | channel=%s | eventos=%d", channel_id, len(items))

            async with _pool.acquire() as db:
                for event in items:
                    event_id = event.get("id")
                    if event.get("status") == "cancelled":
                        appt = await db.fetchrow(
                            "SELECT id, status FROM appointments WHERE google_event_id=$1 AND workspace_id=$2",
                            event_id, calendar_data["workspace_id"],
                        )
                        if appt and appt["status"] not in {"cancelled", "completed"}:
                            await db.execute(
                                "UPDATE appointments SET status='cancelled', cancelled_by=NULL WHERE id=$1",
                                appt["id"],
                            )
                            log.info("[calendar] cita cancelada por sync | appt=%s | event=%s",
                                     appt["id"], event_id)

                if next_sync_token:
                    await db.execute(
                        "UPDATE calendars SET next_sync_token=$1 WHERE id=$2",
                        next_sync_token, calendar_data["id"],
                    )

        except Exception as e:
            log.error("[calendar] error en sync_from_notification | channel=%s | err=%s",
                      channel_id, e, exc_info=True)
