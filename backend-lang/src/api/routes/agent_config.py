"""
Router /workspaces/{workspace_id}/agent — Configuración del agente de WhatsApp.

Separado de business_hours: el agente tiene su propio horario de respuesta,
que puede diferir del horario en que se aceptan citas.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
import asyncpg
from pydantic import BaseModel

from core.database import get_db
from core.security import require_workspace_access

log = logging.getLogger(__name__)
router = APIRouter(tags=["agent"])

DEFAULT_OOH_MSG = "Hola! Por ahora estamos fuera de horario. Te responderemos en cuanto abramos. 🤙"

# ── Schemas ───────────────────────────────────────────────────────────────────

class AgentConfigOut(BaseModel):
    agent_enabled: bool
    out_of_hours_message: str


class AgentConfigUpdate(BaseModel):
    agent_enabled: Optional[bool] = None
    out_of_hours_message: Optional[str] = None


class AgentHoursOut(BaseModel):
    day_of_week: int
    open_time: str
    close_time: str
    is_active: bool


class AgentHoursUpdate(BaseModel):
    hours: list[AgentHoursOut]


# ── Config ────────────────────────────────────────────────────────────────────

@router.get(
    "/workspaces/{workspace_id}/agent/config",
    response_model=AgentConfigOut,
    summary="Configuración global del agente",
    dependencies=[Depends(require_workspace_access("staff"))],
)
async def get_agent_config(
    workspace_id: str,
    db: asyncpg.Connection = Depends(get_db),
):
    row = await db.fetchrow(
        "SELECT agent_enabled, out_of_hours_message FROM agent_config WHERE workspace_id=$1",
        workspace_id,
    )
    if not row:
        return {"agent_enabled": True, "out_of_hours_message": DEFAULT_OOH_MSG}
    return dict(row)


@router.patch(
    "/workspaces/{workspace_id}/agent/config",
    response_model=AgentConfigOut,
    summary="Actualizar configuración del agente",
    dependencies=[Depends(require_workspace_access("staff"))],
)
async def update_agent_config(
    workspace_id: str,
    body: AgentConfigUpdate,
    db: asyncpg.Connection = Depends(get_db),
):
    data = body.model_dump(exclude_none=True)
    if not data:
        return await get_agent_config(workspace_id, db)

    fields = list(data.keys())
    values = list(data.values())
    # $1=workspace_id, $2=default_ooh (INSERT only), $3...$N=update values
    set_clause = ", ".join(f"{f} = ${i+3}" for i, f in enumerate(fields))

    row = await db.fetchrow(
        f"""
        INSERT INTO agent_config (workspace_id, agent_enabled, out_of_hours_message)
        VALUES ($1, TRUE, $2)
        ON CONFLICT (workspace_id) DO UPDATE SET {set_clause}, updated_at = now()
        RETURNING agent_enabled, out_of_hours_message
        """,
        workspace_id, DEFAULT_OOH_MSG, *values,
    )
    return dict(row)


# ── Hours ─────────────────────────────────────────────────────────────────────

@router.get(
    "/workspaces/{workspace_id}/agent/hours",
    response_model=list[AgentHoursOut],
    summary="Horario del agente por día",
    dependencies=[Depends(require_workspace_access("staff"))],
)
async def get_agent_hours(
    workspace_id: str,
    db: asyncpg.Connection = Depends(get_db),
):
    rows = await db.fetch(
        "SELECT day_of_week, open_time::text, close_time::text, is_active "
        "FROM agent_hours WHERE workspace_id=$1 ORDER BY day_of_week",
        workspace_id,
    )
    if rows:
        return [dict(r) for r in rows]

    # Auto-create defaults: lun-sáb 09-21 activo, domingo inactivo
    from datetime import time as _time
    defaults = [
        (workspace_id, i, _time(9, 0), _time(21, 0), i < 6)
        for i in range(7)
    ]
    await db.executemany(
        "INSERT INTO agent_hours (workspace_id, day_of_week, open_time, close_time, is_active) "
        "VALUES ($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING",
        defaults,
    )
    return [
        {"day_of_week": i, "open_time": "09:00", "close_time": "21:00", "is_active": i < 6}
        for i in range(7)
    ]


@router.put(
    "/workspaces/{workspace_id}/agent/hours",
    response_model=list[AgentHoursOut],
    summary="Guardar horario del agente (upsert 7 días)",
    dependencies=[Depends(require_workspace_access("staff"))],
)
async def update_agent_hours(
    workspace_id: str,
    body: AgentHoursUpdate,
    db: asyncpg.Connection = Depends(get_db),
):
    if len(body.hours) != 7:
        raise HTTPException(status_code=422, detail="Se requieren exactamente 7 días.")

    from datetime import time as _time
    def _t(s: str) -> _time:
        h, m = s.split(":")
        return _time(int(h), int(m))

    async with db.transaction():
        for h in body.hours:
            await db.execute(
                """
                INSERT INTO agent_hours (workspace_id, day_of_week, open_time, close_time, is_active)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (workspace_id, day_of_week) DO UPDATE
                SET open_time=$3, close_time=$4, is_active=$5
                """,
                workspace_id, h.day_of_week, _t(h.open_time), _t(h.close_time), h.is_active,
            )

    return await get_agent_hours(workspace_id, db)
