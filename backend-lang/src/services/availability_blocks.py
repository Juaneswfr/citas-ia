"""Bloqueos de agenda: horarios del calendario de un profesional en los que no se reciben citas.

Un bloqueo es una fila de `availability_blocks` ligada a un calendario. Lo respetan todos los
caminos que agendan: el agente (`consultar_disponibilidad`), crear una cita (panel y agente) y
mover una cita. Google free/busy no los conoce porque viven solo en la BD de Hilo; los eventos
que el negocio crea directamente en Google Calendar sí los ve free/busy y no pasan por aquí.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import text

BLOCKED_DETAIL = "Ese horario está bloqueado en la agenda."

_OVERLAP_SQL = text("""
    SELECT id, start_at, end_at, reason
    FROM availability_blocks
    WHERE workspace_id = :w AND calendar_id = :c AND start_at < :end_at AND end_at > :start_at
    ORDER BY start_at
    LIMIT 1
""")


async def find_overlap(db, workspace_id: str, calendar_id: Optional[str],
                       start_at: datetime, end_at: datetime) -> Optional[dict]:
    """Primer bloqueo del calendario que pisa [start_at, end_at), o None. Sin calendario no hay bloqueos."""
    if not calendar_id:
        return None
    row = (await db.execute(
        _OVERLAP_SQL,
        {"w": str(workspace_id), "c": str(calendar_id), "start_at": start_at, "end_at": end_at},
    )).mappings().fetchone()
    return dict(row) if row else None
