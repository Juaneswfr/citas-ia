"""Router /workspaces/{workspace_id}/appointment-history — historial completo de citas, con filtros y exportación.

Una consulta, no una lista fija: texto (cliente, teléfono o servicio), estados, rango de fechas (en los
días del negocio, no en UTC), profesional, servicio y cliente. Devuelve la página pedida, cuántas citas
coinciden y el resumen por estado de TODO el filtro (no solo de la página), que alimenta los contadores.

La ruta no es `/appointments/history` a propósito: `/appointments/{appointment_id}` la capturaría.
"""
import csv
import io
import re
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.routes.search import like_pattern
from core.database import get_db
from core.security import require_workspace_access
from services.day_bounds import AFTER_TO_DAY, FROM_DAY

router = APIRouter(tags=["appointment-history"])

STATUSES = ("pending", "confirmed", "completed", "cancelled", "noshow", "rescheduled")
MANAGER_ROLES = ("super_admin", "workspace_owner", "manager")
MAX_EXPORT = 5000
_CSV_DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


class HistoryItem(BaseModel):
    id: str
    start_at: datetime
    end_at: datetime
    status: str
    customer_id: str
    customer_name: Optional[str]
    customer_phone: str
    service_id: str
    service_name: str
    calendar_id: Optional[str]
    staff_name: Optional[str]
    price_cop: int
    is_home_service: bool
    cancellation_reason: Optional[str]
    cancelled_by_name: Optional[str]
    booked_by: str  # 'agent' (la agendó el agente por WhatsApp) | 'panel' (la creó una persona del equipo)
    created_at: datetime


class HistorySummary(BaseModel):
    total: int
    completed: int
    cancelled: int
    noshow: int
    upcoming: int            # pendientes y confirmadas
    revenue_cop: Optional[int]  # solo dueño y administradores: cobrado en las completadas


class HistoryOut(BaseModel):
    items: list[HistoryItem]
    matching: int             # cuántas coinciden con el filtro (incluido el estado): para paginar
    summary: HistorySummary   # por estado, ignorando el filtro de estado: para los contadores
    limit: int
    offset: int


_ITEMS_SQL = """
    SELECT a.id, a.start_at, a.end_at, a.status, a.calendar_id, a.is_home_service, a.cancellation_reason,
           a.created_at, (a.price_cop + a.home_service_price_cop) AS price_cop,
           CASE WHEN a.created_by IS NULL THEN 'agent' ELSE 'panel' END AS booked_by,
           cu.id AS customer_id, cu.name AS customer_name, cu.phone AS customer_phone,
           s.id AS service_id, s.name AS service_name,
           COALESCE(u.name, c.name) AS staff_name, cb.name AS cancelled_by_name
    FROM appointments a
    JOIN customers cu ON cu.id = a.customer_id
    JOIN services s ON s.id = a.service_id
    LEFT JOIN calendars c ON c.id = a.calendar_id
    LEFT JOIN workspace_members wm ON wm.id = c.member_id
    LEFT JOIN users u ON u.id = wm.user_id
    LEFT JOIN users cb ON cb.id = a.cancelled_by
    WHERE {where}
    ORDER BY a.start_at {direction}, a.id
    LIMIT :limit OFFSET :offset
"""

_SUMMARY_SQL = """
    SELECT a.status, COUNT(*)::int AS n,
           COALESCE(SUM(a.price_cop + a.home_service_price_cop), 0)::int AS revenue
    FROM appointments a
    JOIN customers cu ON cu.id = a.customer_id
    JOIN services s ON s.id = a.service_id
    WHERE {where}
    GROUP BY a.status
"""


def build_filters(
    workspace_id: str, q: str, from_date: Optional[date], to_date: Optional[date],
    calendar_id: Optional[str], service_id: Optional[str], customer_id: Optional[str],
) -> tuple[list[str], dict]:
    """Condiciones del filtro (sin el estado) y sus parámetros. Nada del usuario se concatena al SQL."""
    where = ["a.workspace_id = :workspace_id"]
    params: dict = {"workspace_id": workspace_id}
    term = q.strip()
    if term:
        params["p"] = like_pattern(term)
        clauses = ["cu.name ILIKE :p ESCAPE '\\'", "cu.phone ILIKE :p ESCAPE '\\'", "s.name ILIKE :p ESCAPE '\\'"]
        digits = re.sub(r"\D", "", term)
        if len(digits) >= 3:  # «300 111» encuentra 573001112233
            params["d"] = f"%{digits}%"
            clauses.append("regexp_replace(cu.phone, '[^0-9]', '', 'g') LIKE :d")
        where.append("(" + " OR ".join(clauses) + ")")
    if from_date:
        where.append(f"a.start_at >= {FROM_DAY}")
        params["from_date"] = from_date
    if to_date:
        where.append(f"a.start_at < {AFTER_TO_DAY}")
        params["to_date"] = to_date
    for column, value, name in (("calendar_id", calendar_id, "calendar_id"), ("service_id", service_id, "service_id"),
                                ("customer_id", customer_id, "customer_id")):
        if value:
            where.append(f"a.{column} = :{name}")
            params[name] = value
    return where, params


def _check_statuses(statuses: Optional[list[str]]) -> list[str]:
    picked = statuses or []
    bad = [s for s in picked if s not in STATUSES]
    if bad:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Estado inválido: {', '.join(bad)}. Usa: {', '.join(STATUSES)}.")
    return picked


@router.get(
    "/workspaces/{workspace_id}/appointment-history",
    response_model=HistoryOut,
    summary="Historial de citas con filtros, resumen por estado y paginación",
)
async def appointment_history(
    workspace_id: str,
    q: str = Query("", max_length=80),
    status_in: Optional[list[str]] = Query(None, alias="status"),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    calendar_id: Optional[str] = Query(None),
    service_id: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0, le=100_000),
    current_user: dict = Depends(require_workspace_access("staff")),
    db: AsyncSession = Depends(get_db),
):
    picked = _check_statuses(status_in)
    where, params = build_filters(workspace_id, q, from_date, to_date, calendar_id, service_id, customer_id)

    # El resumen ignora el filtro de estado: los contadores muestran cómo se reparte todo lo filtrado.
    by_status = {r["status"]: r for r in (await db.execute(
        text(_SUMMARY_SQL.format(where=" AND ".join(where))), params)).mappings().fetchall()}

    def count(*names: str) -> int:
        return sum(by_status[n]["n"] for n in names if n in by_status)

    item_where = list(where)
    item_params = {**params, "limit": limit, "offset": offset}
    if picked:
        item_where.append("a.status = ANY(:statuses)")
        item_params["statuses"] = picked
    rows = (await db.execute(
        text(_ITEMS_SQL.format(where=" AND ".join(item_where), direction="ASC" if order == "asc" else "DESC")),
        item_params,
    )).mappings().fetchall()

    # El dinero es solo para dueño y administradores (igual que las rutas de contabilidad).
    revenue = None
    if current_user.get("role") in MANAGER_ROLES:
        revenue = by_status["completed"]["revenue"] if "completed" in by_status else 0
    return HistoryOut(
        items=[dict(r) for r in rows],
        matching=count(*picked) if picked else count(*by_status),
        summary=HistorySummary(
            total=count(*by_status), completed=count("completed"), cancelled=count("cancelled"),
            noshow=count("noshow"), upcoming=count("pending", "confirmed"),
            revenue_cop=revenue,
        ),
        limit=limit,
        offset=offset,
    )


def csv_cell(value) -> str:
    """Una celda de CSV a salvo de «inyección de fórmulas»: Excel ejecuta lo que empieza por = + - @."""
    cell = "" if value is None else str(value)
    return "'" + cell if cell.startswith(_CSV_DANGEROUS) else cell


_STATUS_ES = {"pending": "Pendiente", "confirmed": "Confirmada", "completed": "Completada",
              "cancelled": "Cancelada", "noshow": "No asistió", "rescheduled": "Reagendada"}


@router.get(
    "/workspaces/{workspace_id}/appointment-history/export",
    summary="Exporta a CSV las citas del filtro (hasta 5 000)",
)
async def appointment_history_export(
    workspace_id: str,
    q: str = Query("", max_length=80),
    status_in: Optional[list[str]] = Query(None, alias="status"),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    calendar_id: Optional[str] = Query(None),
    service_id: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    current_user: dict = Depends(require_workspace_access("manager")),
    db: AsyncSession = Depends(get_db),
):
    picked = _check_statuses(status_in)
    where, params = build_filters(workspace_id, q, from_date, to_date, calendar_id, service_id, customer_id)
    if picked:
        where.append("a.status = ANY(:statuses)")
        params["statuses"] = picked
    params.update(limit=MAX_EXPORT, offset=0)
    rows = (await db.execute(text(_ITEMS_SQL.format(where=" AND ".join(where), direction="DESC")), params)
            ).mappings().fetchall()
    tz = ZoneInfo((await db.execute(text("SELECT timezone FROM workspaces WHERE id = :w"),
                                    {"w": workspace_id})).scalar_one_or_none() or "America/Bogota")

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Fecha", "Hora", "Cliente", "Teléfono", "Servicio", "Profesional", "Estado", "Precio (COP)",
                     "Agendada por", "Motivo de cancelación", "Cancelada por"])
    for r in rows:
        start = r["start_at"].astimezone(tz)
        writer.writerow([csv_cell(v) for v in (
            start.strftime("%Y-%m-%d"), start.strftime("%H:%M"), r["customer_name"], r["customer_phone"],
            r["service_name"], r["staff_name"], _STATUS_ES.get(r["status"], r["status"]), r["price_cop"],
            "Agente" if r["booked_by"] == "agent" else "Equipo", r["cancellation_reason"], r["cancelled_by_name"])])
    # BOM para que Excel abra bien las tildes.
    return Response(
        content="﻿" + out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="historial-de-citas.csv"'},
    )
