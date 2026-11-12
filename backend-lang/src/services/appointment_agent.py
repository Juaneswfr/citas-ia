"""
Agente de citas: LLM + herramientas ejecutadas por el backend.

El vocabulario depende del tipo de negocio del workspace (`core/business_types.py`): en una
barbería quien atiende es un «barbero», en un consultorio un «doctor». Los nombres de las
herramientas son neutros (`listar_profesionales`) para que sirvan a cualquier industria.

El modelo nunca elige workspace_id, cliente, canal ni calendario: salen del contexto de la
conversación y las herramientas los cierran por closure. La confirmación al cliente la
redacta el backend solo si la cita quedó insertada o movida en BD (ver `run_agent`).

Cambiar la hora de una cita la mueve (`reagendar_cita`), nunca crea otra: mover y cancelar
viven en `services/appointment_service.py`, compartidos con el panel.
"""
import asyncio
import logging
import re
import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables.config import RunnableConfig
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, field_validator

from core.business_types import BusinessProfile, get_profile
from core.database import AsyncSessionLocal
from sqlalchemy import text

log = logging.getLogger(__name__)

MODEL = "anthropic:claude-haiku-4-5-20251001"  # mismo modelo que el dispatcher de hilo
MAX_TOOL_CALLS = 5
TIMEOUT_S = 45
HISTORY = 10

FALLBACK = "Tuvimos un inconveniente técnico. Un asesor te escribirá en breve para ayudarte con tu cita."
NOT_BOOKED = "No pude agendar la cita en este momento. Un asesor te contactará para ayudarte."
_CLAIMS_CONFIRMED = re.compile(r"confirmad|agendad|reservad|qued[óo] list", re.I)

_SYSTEM = (
    "Eres el asistente de citas de {workspace} ({business_label}). Responde siempre en español, breve y amable. "
    "Fecha de hoy: {today} (zona {tz}).\n\n"
    "SERVICIOS ACTUALES (usa estos datos, no los del historial):\n{services}\n\n"
    "{staff_heading} DISPONIBLES (usa estos datos, no los del historial):\n{staff}\n\n"
    "CITAS PRÓXIMAS DEL CLIENTE (appointment_id | servicio | fecha y hora | {staff_singular} | calendar_id | service_id):\n"
    "{upcoming}\n\n"
    "Quien atiende en este negocio es un {staff_singular}: usa esa palabra al hablar con el cliente.\n"
    "Flujo para agendar: "
    "1) Si hay varios {staff_plural} pregunta cuál prefiere el cliente, si hay uno solo selecciónalo. "
    "2) consultar_disponibilidad con el calendar_id del {staff_singular} y el service_id del servicio elegido, "
    "3) crear_cita con el mismo calendar_id y service_id. "
    "También puedes listar y cancelar citas del cliente.\n"
    "Para cambiar el día o la hora de una cita que ya existe: consultar_disponibilidad con el calendar_id y el "
    "service_id de esa cita y luego reagendar_cita con su appointment_id. "
    "Nunca uses crear_cita para mover una cita: quedaría duplicada. "
    "reagendar_cita conserva el servicio y el {staff_singular}; si el cliente quiere cambiar alguno, "
    "cancela la cita con cancelar_cita y agenda una nueva. "
    "Si el cliente ya tiene una cita próxima y pide agendar, pregúntale si quiere mover esa cita o agendar otra adicional. "
    "Si tiene varias citas y no queda claro cuál quiere mover o cancelar, pregúntale.\n"
    "Nunca afirmes que una cita está confirmada o reagendada: el sistema te dirá si se creó o se movió. "
    "No inventes servicios ni horarios.\n"
    "{agent_note}"
    "FORMATO: solo texto plano de WhatsApp. "
    "Usa *texto* para negrita, _texto_ para cursiva, ~texto~ para tachado. "
    "NO uses markdown (#, **, ```, [], ![]). NO uses listas con guiones. "
    "Separa con saltos de línea, no con símbolos raros."
)


_STAFF_SQL = text("""
    SELECT c.id AS calendar_id, COALESCE(u.name, c.name) AS nombre
    FROM calendars c
    LEFT JOIN workspace_members wm ON wm.id = c.member_id
    LEFT JOIN users u ON u.id = wm.user_id
    WHERE c.workspace_id = :workspace_id AND c.sync_status = 'active'
    ORDER BY c.created_at
""")


_UPCOMING_SQL = text("""
    SELECT a.id, a.calendar_id, a.service_id, s.name AS servicio, a.start_at,
           COALESCE(u.name, c.name) AS profesional
    FROM appointments a
    JOIN services s ON s.id = a.service_id
    LEFT JOIN calendars c ON c.id = a.calendar_id
    LEFT JOIN workspace_members wm ON wm.id = c.member_id
    LEFT JOIN users u ON u.id = wm.user_id
    WHERE a.workspace_id = :workspace_id AND a.customer_id = :customer_id
      AND a.status NOT IN ('cancelled','noshow','completed')
      AND a.start_at > :now
    ORDER BY a.start_at
    LIMIT 5
""")


async def _upcoming_text(session, workspace_id: str, customer_id, tz: ZoneInfo) -> str:
    """Citas próximas del cliente, una por línea, con lo necesario para moverlas o cancelarlas."""
    if not customer_id:
        return ""
    rows = (await session.execute(
        _UPCOMING_SQL,
        {"workspace_id": workspace_id, "customer_id": str(customer_id), "now": datetime.now(tz)},
    )).mappings().fetchall()
    return "\n".join(
        f"{r['id']} | {r['servicio']} | {r['start_at'].astimezone(tz):%d/%m/%Y %H:%M} | "
        f"{r['profesional'] or '-'} | {r['calendar_id'] or '-'} | {r['service_id']}"
        for r in rows
    )


def _profile(ctx: dict) -> BusinessProfile:
    """Perfil de industria del workspace de la conversación (genérico si no tiene tipo)."""
    return get_profile(ctx.get("workspace", {}).get("business_type"))


async def _staff_text(session, workspace_id: str, profile: BusinessProfile) -> str:
    """Quienes atienden (un calendario activo por persona), como `calendar_id | nombre`."""
    rows = (await session.execute(_STAFF_SQL, {"workspace_id": workspace_id})).mappings().fetchall()
    return ("\n".join(f"{r['calendar_id']} | {r['nombre']}" for r in rows)
            or f"Sin {profile.staff_plural} disponibles.")


def build_system_prompt(ctx: dict, services_txt: str, staff_txt: str, upcoming_txt: str = "") -> str:
    """Prompt de sistema con el vocabulario y las advertencias de la industria del negocio."""
    workspace = ctx.get("workspace", {})
    profile = _profile(ctx)
    tz = workspace.get("timezone") or "America/Bogota"
    return _SYSTEM.format(
        workspace=workspace.get("name", ""),
        business_label=profile.label,
        tz=tz,
        today=datetime.now(ZoneInfo(tz)).date(),
        services=services_txt,
        staff=staff_txt,
        upcoming=upcoming_txt or "Ninguna.",
        staff_heading=profile.staff_plural.upper(),
        staff_singular=profile.staff_singular,
        staff_plural=profile.staff_plural,
        agent_note=f"{profile.agent_note}\n" if profile.agent_note else "",
    )


def _get_llm():
    from langchain.chat_models import init_chat_model
    return init_chat_model(MODEL, temperature=0)


class _ListIn(BaseModel):
    pass


def _validate_service_uuid(v: str) -> str:
    try:
        uuid.UUID(v)
    except ValueError:
        raise ValueError(f"service_id debe ser UUID válido, recibido: {v!r}")
    return v


class _AvailIn(BaseModel):
    calendar_id: str = Field(description="ID del calendario del profesional (de listar_profesionales)")
    service_id: str = Field(description="ID del servicio (de listar_servicios)")
    fecha: str = Field(description="Fecha YYYY-MM-DD")
    horas: list[str] = Field(description="Horas candidatas HH:MM (máx. 8)", max_length=8)

    @field_validator("service_id")
    @classmethod
    def check_uuid(cls, v: str) -> str:
        return _validate_service_uuid(v)


class _CreateIn(BaseModel):
    calendar_id: str = Field(description="ID del calendario del profesional (de listar_profesionales)")
    service_id: str
    fecha: str = Field(description="Fecha YYYY-MM-DD")
    hora: str = Field(description="Hora HH:MM")

    @field_validator("service_id")
    @classmethod
    def check_uuid(cls, v: str) -> str:
        return _validate_service_uuid(v)


class _CancelIn(BaseModel):
    appointment_id: str = Field(description="ID de la cita a cancelar (de listar_mis_citas)")
    motivo: str = Field(default="Cliente solicitó cancelación", description="Motivo de cancelación")


class _RescheduleIn(BaseModel):
    appointment_id: str = Field(description="ID de la cita a mover (de las citas próximas o de listar_mis_citas)")
    fecha: str = Field(description="Nueva fecha YYYY-MM-DD")
    hora: str = Field(description="Nueva hora HH:MM")


class _ListMisIn(BaseModel):
    pass


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


def _parse(tz: ZoneInfo, fecha: str, hora: str) -> datetime:
    start = datetime.combine(date.fromisoformat(fecha), time.fromisoformat(hora), tzinfo=tz)
    if start <= datetime.now(tz):
        raise ValueError("la fecha y hora ya pasaron")
    return start


def build_tools(ctx: dict, state: dict) -> list[StructuredTool]:
    """Herramientas atadas al contexto. `state["booked"]` solo se llena con la fila de la BD."""
    ws = ctx["workspace_id"]
    tz = ZoneInfo(ctx.get("workspace", {}).get("timezone") or "America/Bogota")
    profile = _profile(ctx)

    async def _service(session, service_id):
        return (await session.execute(
            text("SELECT id,name,duration_minutes,price_cop FROM services "
                 "WHERE id=:service_id AND workspace_id=:workspace_id AND is_active=TRUE"),
            {"service_id": service_id, "workspace_id": ws},
        )).mappings().fetchone()

    async def _calendar(session, calendar_id: str | None = None):
        if calendar_id:
            return (await session.execute(
                text("SELECT * FROM calendars WHERE id=:calendar_id AND workspace_id=:workspace_id AND sync_status='active'"),
                {"calendar_id": calendar_id, "workspace_id": ws},
            )).mappings().fetchone()
        return (await session.execute(
            text("SELECT * FROM calendars WHERE workspace_id=:workspace_id AND sync_status='active' "
                 "ORDER BY created_at LIMIT 1"),
            {"workspace_id": ws},
        )).mappings().fetchone()

    async def listar_servicios() -> str:
        async with AsyncSessionLocal() as session:
            rows = (await session.execute(
                text("SELECT id,name,duration_minutes,price_cop FROM services "
                     "WHERE workspace_id=:workspace_id AND is_active=TRUE"),
                {"workspace_id": ws},
            )).mappings().fetchall()
        return "\n".join(f"{r['id']} | {r['name']} | {r['duration_minutes']} min | ${r['price_cop']} COP"
                         for r in rows) or "Sin servicios activos."

    async def listar_profesionales() -> str:
        async with AsyncSessionLocal() as session:
            return await _staff_text(session, ws, profile)

    async def consultar_disponibilidad(calendar_id: str, service_id: str, fecha: str, horas: list[str]) -> str:
        from services.calendar_service import CalendarService
        try:
            async with AsyncSessionLocal() as session:
                svc = await _service(session, service_id)
                cal = None
                if svc:
                    cal = await _calendar(session, calendar_id)
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
            log.warning("[agent] disponibilidad fallo | err=%s: %s", type(e).__name__, e)
            return "ERROR: no se pudo consultar la disponibilidad (revisa fecha YYYY-MM-DD y horas HH:MM)."

    async def crear_cita(calendar_id: str, service_id: str, fecha: str, hora: str) -> str:
        from api.routes.appointments import create_appointment
        from schemas.appointment import AppointmentCreate
        if not (ctx.get("customer_id") and ctx.get("channel_id")):
            return "ERROR: no hay cliente o canal en la conversación."
        try:
            start = _parse(tz, fecha, hora)
            async with AsyncSessionLocal() as session:
                svc = await _service(session, service_id)
                cal = await _calendar(session, calendar_id) if svc else None
                if not svc or not cal:
                    return "ERROR: servicio o calendario no disponible."
                # Reutiliza el endpoint: free/busy, evento en Google Calendar, INSERT y auditoría
                row = await create_appointment(
                    ws,
                    AppointmentCreate(customer_id=str(ctx["customer_id"]), service_id=str(svc["id"]),
                                      channel_id=str(ctx["channel_id"]), calendar_id=str(cal["id"]),
                                      start_at=start, price_cop=svc["price_cop"]),
                    {"sub": None}, session)
            state["booked"] = {"id": row["id"], "service": svc["name"], "start": start}
            return "OK: cita creada."
        except HTTPException as e:
            state["create_failed"] = True
            return f"ERROR: no se pudo crear la cita ({e.status_code}: {e.detail})"
        except Exception as e:
            state["create_failed"] = True
            log.warning("[agent] crear_cita fallo | err=%s: %s", type(e).__name__, e)
            return "ERROR: no se pudo crear la cita."

    async def listar_mis_citas() -> str:
        if not ctx.get("customer_id"):
            return "ERROR: no hay cliente en la conversación."
        async with AsyncSessionLocal() as session:
            return (await _upcoming_text(session, ws, ctx["customer_id"], tz)
                    or "No tienes citas próximas agendadas.")

    async def reagendar_cita(appointment_id: str, fecha: str, hora: str) -> str:
        from services import appointment_service
        if not ctx.get("customer_id"):
            return "ERROR: no hay cliente en la conversación."
        if not _is_uuid(appointment_id):
            return "ERROR: appointment_id inválido. Usa el ID de las citas próximas del cliente."
        try:
            start = _parse(tz, fecha, hora)
            async with AsyncSessionLocal() as session:
                # Mueve la misma cita y su evento de Google Calendar: no se crea otra fila
                row = await appointment_service.reschedule(
                    session, ws, appointment_id, start, customer_id=str(ctx["customer_id"]))
            state["rescheduled"] = {"id": row["id"], "service": row["service_name"], "start": start}
            return "OK: cita reagendada."
        except HTTPException as e:
            return f"ERROR: no se pudo mover la cita ({e.status_code}: {e.detail})"
        except Exception as e:
            log.warning("[agent] reagendar_cita fallo | err=%s: %s", type(e).__name__, e)
            return "ERROR: no se pudo mover la cita (revisa fecha YYYY-MM-DD y hora HH:MM)."

    async def cancelar_cita(appointment_id: str, motivo: str = "Cliente solicitó cancelación") -> str:
        from services import appointment_service
        if not ctx.get("customer_id"):
            return "ERROR: no hay cliente en la conversación."
        if not _is_uuid(appointment_id):
            return "ERROR: appointment_id inválido. Usa el ID de las citas próximas del cliente."
        try:
            async with AsyncSessionLocal() as session:
                await appointment_service.cancel(
                    session, ws, appointment_id, reason=motivo, customer_id=str(ctx["customer_id"]))
            log.info("[agent] cita cancelada | id=%s | conv=%s", appointment_id, ctx.get("conversation_id"))
            state["cancelled"] = appointment_id
            return "OK: cita cancelada."
        except HTTPException as e:
            return f"ERROR: no se pudo cancelar la cita ({e.status_code}: {e.detail})"
        except Exception as e:
            log.warning("[agent] cancelar_cita fallo | err=%s: %s", type(e).__name__, e)
            return "ERROR: no se pudo cancelar la cita."

    return [
        StructuredTool.from_function(coroutine=listar_profesionales, name="listar_profesionales",
                                     description=f"Lista los {profile.staff_plural} disponibles con su calendar_id. "
                                                 "Llama primero antes de consultar disponibilidad.",
                                     args_schema=_ListIn),
        StructuredTool.from_function(coroutine=listar_servicios, name="listar_servicios",
                                     description="Lista los servicios activos.", args_schema=_ListIn),
        StructuredTool.from_function(coroutine=consultar_disponibilidad, name="consultar_disponibilidad",
                                     description=f"Indica si horas candidatas de una fecha están libres para el {profile.staff_singular} elegido.",
                                     args_schema=_AvailIn),
        StructuredTool.from_function(coroutine=crear_cita, name="crear_cita",
                                     description=f"Crea la cita en un horario libre con el {profile.staff_singular} elegido.",
                                     args_schema=_CreateIn),
        StructuredTool.from_function(coroutine=listar_mis_citas, name="listar_mis_citas",
                                     description="Lista las citas próximas del cliente: appointment_id | servicio | "
                                                 f"fecha y hora | {profile.staff_singular} | calendar_id | service_id.",
                                     args_schema=_ListMisIn),
        StructuredTool.from_function(coroutine=reagendar_cita, name="reagendar_cita",
                                     description="Mueve una cita existente del cliente a otro día u hora libre, con el "
                                                 f"mismo servicio y el mismo {profile.staff_singular}. "
                                                 "Úsala en vez de crear_cita cuando el cliente quiere cambiar su cita.",
                                     args_schema=_RescheduleIn),
        StructuredTool.from_function(coroutine=cancelar_cita, name="cancelar_cita",
                                     description="Cancela una cita del cliente por su ID.",
                                     args_schema=_CancelIn),
    ]


async def _loop(llm, ctx: dict, message: str, state: dict) -> str:
    tools = build_tools(ctx, state)
    by_name = {t.name: t for t in tools}
    bound = llm.bind_tools(tools)
    ws = ctx["workspace_id"]
    async with AsyncSessionLocal() as session:
        hist = (await session.execute(
            text(
                "SELECT direction,content FROM messages WHERE conversation_id=:conversation_id AND workspace_id=:workspace_id "
                "AND content IS NOT NULL ORDER BY created_at DESC LIMIT :limit"
            ),
            {"conversation_id": ctx["conversation_id"], "workspace_id": ctx["workspace_id"], "limit": HISTORY},
        )).mappings().fetchall()
        services_rows = (await session.execute(
            text("SELECT id,name,duration_minutes,price_cop FROM services WHERE workspace_id=:ws AND is_active=TRUE"),
            {"ws": ws},
        )).mappings().fetchall()
        staff_txt = await _staff_text(session, ws, _profile(ctx))
        tz = ZoneInfo(ctx.get("workspace", {}).get("timezone") or "America/Bogota")
        upcoming_txt = await _upcoming_text(session, ws, ctx.get("customer_id"), tz)

    services_txt = "\n".join(
        f"{r['id']} | {r['name']} | {r['duration_minutes']} min | ${r['price_cop']} COP"
        for r in services_rows
    ) or "Sin servicios activos."

    msgs = [SystemMessage(build_system_prompt(ctx, services_txt, staff_txt, upcoming_txt))]
    msgs += [(HumanMessage if r["direction"] == "inbound" else AIMessage)(r["content"])
             for r in reversed(list(hist))]
    if not hist or hist[0]["content"] != message:  # el inbound ya se guarda antes de correr el agente
        msgs.append(HumanMessage(message))

    _phone = ctx.get("customer_phone", "")
    _thread = f"{_phone}-{ctx.get('conversation_id', '')}" if _phone else str(ctx.get("conversation_id", ""))
    lc_config = RunnableConfig(
        metadata={
            "thread_id": _thread,
            "workspace_id": str(ctx.get("workspace_id", "")),
            "customer_phone": _phone,
        },
        configurable={"thread_id": _thread},
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
            if state.get("booked") or state.get("rescheduled"):
                return ""


def _confirmation(b: dict) -> str:
    return f"Tu cita de {b['service']} quedó confirmada para el {b['start']:%d/%m/%Y} a las {b['start']:%H:%M}."


def _rescheduled(b: dict) -> str:
    return f"Tu cita de {b['service']} quedó reagendada para el {b['start']:%d/%m/%Y} a las {b['start']:%H:%M}."


def _done(state: dict) -> dict | None:
    """Respuesta escrita por el backend cuando la cita quedó creada o movida en la BD."""
    if state.get("booked"):
        return {"reply_text": _confirmation(state["booked"]), "booked": True, "rescheduled": False, "error": None}
    if state.get("rescheduled"):
        return {"reply_text": _rescheduled(state["rescheduled"]), "booked": False, "rescheduled": True, "error": None}
    return None


async def run_agent(ctx: dict, message: str, llm=None) -> dict:
    """Devuelve {"reply_text", "booked": bool, "rescheduled": bool, "error": str|None}. No lanza por fallos del LLM."""
    state: dict = {}
    try:
        text_reply = await asyncio.wait_for(_loop(llm or _get_llm(), ctx, message, state), TIMEOUT_S)
    except Exception as e:
        err = type(e).__name__
        log.error("[agent] llm/herramientas fallaron | conv=%s | err=%s", ctx.get("conversation_id"), err)
        # la cita ya está creada o movida en BD: es verdad
        return _done(state) or {"reply_text": FALLBACK, "booked": False, "rescheduled": False,
                                "error": f"agent_{err}"}
    if done := _done(state):
        return done
    if state.get("limit"):
        return {"reply_text": NOT_BOOKED, "booked": False, "rescheduled": False, "error": "tool_limit"}
    if state.get("create_failed") or not text_reply.strip() or _CLAIMS_CONFIRMED.search(text_reply):
        return {"reply_text": NOT_BOOKED if state.get("create_failed") or text_reply.strip() else FALLBACK,
                "booked": False, "rescheduled": False,
                "error": "create_failed" if state.get("create_failed") else None}
    return {"reply_text": text_reply.strip(), "booked": False, "rescheduled": False, "error": None}
