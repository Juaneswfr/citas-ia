"""
Router /workspaces/{workspace_id}/agent-alerts — Alertas del agente de IA.
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
router = APIRouter(tags=["agent-alerts"])


class AgentAlertOut(BaseModel):
    id: str
    workspace_id: str
    conversation_id: Optional[str]
    severity: str  # info | warning | error | critical
    reason: str
    resolved: bool
    created_at: str


# /count DEBE ir antes de cualquier ruta con {alert_id} para evitar ambigüedad en FastAPI
@router.get(
    "/workspaces/{workspace_id}/agent-alerts/count",
    summary="Conteo de alertas no resueltas",
    dependencies=[Depends(require_workspace_access("staff"))],
)
async def count_agent_alerts(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
):
    n = (await db.execute(
        text("SELECT COUNT(*) FROM agent_alerts WHERE workspace_id=:workspace_id AND resolved=FALSE"),
        {"workspace_id": workspace_id},
    )).scalar_one_or_none()
    return {"count": int(n or 0)}


@router.get(
    "/workspaces/{workspace_id}/agent-alerts",
    response_model=list[AgentAlertOut],
    summary="Lista alertas del agente",
    dependencies=[Depends(require_workspace_access("staff"))],
)
async def list_agent_alerts(
    workspace_id: str,
    resolved: bool = False,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        text("""
        SELECT id::text, workspace_id::text, conversation_id::text,
               severity, reason, resolved, created_at::text
        FROM agent_alerts
        WHERE workspace_id=:workspace_id AND resolved=:resolved
        ORDER BY created_at DESC
        LIMIT :limit
        """),
        {"workspace_id": workspace_id, "resolved": resolved, "limit": limit},
    )).mappings().fetchall()
    return [dict(r) for r in rows]


@router.patch(
    "/workspaces/{workspace_id}/agent-alerts/{alert_id}/resolve",
    response_model=AgentAlertOut,
    summary="Marcar alerta como resuelta",
    dependencies=[Depends(require_workspace_access("staff"))],
)
async def resolve_agent_alert(
    workspace_id: str,
    alert_id: str,
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(
        text("""
        UPDATE agent_alerts SET resolved=TRUE
        WHERE id=:alert_id AND workspace_id=:workspace_id
        RETURNING id::text, workspace_id::text, conversation_id::text,
                  severity, reason, resolved, created_at::text
        """),
        {"alert_id": alert_id, "workspace_id": workspace_id},
    )).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Alerta no encontrada.")
    await db.commit()
    return dict(row)
