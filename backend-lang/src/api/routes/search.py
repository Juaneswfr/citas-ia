"""Router /workspaces/{workspace_id}/search — buscador global del panel (citas, clientes y servicios).

Se consulta mientras la persona escribe, así que cada tipo devuelve pocos resultados. Todo se
acota al workspace del token; el texto de búsqueda nunca se concatena al SQL.
"""
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import require_workspace_access

router = APIRouter(tags=["search"])

MIN_CHARS = 2
LIMIT = 6


class CustomerHit(BaseModel):
    id: str
    name: Optional[str]
    phone: str
    email: Optional[str]


class ServiceHit(BaseModel):
    id: str
    name: str
    duration_minutes: int
    price_cop: int
    is_active: bool


class AppointmentHit(BaseModel):
    id: str
    start_at: datetime
    status: str
    customer_name: Optional[str]
    customer_phone: str
    service_name: str
    staff_name: Optional[str]


class SearchOut(BaseModel):
    customers: list[CustomerHit]
    services: list[ServiceHit]
    appointments: list[AppointmentHit]


def like_pattern(term: str) -> str:
    """`%término%` con `%`, `_` y `\\` del usuario escapados: «50%» busca un 50%, no «todo»."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


_CUSTOMERS_SQL = """
    SELECT id, name, phone, email FROM customers
    WHERE workspace_id = :w
      AND (name ILIKE :p ESCAPE '\\' OR email ILIKE :p ESCAPE '\\' OR phone ILIKE :p ESCAPE '\\'{digits})
    ORDER BY (name ILIKE :starts ESCAPE '\\') DESC, last_seen_at DESC NULLS LAST, name
    LIMIT :n
"""

_SERVICES_SQL = """
    SELECT id, name, duration_minutes, price_cop, is_active FROM services
    WHERE workspace_id = :w AND name ILIKE :p ESCAPE '\\'
    ORDER BY is_active DESC, name
    LIMIT :n
"""

# Las citas más cercanas a hoy primero: lo que se busca casi siempre es una cita reciente o próxima.
_APPOINTMENTS_SQL = """
    SELECT a.id, a.start_at, a.status, cu.name AS customer_name, cu.phone AS customer_phone,
           s.name AS service_name, COALESCE(u.name, c.name) AS staff_name
    FROM appointments a
    JOIN customers cu ON cu.id = a.customer_id
    JOIN services s ON s.id = a.service_id
    LEFT JOIN calendars c ON c.id = a.calendar_id
    LEFT JOIN workspace_members wm ON wm.id = c.member_id
    LEFT JOIN users u ON u.id = wm.user_id
    WHERE a.workspace_id = :w
      AND (cu.name ILIKE :p ESCAPE '\\' OR cu.phone ILIKE :p ESCAPE '\\' OR s.name ILIKE :p ESCAPE '\\'{digits})
    ORDER BY ABS(EXTRACT(EPOCH FROM (a.start_at - NOW())))
    LIMIT :n
"""


@router.get(
    "/workspaces/{workspace_id}/search",
    response_model=SearchOut,
    summary="Buscar citas, clientes y servicios del negocio",
    dependencies=[Depends(require_workspace_access("staff"))],
)
async def search(
    workspace_id: str,
    q: str = Query("", max_length=80),
    db: AsyncSession = Depends(get_db),
):
    term = q.strip()
    if len(term) < MIN_CHARS:
        return SearchOut(customers=[], services=[], appointments=[])

    params: dict = {"w": workspace_id, "p": like_pattern(term), "starts": like_pattern(term)[1:], "n": LIMIT}
    # «300 111» debe encontrar 573001112233: con 3+ dígitos también se compara el teléfono sin formato.
    digits = re.sub(r"\D", "", term)
    phone_clause = ""
    if len(digits) >= 3:
        params["d"] = f"%{digits}%"
        phone_clause = " OR regexp_replace(cu.phone, '[^0-9]', '', 'g') LIKE :d"
    customer_clause = phone_clause.replace("cu.phone", "phone")

    customers = (await db.execute(text(_CUSTOMERS_SQL.format(digits=customer_clause)), params)).mappings().fetchall()
    services = (await db.execute(text(_SERVICES_SQL), {k: v for k, v in params.items() if k in ("w", "p", "n")})
                ).mappings().fetchall()
    appointments = (await db.execute(text(_APPOINTMENTS_SQL.format(digits=phone_clause)),
                                     {k: v for k, v in params.items() if k != "starts"})).mappings().fetchall()
    return SearchOut(
        customers=[dict(r) for r in customers],
        services=[dict(r) for r in services],
        appointments=[dict(r) for r in appointments],
    )
