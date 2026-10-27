"""Herramientas del agente de citas. El backend las ejecuta; el LLM solo propone argumentos.

workspace/customer/channel/conversation salen de CitasContext (fijado por el backend) y no existen
en los esquemas que ve el modelo. Todo id propuesto se valida contra la BD dentro del workspace.
"""
import json
import logging
import uuid
from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agents.citas.context import CitasContext
from agents.citas.errors import (CalendarFailure, CitasError, InvalidInput,
                                 NotFoundOrNotAllowed, SlotConflict)
from agents.citas.ports import CalendarFactory, CitasRepository

log = logging.getLogger(__name__)

# shortcut: no hay tabla de horarios laborales; ventana fija 09:00-18:00, subir a config por workspace.
WORK_START, WORK_END = time(9, 0), time(18, 0)
MAX_RANGE_DAYS, MAX_SLOTS, MAX_CALENDAR_CHECKS = 7, 8, 20

WRITE_TOOLS = {"create_appointment", "cancel_appointment"}


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")  # un workspace_id inyectado por el modelo se rechaza


class CheckAvailabilityArgs(_Args):
    service_id: str = Field(description="UUID del servicio (de la lista de servicios).")
    date_from: str = Field(description="Fecha inicial YYYY-MM-DD en la zona horaria del negocio.")
    date_to: str | None = Field(default=None, description="Fecha final YYYY-MM-DD (máx. 7 días). Por defecto igual a date_from.")
    calendar_id: str | None = Field(default=None, description="UUID del calendario, opcional.")


class CreateAppointmentArgs(_Args):
    service_id: str = Field(description="UUID del servicio.")
    start_at: str = Field(description="Inicio ISO 8601, p. ej. 2026-11-03T15:00:00-05:00. Debe ser un hueco devuelto por check_availability.")
    calendar_id: str | None = Field(default=None, description="UUID del calendario, opcional.")


class CancelAppointmentArgs(_Args):
    appointment_id: str = Field(description="UUID de la cita del cliente a cancelar.")


_SPECS = {
    "check_availability": ("Consulta huecos libres de un servicio en un rango de fechas.", CheckAvailabilityArgs),
    "create_appointment": ("Agenda una cita para el cliente actual. Solo después de que el cliente confirme el hueco.", CreateAppointmentArgs),
    "cancel_appointment": ("Cancela una cita del cliente actual. Solo después de que el cliente lo pida explícitamente.", CancelAppointmentArgs),
}

TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": n, "description": d, "parameters": m.model_json_schema()}}
    for n, (d, m) in _SPECS.items()
]


def _uuid(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    try:
        return str(uuid.UUID(str(value)))
    except ValueError:
        raise InvalidInput(f"{field} no es un identificador válido.") from None


def _parse_day(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise InvalidInput(f"{field} debe tener formato YYYY-MM-DD.") from None


class CitasTools:
    """Ejecuta las herramientas con el contexto fijo. `execute` nunca lanza: devuelve un dict."""

    def __init__(self, ctx: CitasContext, repo: CitasRepository, calendar_factory: CalendarFactory,
                 now=lambda: datetime.now(timezone.utc)):
        self._ctx, self._repo, self._cal, self._now = ctx, repo, calendar_factory, now
        self._tz = ZoneInfo(ctx.timezone)

    async def execute(self, name: str, args: dict) -> dict:
        """Valida args, ejecuta y registra en tool_calls. Resultado {ok, code, message, ...}."""
        try:
            if name not in _SPECS:
                raise InvalidInput("Herramienta desconocida.")
            parsed = _SPECS[name][1](**(args or {}))
            result = await getattr(self, name)(parsed)
        except ValidationError:
            result = {"ok": False, "code": "invalid_input", "message": "Argumentos inválidos."}
        except CitasError as e:
            result = {"ok": False, "code": e.code, "message": e.message}
        except Exception as e:  # BD caída, constraint, etc.: no se confirma nada
            log.error("[citas] error en herramienta | tool=%s | err=%s", name, type(e).__name__, exc_info=True)
            result = {"ok": False, "code": "internal_error", "message": "No se pudo completar la operación."}
        await self._record(name, args, result)
        return result

    async def _record(self, name: str, args: dict, result: dict) -> None:
        if not self._ctx.agent_run_id:
            return
        try:
            await self._repo.record_tool_call(self._ctx.agent_run_id, name, args or {}, result, result["ok"])
        except Exception as e:  # la auditoría no debe tumbar la respuesta
            log.warning("[citas] no se pudo registrar tool_call | tool=%s | err=%s", name, type(e).__name__)

    def _local_dt(self, value: str) -> datetime:
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            raise InvalidInput("start_at debe ser ISO 8601.") from None
        return dt.replace(tzinfo=self._tz) if dt.tzinfo is None else dt

    # ── check_availability ────────────────────────────────────────────────
    async def check_availability(self, a: CheckAvailabilityArgs) -> dict:
        """Huecos libres: descarta los ocupados en BD y luego confirma con free/busy de Calendar."""
        ws = self._ctx.workspace_id
        d0 = _parse_day(a.date_from, "date_from")
        d1 = _parse_day(a.date_to, "date_to") if a.date_to else d0
        if d1 < d0 or (d1 - d0).days >= MAX_RANGE_DAYS:
            raise InvalidInput(f"El rango debe ser de 1 a {MAX_RANGE_DAYS} días.")
        async with self._repo.transaction() as tx:
            service = await tx.get_service(ws, _uuid(a.service_id, "service_id"))
            if not service:
                raise NotFoundOrNotAllowed("Servicio no encontrado.")
            if a.calendar_id:
                cal = await tx.get_calendar(ws, _uuid(a.calendar_id, "calendar_id"))
                calendars = [cal] if cal else []
            else:
                calendars = await tx.list_calendars(ws)
            if not calendars:
                raise NotFoundOrNotAllowed("Calendario no encontrado.")
            step = timedelta(minutes=service["duration_minutes"] + service["buffer_minutes"])
            dur = timedelta(minutes=service["duration_minutes"])
            slots, checks, now = [], 0, self._now()
            for cal in calendars:
                day = d0
                while day <= d1 and len(slots) < MAX_SLOTS:
                    t = datetime.combine(day, WORK_START, self._tz)
                    close = datetime.combine(day, WORK_END, self._tz)
                    busy = await tx.busy_slots(cal["id"], t, close)
                    while t + dur <= close and len(slots) < MAX_SLOTS:
                        if t > now and not any(b0 < t + dur and b1 > t for b0, b1 in busy):
                            if checks >= MAX_CALENDAR_CHECKS:
                                break
                            checks += 1
                            if await self._calendar_free(cal, t, t + dur):
                                slots.append({"calendar_id": cal["id"], "calendar_name": cal["name"],
                                              "start_at": t.isoformat()})
                        t += step
                    day += timedelta(days=1)
        return {"ok": True, "code": "ok", "service": service["name"], "slots": slots,
                "message": "Sin huecos en ese rango." if not slots else "Huecos disponibles."}

    async def _calendar_free(self, cal: dict, start: datetime, end: datetime) -> bool:
        try:
            return await self._cal(cal).check_availability(start, end)
        except Exception as e:
            log.error("[citas] free/busy falló | err=%s", type(e).__name__)
            raise CalendarFailure("No se pudo consultar el calendario.") from None

    # ── create_appointment ────────────────────────────────────────────────
    async def create_appointment(self, a: CreateAppointmentArgs) -> dict:
        """Orden: tx → lock calendario → conflicto en BD → INSERT → Calendar → guardar event id → commit.

        Si Calendar falla se lanza y la transacción hace rollback. El resultado ok=True solo existe
        después de salir limpio del bloque `async with` (commit confirmado).
        """
        c = self._ctx
        start = self._local_dt(a.start_at)
        if start <= self._now():
            raise InvalidInput("La fecha debe ser futura.")
        event_id, cal_port = None, None
        try:
            async with self._repo.transaction() as tx:
                service = await tx.get_service(c.workspace_id, _uuid(a.service_id, "service_id"))
                if not service:
                    raise NotFoundOrNotAllowed("Servicio no encontrado.")
                cal = await self._pick_calendar(tx, a.calendar_id)
                end = start + timedelta(minutes=service["duration_minutes"])
                block_end = end + timedelta(minutes=service["buffer_minutes"])
                await tx.lock_calendar(cal["id"])
                if await tx.has_conflict(cal["id"], start, block_end):
                    raise SlotConflict("Ese horario ya no está disponible.")
                appt_id = await tx.insert_appointment(
                    workspace_id=c.workspace_id, customer_id=c.customer_id, channel_id=c.channel_id,
                    service=service, calendar_id=cal["id"], start_at=start, end_at=end)
                cal_port = self._cal(cal)
                try:
                    if not await cal_port.check_availability(start, end):
                        raise SlotConflict("Ese horario ya no está disponible.")
                    event_id = await cal_port.create_event(
                        SimpleNamespace(start_at=start), end, service_name=service["name"],
                        customer_name=await tx.get_customer_name(c.workspace_id, c.customer_id))
                except CitasError:
                    raise
                except Exception as e:
                    log.error("[citas] Calendar falló al crear | err=%s", type(e).__name__)
                    raise CalendarFailure("No se pudo crear el evento en el calendario.") from None
                if not event_id:
                    raise CalendarFailure("No se pudo crear el evento en el calendario.")
                await tx.set_google_event_id(appt_id, event_id)
        except Exception:
            if event_id and cal_port:  # commit/UPDATE falló tras crear el evento: no dejar huérfano
                try:
                    await cal_port.delete_event(event_id)
                except Exception:
                    log.error("[citas] evento huérfano en Calendar | appt=%s", appt_id)
            raise
        return {"ok": True, "code": "ok", "appointment_id": appt_id, "service": service["name"],
                "start_at": start.isoformat(), "end_at": end.isoformat(),
                "message": "Cita agendada y confirmada."}

    async def _pick_calendar(self, tx, calendar_id: str | None) -> dict:
        ws = self._ctx.workspace_id
        if calendar_id:
            cal = await tx.get_calendar(ws, _uuid(calendar_id, "calendar_id"))
        else:
            cals = await tx.list_calendars(ws)
            if len(cals) > 1:
                raise InvalidInput("Hay varios calendarios: indica calendar_id de check_availability.")
            cal = cals[0] if cals else None
        if not cal:
            raise NotFoundOrNotAllowed("Calendario no encontrado.")
        return cal

    # ── cancel_appointment ────────────────────────────────────────────────
    async def cancel_appointment(self, a: CancelAppointmentArgs) -> dict:
        """Solo cita del workspace y cliente fijos. Borra el evento dentro de la tx; si falla, rollback."""
        c = self._ctx
        async with self._repo.transaction() as tx:
            appt = await tx.get_cancellable(c.workspace_id, c.customer_id, _uuid(a.appointment_id, "appointment_id"))
            if not appt:  # mismo mensaje para "no existe" y "es de otro": no revela existencia
                raise NotFoundOrNotAllowed("No encontré esa cita a tu nombre.")
            await tx.mark_cancelled(appt["id"])
            if appt["google_event_id"]:
                cal = await tx.get_calendar(c.workspace_id, appt["calendar_id"])
                try:
                    deleted = bool(cal) and await self._cal(cal).delete_event(appt["google_event_id"])
                except Exception:
                    deleted = False
                if not deleted:
                    raise CalendarFailure("No se pudo cancelar el evento en el calendario.")
        return {"ok": True, "code": "ok", "appointment_id": appt["id"], "message": "Cita cancelada."}


def dumps(result: dict) -> str:
    """Serializa el resultado de una herramienta para el ToolMessage."""
    return json.dumps(result, ensure_ascii=False, default=str)
