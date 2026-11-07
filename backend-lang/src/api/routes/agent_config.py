"""
Router /workspaces/{workspace_id}/agent — Configuración del agente de WhatsApp.

Separado de business_hours: el agente tiene su propio horario de respuesta,
que puede diferir del horario en que se aceptan citas.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
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
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(
        text("SELECT agent_enabled, out_of_hours_message FROM agent_config WHERE workspace_id=:workspace_id"),
        {"workspace_id": workspace_id},
    )).mappings().fetchone()
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
    db: AsyncSession = Depends(get_db),
):
    data = body.model_dump(exclude_none=True)
    if not data:
        return await get_agent_config(workspace_id, db)

    fields = list(data.keys())
    # $1=workspace_id, $2=default_ooh (INSERT only), $3...$N=update values
    set_clause = ", ".join(f"{f} = :{f}" for f in fields)
    params = {"workspace_id": workspace_id, "default_ooh": DEFAULT_OOH_MSG, **data}

    row = (await db.execute(
        text(f"""
        INSERT INTO agent_config (workspace_id, agent_enabled, out_of_hours_message)
        VALUES (:workspace_id, TRUE, :default_ooh)
        ON CONFLICT (workspace_id) DO UPDATE SET {set_clause}, updated_at = now()
        RETURNING agent_enabled, out_of_hours_message
        """),
        params,
    )).mappings().fetchone()
    await db.commit()
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
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        text(
            "SELECT day_of_week, open_time::text, close_time::text, is_active "
            "FROM agent_hours WHERE workspace_id=:workspace_id ORDER BY day_of_week"
        ),
        {"workspace_id": workspace_id},
    )).mappings().fetchall()
    if rows:
        return [dict(r) for r in rows]

    # Auto-create defaults: lun-sáb 09-21 activo, domingo inactivo
    from datetime import time as _time
    for i in range(7):
        await db.execute(
            text(
                "INSERT INTO agent_hours (workspace_id, day_of_week, open_time, close_time, is_active) "
                "VALUES (:workspace_id,:day,:open_t,:close_t,:is_active) ON CONFLICT DO NOTHING"
            ),
            {"workspace_id": workspace_id, "day": i, "open_t": _time(9, 0), "close_t": _time(21, 0), "is_active": i < 6},
        )
    await db.commit()
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
    db: AsyncSession = Depends(get_db),
):
    if len(body.hours) != 7:
        raise HTTPException(status_code=422, detail="Se requieren exactamente 7 días.")

    from datetime import time as _time
    def _t(s: str) -> _time:
        h, m = s.split(":")
        return _time(int(h), int(m))

    async with db.begin():
        for h in body.hours:
            await db.execute(
                text("""
                INSERT INTO agent_hours (workspace_id, day_of_week, open_time, close_time, is_active)
                VALUES (:workspace_id, :day_of_week, :open_time, :close_time, :is_active)
                ON CONFLICT (workspace_id, day_of_week) DO UPDATE
                SET open_time=:open_time, close_time=:close_time, is_active=:is_active
                """),
                {
                    "workspace_id": workspace_id,
                    "day_of_week": h.day_of_week,
                    "open_time": _t(h.open_time),
                    "close_time": _t(h.close_time),
                    "is_active": h.is_active,
                },
            )

    return await get_agent_hours(workspace_id, db)
