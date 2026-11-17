"""Freno para conversaciones cíclicas: pausa al agente antes de que siga gastando tokens.

Se evalúa ANTES de llamar al modelo, así que detectar el bucle no cuesta nada. Mira solo los
mensajes recientes de la conversación y se reinicia cuando algo prueba que hubo avance:
una cita confirmada, movida o cancelada, o una persona del negocio que tomó la conversación.

Qué cuenta como bucle:
- el agente repitió (casi) la misma respuesta varias veces seguidas, o
- llevó demasiadas respuestas sin llegar a agendar, mover ni cancelar nada.

Al pausar se apaga al agente solo con ESE cliente (`customers.agent_enabled`, el mismo
interruptor de la ficha y del chat) y se deja una alerta para el equipo. Reactivarlo es
volver a encender ese interruptor.
"""
import logging
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Optional

from sqlalchemy import text

log = logging.getLogger(__name__)

HISTORY_ROWS = 30                 # mensajes recientes que se revisan
WINDOW = timedelta(hours=6)       # lo más viejo ya es otra conversación
REPEAT_LIMIT = 3                  # respuestas seguidas casi idénticas
SIMILARITY = 0.92                 # 0..1: qué tan parecidas cuentan como la misma
MAX_AGENT_TURNS = 14              # respuestas sin lograr nada (agendar toma ~4-6)

# Respuestas del agente que prueban avance: la confirmación y el cambio de hora las escribe el
# backend; la cancelación la redacta el modelo, pero siempre dice «cancelada».
_GOAL = re.compile(r"qued[óo] (confirmada|reagendada)|(fue|qued[óo]) cancelad[ao]", re.I)

HANDOFF = "Para ayudarte mejor, una persona del equipo te escribirá en breve. ¡Gracias por tu paciencia!"

REPEATING = "estaba repitiendo la misma respuesta sin avanzar"


def _long(turns: int) -> str:
    return f"llevaba {turns} respuestas sin llegar a agendar, mover ni cancelar una cita"


def _norm(content: str) -> str:
    """Minúsculas, sin tildes ni signos: «¡Hola!» y «hola» son la misma respuesta."""
    plain = unicodedata.normalize("NFKD", content).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", plain.lower()).strip()


def _same(a: str, b: str) -> bool:
    """Misma respuesta: texto casi idéntico Y mismas cifras. «¿A las 3:00?» y «¿A las 4:00?» son
    ofertas distintas (el cliente va rechazando horas): eso es avanzar, no repetirse."""
    return re.findall(r"\d+", a) == re.findall(r"\d+", b) and SequenceMatcher(None, a, b).ratio() >= SIMILARITY


def detect_loop(rows: list[dict], now: Optional[datetime] = None) -> Optional[str]:
    """Motivo (en palabras del equipo) si la conversación es un bucle; None si va bien.

    `rows`: mensajes de la conversación, del más nuevo al más viejo, con `direction`,
    `sender_type`, `content` y `created_at`.
    """
    now = now or datetime.now(timezone.utc)
    replies: list[str] = []  # respuestas del agente desde el último avance, de la más nueva a la más vieja
    for row in rows:
        created = row.get("created_at")
        if created and now - created > WINDOW:
            break
        if row.get("direction") != "outbound":
            continue
        if row.get("sender_type") == "human":
            break  # una persona tomó la conversación: se empieza de cero
        if row.get("sender_type") != "agent":
            continue
        content = row.get("content") or ""
        if _GOAL.search(content):
            break  # hubo avance: lo anterior ya no cuenta
        replies.append(_norm(content))

    last = replies[:REPEAT_LIMIT]
    if len(last) == REPEAT_LIMIT and last[0] and all(_same(last[0], other) for other in last[1:]):
        return REPEATING
    if len(replies) >= MAX_AGENT_TURNS:
        return _long(len(replies))
    return None


async def recent_messages(db, workspace_id: str, conversation_id: str) -> list[dict]:
    rows = (await db.execute(
        text("""
            SELECT direction, sender_type, content, created_at FROM messages
            WHERE conversation_id = :c AND workspace_id = :w
            ORDER BY created_at DESC LIMIT :n
        """),
        {"c": conversation_id, "w": workspace_id, "n": HISTORY_ROWS},
    )).mappings().fetchall()
    return [dict(r) for r in rows]


async def pause_agent(db, conversation: dict, detail: str) -> None:
    """Apaga al agente con este cliente y deja la alerta para el equipo. Hace commit."""
    workspace_id, customer_id = conversation["workspace_id"], conversation.get("customer_id")
    who = None
    if customer_id:
        row = (await db.execute(
            text("SELECT COALESCE(name, phone) AS who FROM customers WHERE id = :c AND workspace_id = :w"),
            {"c": customer_id, "w": workspace_id},
        )).mappings().fetchone()
        who = row["who"] if row else None
        await db.execute(
            text("UPDATE customers SET agent_enabled = FALSE WHERE id = :c AND workspace_id = :w"),
            {"c": customer_id, "w": workspace_id},
        )
    await db.execute(
        text("""
            INSERT INTO agent_alerts (workspace_id, conversation_id, severity, reason, resolved)
            VALUES (:w, :conv, 'warning', :reason, FALSE)
        """),
        {"w": workspace_id, "conv": conversation["id"],
         "reason": (f"Agente en pausa con {who or 'este cliente'}: {detail}. Revisa la conversación y "
                    "reactívalo con el interruptor «Agente» cuando quieras.")[:500]},
    )
    await db.commit()
    log.warning("[agent] pausado por conversación cíclica | conv=%s | %s", conversation["id"], detail)
