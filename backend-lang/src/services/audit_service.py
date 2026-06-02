"""
AuditService — Registro inmutable de acciones críticas.

Principio V (Constitución): Toda acción relevante MUST escribirse en audit_logs.
Responsabilidad única (Principio X): solo escribe audit_logs; nada más.
"""
import logging
from typing import Optional

from core.supabase_client import get_supabase

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
        """
        Persiste una entrada en audit_logs.

        Args:
            workspace_id: Workspace al que pertenece la acción.
            actor_user_id: ID del usuario que ejecutó la acción.
            action: Nombre de la acción, ej: 'appointment.cancel'.
            entity_type: Tipo de entidad afectada, ej: 'appointment'.
            entity_id: ID de la entidad afectada.
            before_data: Estado de la entidad antes del cambio.
            after_data: Estado de la entidad después del cambio.
            ip_address: IP del actor si está disponible.
        """
        supabase = get_supabase()
        entry = {
            "workspace_id": workspace_id,
            "actor_user_id": actor_user_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "before_data": before_data,
            "after_data": after_data,
            "ip_address": ip_address,
        }
        try:
            supabase.table("audit_logs").insert(entry).execute()
        except Exception as e:
            # El fallo de auditoría NUNCA debe romper la operación principal
            log.error("[audit] fallo al escribir | action=%s | entity=%s/%s | err=%s",
                      action, entity_type, entity_id, e)
