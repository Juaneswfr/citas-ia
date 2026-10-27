"""
AuditService — Registro inmutable de acciones críticas.

Principio V (Constitución): Toda acción relevante MUST escribirse en audit_logs.
Responsabilidad única (Principio X): solo escribe audit_logs; nada más.
"""
import json
import logging
from typing import Optional

from core.database import _pool

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
        if _pool is None:
            return
        try:
            async with _pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO audit_logs
                        (workspace_id, actor_user_id, action, entity_type, entity_id, before_data, after_data)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    workspace_id,
                    actor_user_id,
                    action,
                    entity_type,
                    entity_id,
                    json.dumps(before_data) if before_data is not None else None,
                    json.dumps(after_data) if after_data is not None else None,
                )
        except Exception as e:
            # El fallo de auditoría NUNCA debe romper la operación principal
            log.error("[audit] fallo al escribir | action=%s | entity=%s/%s | err=%s",
                      action, entity_type, entity_id, e)
