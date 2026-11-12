"""
AuditService — Registro inmutable de acciones críticas.

Principio V (Constitución): Toda acción relevante MUST escribirse en audit_logs.
Responsabilidad única (Principio X): solo escribe audit_logs; nada más.
"""
import json
import logging
from typing import Optional

from core.database import AsyncSessionLocal
from sqlalchemy import text

log = logging.getLogger(__name__)


class AuditService:
    """Servicio estático para registrar acciones en audit_logs."""

    @staticmethod
    async def log(
        workspace_id: str,
        actor_user_id: Optional[str],
        action: str,
        entity_type: str,
        entity_id: str,
        before_data: Optional[dict] = None,
        after_data: Optional[dict] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(
                    text("""
                    INSERT INTO audit_logs
                        (workspace_id, actor_user_id, action, entity_type, entity_id, before_data, after_data)
                    VALUES (:workspace_id, :actor_user_id, :action, :entity_type, :entity_id, :before_data, :after_data)
                    """),
                    {
                        "workspace_id": workspace_id,
                        "actor_user_id": actor_user_id,
                        "action": action,
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        # default=str: las filas traen fechas y UUID que json no serializa solo
                        "before_data": json.dumps(before_data, default=str) if before_data is not None else None,
                        "after_data": json.dumps(after_data, default=str) if after_data is not None else None,
                    },
                )
                await session.commit()
        except Exception as e:
            # El fallo de auditoría NUNCA debe romper la operación principal
            log.error("[audit] fallo al escribir | action=%s | entity=%s/%s | err=%s",
                      action, entity_type, entity_id, e)
