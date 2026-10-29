"""
Agente de citas: LLM + 3 herramientas ejecutadas por el backend.

El modelo nunca elige workspace_id, cliente, canal ni calendario: salen del contexto de la
conversación y las herramientas los cierran por closure. La confirmación al cliente la
redacta el backend solo si la cita quedó insertada en BD (ver `run_agent`).
"""
import asyncio
import logging
import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables.config import RunnableConfig
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from core.database import _pool

log = logging.getLogger(__name__)

MODEL = "anthropic:claude-haiku-4-5-20251001"  # mismo modelo que el dispatcher de hilo
MAX_TOOL_CALLS = 5
TIMEOUT_S = 45
HISTORY = 10

FALLBACK = "Tuvimos un inconveniente técnico. Un asesor te escribirá en breve para ayudarte con tu cita."
NOT_BOOKED = "No pude agendar la cita en este momento. Un asesor te contactará para ayudarte."
_CLAIMS_CONFIRMED = re.compile(r"confirmad|agendad|reservad|qued[óo] list", re.I)

_SYSTEM = (
    "Eres el asistente de citas de {workspace}. Responde siempre en español, breve y amable. "
    "Usa las herramientas para listar servicios, consultar disponibilidad, crear, listar y cancelar citas. "
    "Nunca afirmes que una cita está confirmada: el sistema te dirá si se creó. "
    "No inventes servicios ni horarios. Fecha de hoy: {today} (zona {tz}).\n"
    "FORMATO: solo texto plano de WhatsApp. "
    "Usa *texto* para negrita, _texto_ para cursiva, ~texto~ para tachado. "
    "NO uses markdown (#, **, ```, [], ![]). NO uses listas con guiones. "
    "Separa con saltos de línea, no con símbolos raros."
)


def _get_llm():
    from langchain.chat_models import init_chat_model
    return init_chat_model(MODEL, temperature=0)


class _ListIn(BaseModel):
    pass


class _AvailIn(BaseModel):
    service_id: str = Field(description="ID del servicio (de listar_servicios)")
    fecha: str = Field(description="Fecha YYYY-MM-DD")
    horas: list[str] = Field(description="Horas candidatas HH:MM (máx. 8)", max_length=8)


class _CreateIn(BaseModel):
    service_id: str
    fecha: str = Field(description="Fecha YYYY-MM-DD")
    hora: str = Field(description="Hora HH:MM")


class _CancelIn(BaseModel):
    appointment_id: str = Field(description="ID de la cita a cancelar (de listar_mis_citas)")
    motivo: str = Field(default="Cliente solicitó cancelación", description="Motivo de cancelación")


class _ListMisIn(BaseModel):
    pass


def _parse(tz: ZoneInfo, fecha: str, hora: str) -> datetime:
    start = datetime.combine(date.fromisoformat(fecha), time.fromisoformat(hora), tzinfo=tz)
    if start <= datetime.now(tz):
        raise ValueError("la fecha y hora ya pasaron")
    return start


def build_tools(ctx: dict, state: dict) -> list[StructuredTool]:
    """Herramientas atadas al contexto. `state["booked"]` solo se llena con la fila de la BD."""
    ws = ctx["workspace_id"]
    tz = ZoneInfo(ctx.get("workspace", {}).get("timezone") or "America/Bogota")

    async def _service(db, service_id):
        return await db.fetchrow(
            "SELECT id,name,duration_minutes,price_cop FROM services "
            "WHERE id=$1 AND workspace_id=$2 AND is_active=TRUE", service_id, ws)

    async def _calendar(db):
        return await db.fetchrow(
            "SELECT * FROM calendars WHERE workspace_id=$1 AND sync_status='active' "
            "ORDER BY created_at LIMIT 1", ws)

    async def listar_servicios() -> str:
        async with _pool.acquire() as db:
            rows = await db.fetch(
                "SELECT id,name,duration_minutes,price_cop FROM services "
                "WHERE workspace_id=$1 AND is_active=TRUE", ws)
        return "\n".join(f"{r['id']} | {r['name']} | {r['duration_minutes']} min | ${r['price_cop']} COP"
                         for r in rows) or "Sin servicios activos."

    async def consultar_disponibilidad(service_id: str, fecha: str, horas: list[str]) -> str:
        from services.calendar_service import CalendarService
        try:
            async with _pool.acquire() as db:
                svc, cal = await _service(db, service_id), None
                if svc:
                    cal = await _calendar(db)
            if not svc:
                return "ERROR: servicio no encontrado."
            if not cal:
                return "ERROR: no hay calendario conectado."
            cs, out = CalendarService(dict(cal)), []
            for h in horas[:8]:
                start = _parse(tz, fecha, h)
                free = await cs.check_availability(start, start + timedelta(minutes=svc["duration_minutes"]))
                out.append(f"{h}: {'libre' if free else 'ocupado'}")
            return "\n".join(out)
        except Exception as e:
            log.warning("[agent] disponibilidad fallo | err=%s", type(e).__name__)
            return "ERROR: no se pudo consultar la disponibilidad (revisa fecha YYYY-MM-DD y horas HH:MM)."

    async def crear_cita(service_id: str, fecha: str, hora: str) -> str:
        from api.routes.appointments import create_appointment
        from schemas.appointment import AppointmentCreate
        if not (ctx.get("customer_id") and ctx.get("channel_id")):
            return "ERROR: no hay cliente o canal en la conversación."
        try:
            start = _parse(tz, fecha, hora)
            async with _pool.acquire() as db:
                svc = await _service(db, service_id)
                cal = await _calendar(db) if svc else None
                if not svc or not cal:
                    return "ERROR: servicio o calendario no disponible."
                # Reutiliza el endpoint: free/busy, evento en Google Calendar, INSERT y auditoría
                row = await create_appointment(
                    ws,
                    AppointmentCreate(customer_id=str(ctx["customer_id"]), service_id=str(svc["id"]),
                                      channel_id=str(ctx["channel_id"]), calendar_id=str(cal["id"]),
                                      start_at=start, price_cop=svc["price_cop"]),
                    {"sub": None}, db)
            state["booked"] = {"id": row["id"], "service": svc["name"], "start": start}
            return "OK: cita creada."
        except HTTPException as e:
            state["create_failed"] = True
            return f"ERROR: no se pudo crear la cita ({e.status_code}: {e.detail})"
        except Exception as e:
            state["create_failed"] = True
            log.warning("[agent] crear_cita fallo | err=%s", type(e).__name__)
            return "ERROR: no se pudo crear la cita."

    async def listar_mis_citas() -> str:
        if not ctx.get("customer_id"):
            return "ERROR: no hay cliente en la conversación."
        now = datetime.now(tz)
        async with _pool.acquire() as db:
            rows = await db.fetch(
                """
                SELECT a.id, s.name AS servicio, a.start_at, a.end_at, a.status
                FROM appointments a
                JOIN services s ON s.id = a.service_id
                WHERE a.workspace_id=$1 AND a.customer_id=$2
                  AND a.status NOT IN ('cancelled','noshow','completed')
                  AND a.start_at > $3
                ORDER BY a.start_at
                LIMIT 5
                """,
                ws, str(ctx["customer_id"]), now,
            )
        if not rows:
            return "No tienes citas próximas agendadas."
        return "\n".join(
            f"{r['id']} | {r['servicio']} | {r['start_at'].astimezone(tz):%d/%m/%Y %H:%M}"
            for r in rows
        )

    async def cancelar_cita(appointment_id: str, motivo: str) -> str:
        if not ctx.get("customer_id"):
            return "ERROR: no hay cliente en la conversación."
        try:
            async with _pool.acquire() as db:
                row = await db.fetchrow(
                    "SELECT id, google_event_id, status FROM appointments "
                    "WHERE id=$1 AND workspace_id=$2 AND customer_id=$3",
                    appointment_id, ws, str(ctx["customer_id"]),
                )
                if not row:
                    return "ERROR: cita no encontrada o no pertenece a este cliente."
                if row["status"] in ("cancelled", "completed", "noshow"):
                    return f"ERROR: la cita ya está en estado {row['status']}."
                await db.execute(
                    "UPDATE appointments SET status='cancelled', cancellation_reason=$1, "
                    "cancelled_by='customer', cancelled_at=now() WHERE id=$2",
                    motivo, appointment_id,
                )
                cal = await _calendar(db)
            if row.get("google_event_id") and cal:
                try:
                    from services.calendar_service import CalendarService
                    await CalendarService(dict(cal)).delete_event(row["google_event_id"])
                except Exception as ce:
                    log.warning("[agent] eliminar evento GCal fallo | event=%s | err=%s",
                                row["google_event_id"], type(ce).__name__)
            log.info("[agent] cita cancelada | id=%s | conv=%s", appointment_id, ctx.get("conversation_id"))
            state["cancelled"] = appointment_id
            return "OK: cita cancelada."
        except Exception as e:
            log.warning("[agent] cancelar_cita fallo | err=%s", type(e).__name__)
            return "ERROR: no se pudo cancelar la cita."

    return [
        StructuredTool.from_function(coroutine=listar_servicios, name="listar_servicios",
                                     description="Lista los servicios activos.", args_schema=_ListIn),
        StructuredTool.from_function(coroutine=consultar_disponibilidad, name="consultar_disponibilidad",
                                     description="Indica si horas candidatas de una fecha están libres.",
                                     args_schema=_AvailIn),
        StructuredTool.from_function(coroutine=crear_cita, name="crear_cita",
                                     description="Crea la cita en un horario libre.", args_schema=_CreateIn),
        StructuredTool.from_function(coroutine=listar_mis_citas, name="listar_mis_citas",
                                     description="Lista las citas próximas del cliente en esta conversación.",
                                     args_schema=_ListMisIn),
        StructuredTool.from_function(coroutine=cancelar_cita, name="cancelar_cita",
                                     description="Cancela una cita del cliente por su ID.",
                                     args_schema=_CancelIn),
    ]


async def _loop(llm, ctx: dict, message: str, state: dict) -> str:
    tools = build_tools(ctx, state)
    by_name = {t.name: t for t in tools}
    bound = llm.bind_tools(tools)
    async with _pool.acquire() as db:
        hist = await db.fetch(
            "SELECT direction,content FROM messages WHERE conversation_id=$1 AND workspace_id=$2 "
            "AND content IS NOT NULL ORDER BY created_at DESC LIMIT $3",
            ctx["conversation_id"], ctx["workspace_id"], HISTORY)
    msgs = [SystemMessage(_SYSTEM.format(
        workspace=ctx.get("workspace", {}).get("name", ""),
        tz=ctx.get("workspace", {}).get("timezone") or "America/Bogota",
        today=datetime.now(ZoneInfo(ctx.get("workspace", {}).get("timezone") or "America/Bogota")).date()))]
    msgs += [(HumanMessage if r["direction"] == "inbound" else AIMessage)(r["content"])
             for r in reversed(list(hist))]
    if not hist or hist[0]["content"] != message:  # el inbound ya se guarda antes de correr el agente
        msgs.append(HumanMessage(message))

    lc_config = RunnableConfig(
        metadata={
            "thread_id": str(ctx.get("conversation_id", "")),
            "workspace_id": str(ctx.get("workspace_id", "")),
        },
        configurable={"thread_id": str(ctx.get("conversation_id", ""))},
        tags=["citas"],
    )
    used = 0
    while True:
        ai = await bound.ainvoke(msgs, config=lc_config)
        calls = getattr(ai, "tool_calls", None) or []
        if not calls:
            return ai.content if isinstance(ai.content, str) else ""
        msgs.append(ai)
        for c in calls:
            if used >= MAX_TOOL_CALLS:
                state["limit"] = True
                return ""
            used += 1
            tool = by_name.get(c["name"])
            # workspace_id/canal nunca son argumentos: los campos extra del modelo se descartan en el schema
            res = await tool.ainvoke(c["args"]) if tool else "ERROR: herramienta desconocida."
            msgs.append(ToolMessage(str(res), tool_call_id=c["id"]))
            if state.get("booked"):
                return ""


def _confirmation(b: dict) -> str:
    return f"Tu cita de {b['service']} quedó confirmada para el {b['start']:%d/%m/%Y} a las {b['start']:%H:%M}."


async def run_agent(ctx: dict, message: str, llm=None) -> dict:
    """Devuelve {"reply_text", "booked": bool, "error": str|None}. No lanza por fallos del LLM."""
    state: dict = {}
    try:
        text = await asyncio.wait_for(_loop(llm or _get_llm(), ctx, message, state), TIMEOUT_S)
    except Exception as e:
        err = type(e).__name__
        log.error("[agent] llm/herramientas fallaron | conv=%s | err=%s", ctx.get("conversation_id"), err)
        if state.get("booked"):  # la cita ya está en BD: es verdad
            return {"reply_text": _confirmation(state["booked"]), "booked": True, "error": None}
        return {"reply_text": FALLBACK, "booked": False, "error": f"agent_{err}"}
    if state.get("booked"):
        return {"reply_text": _confirmation(state["booked"]), "booked": True, "error": None}
    if state.get("limit"):
        return {"reply_text": NOT_BOOKED, "booked": False, "error": "tool_limit"}
    if state.get("create_failed") or not text.strip() or _CLAIMS_CONFIRMED.search(text):
        return {"reply_text": NOT_BOOKED if state.get("create_failed") or text.strip() else FALLBACK,
                "booked": False, "error": "create_failed" if state.get("create_failed") else None}
    return {"reply_text": text.strip(), "booked": False, "error": None}
