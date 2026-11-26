"""Detalle de costos de IA por cliente, por ejecución y por cita (Zumit Manager › Costos).

Responde tres preguntas de un negocio, de lo general a lo particular:
1. ¿Qué clientes cuestan más? (`customers`)
2. ¿Cuánto costó cada ejecución del agente de un cliente (un «trace» de LangSmith)? (`customer`)
3. ¿Cuánto costó LLEGAR a cada cita? (`customer`, campo `appointments`)

Costo de una ejecución = el real de LangSmith si ya se sincronizó (`ls_cost_usd`), si no la estimación por tokens
(`cost_usd`). Una ejecución que no tiene ninguna de las dos está «sin medir» (anterior a la migración 024): no cuenta
como gratis. «Costo de llegar a una cita» = suma de las ejecuciones del cliente desde la cita anterior del asistente
(o desde siempre) hasta la que la creó, la misma regla de `billing_insights.ai_cost_per_appointment`.
Solo las citas que creó el asistente (`created_by IS NULL`) tienen costo de IA; las del panel no.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text

from services import billing_costs as bc

log = logging.getLogger(__name__)

MAX_CUSTOMERS = 200
MAX_RUNS = 400
MAX_BOOKINGS = 100

_COST = "COALESCE(r.ls_cost_usd, r.cost_usd)"
_TOKENS = "COALESCE(r.ls_tokens, r.input_tokens + r.output_tokens)"


def _cop(usd: Optional[float], usd_cop: Optional[float]) -> Optional[int]:
    return round(usd * usd_cop) if usd is not None and usd_cop else None


def _source(with_ls: int, measured: int) -> Optional[str]:
    """De dónde sale el costo de un conjunto de ejecuciones."""
    if measured == 0:
        return None
    return "langsmith" if with_ls >= measured else ("mixed" if with_ls else "estimate")


def run_source(ls_cost, est_cost) -> Optional[str]:
    if ls_cost is not None:
        return "langsmith"
    return "estimate" if est_cost is not None else None


def thread_name(workspace: str, phone: Optional[str]) -> str:
    """El mismo nombre de hilo que ve LangSmith (`appointment_agent._thread_id`): «Negocio | Teléfono»."""
    return " | ".join(p for p in (workspace.strip(), (phone or "").strip()) if p)


def allocate_to_bookings(runs: list[dict], bookings: list[dict]) -> tuple[list[dict], list[dict]]:
    """Reparte las ejecuciones entre las citas del asistente.

    `runs` y `bookings` vienen con `started_at` / `created_at` (datetime). Cada cita se lleva las ejecuciones que ocurrieron
    después de la cita anterior y hasta su creación. Devuelve (citas con su costo, ejecuciones que no llevaron a una cita).
    """
    bookings = sorted(bookings, key=lambda b: b["created_at"])
    out, used = [], set()
    prev = None
    for b in bookings:
        mine = [r for r in runs if r["started_at"] <= b["created_at"] and (prev is None or r["started_at"] > prev)]
        used.update(id(r) for r in mine)
        measured = [r for r in mine if r["cost_usd"] is not None]
        out.append({
            **b,
            "runs": len(mine),
            "unmeasured": len(mine) - len(measured),
            "cost_usd": sum(r["cost_usd"] for r in measured),
            "tokens": sum(r["tokens"] or 0 for r in mine),
        })
        prev = b["created_at"]
    leftovers = [r for r in runs if id(r) not in used]
    return out, leftovers


async def customers(db, workspace_id: str, days: int) -> dict:
    """Clientes del negocio ordenados por lo que costaron de IA en los últimos `days` días."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    usd_cop = await bc.load_usd_cop(db)
    try:
        rows = (await db.execute(
            text(f"""
            SELECT cu.id, cu.name, cu.phone,
                   COUNT(r.id) AS runs, COALESCE(SUM(r.llm_calls), 0) AS calls,
                   COALESCE(SUM({_TOKENS}), 0) AS tokens,
                   COALESCE(SUM({_COST}), 0) AS usd,
                   COUNT({_COST}) AS measured, COUNT(r.ls_cost_usd) AS with_ls,
                   MAX(r.started_at) AS last_at,
                   (SELECT COUNT(*) FROM appointments a
                     WHERE a.customer_id = cu.id AND a.workspace_id = :w AND a.created_by IS NULL
                       AND a.created_at >= :since) AS bookings
            FROM agent_runs r
            JOIN conversations cv ON cv.id = r.conversation_id
            JOIN customers cu ON cu.id = cv.customer_id
            WHERE r.workspace_id = :w AND r.started_at >= :since
            GROUP BY cu.id, cu.name, cu.phone
            ORDER BY usd DESC, runs DESC LIMIT {MAX_CUSTOMERS}"""),
            {"w": workspace_id, "since": since},
        )).mappings().fetchall()
    except Exception as exc:
        await db.rollback()
        log.warning("[costos] detalle por cliente no disponible (¿falta la migración 024?) | err=%s", type(exc).__name__)
        return {"available": False}

    items = []
    for r in rows:
        usd = float(r["usd"])
        bookings = int(r["bookings"])
        items.append({
            "customer_id": str(r["id"]), "name": r["name"], "phone": r["phone"],
            "runs": int(r["runs"]), "calls": int(r["calls"]), "tokens": int(r["tokens"]),
            "cost_usd": usd, "cost_cop": _cop(usd, usd_cop),
            "unmeasured": int(r["runs"]) - int(r["measured"]),
            "source": _source(int(r["with_ls"]), int(r["measured"])),
            "bookings": bookings,
            "per_booking_usd": usd / bookings if bookings else None,
            "per_booking_cop": _cop(usd / bookings, usd_cop) if bookings else None,
            "last_at": r["last_at"].isoformat() if r["last_at"] else None,
        })
    return {"available": True, "days": days, "usd_cop": usd_cop, "items": items,
            "truncated": len(rows) >= MAX_CUSTOMERS}


async def customer(db, workspace_id: str, customer_id: str) -> Optional[dict]:
    """Ejecuciones y citas de un cliente, con lo que costó cada una y lo que costó llegar a cada cita. None si no existe."""
    try:
        uuid.UUID(customer_id)
    except ValueError:
        return None
    head = (await db.execute(
        text("""SELECT cu.id, cu.name, cu.phone, w.name AS workspace
                FROM customers cu JOIN workspaces w ON w.id = cu.workspace_id
                WHERE cu.id = :c AND cu.workspace_id = :w"""),
        {"c": customer_id, "w": workspace_id},
    )).mappings().fetchone()
    if not head:
        return None
    usd_cop = await bc.load_usd_cop(db)
    # `model` existe desde la migración 027: sin ella se repite la consulta con NULL en su lugar.
    run_rows = None
    for model_col in ("r.model", "NULL::text"):
        try:
            run_rows = (await db.execute(
                text(f"""
                SELECT r.id, r.conversation_id, r.started_at, r.ended_at, r.status, {model_col} AS model, r.llm_calls,
                       {_TOKENS} AS tokens, r.cost_usd, r.ls_cost_usd, {_COST} AS cost,
                       left(r.input_summary, 140) AS input, left(r.output_summary, 140) AS output
                FROM agent_runs r JOIN conversations cv ON cv.id = r.conversation_id
                WHERE cv.customer_id = :c AND cv.workspace_id = :w
                ORDER BY r.started_at DESC LIMIT {MAX_RUNS}"""),
                {"c": customer_id, "w": workspace_id},
            )).mappings().fetchall()
            break
        except Exception as exc:
            await db.rollback()
            log.warning("[costos] detalle de cliente (%s) falló | err=%s", model_col, type(exc).__name__)
    if run_rows is None:
        return {"available": False}
    book_rows = (await db.execute(
        text(f"""
        SELECT a.id, a.created_at, a.start_at, a.status, a.price_cop, s.name AS service
        FROM appointments a LEFT JOIN services s ON s.id = a.service_id
        WHERE a.customer_id = :c AND a.workspace_id = :w AND a.created_by IS NULL
        ORDER BY a.created_at DESC LIMIT {MAX_BOOKINGS}"""),
        {"c": customer_id, "w": workspace_id},
    )).mappings().fetchall()

    runs = [{
        "id": str(r["id"]), "started_at": r["started_at"], "ended_at": r["ended_at"], "status": r["status"],
        "model": r["model"], "calls": int(r["llm_calls"] or 0), "tokens": int(r["tokens"] or 0) if r["tokens"] is not None else None,
        "cost_usd": float(r["cost"]) if r["cost"] is not None else None,
        "source": run_source(r["ls_cost_usd"], r["cost_usd"]), "input": r["input"], "output": r["output"],
    } for r in run_rows]
    bookings = [{
        "id": str(b["id"]), "created_at": b["created_at"], "start_at": b["start_at"], "status": b["status"],
        "price_cop": b["price_cop"], "service": b["service"],
    } for b in book_rows]
    booked, leftovers = allocate_to_bookings(runs, bookings)

    def _iso(v):
        return v.isoformat() if v else None

    total_usd = sum(r["cost_usd"] for r in runs if r["cost_usd"] is not None)
    return {
        "available": True,
        "customer": {"id": str(head["id"]), "name": head["name"], "phone": head["phone"]},
        "thread": thread_name(head["workspace"], head["phone"]),
        "usd_cop": usd_cop,
        "totals": {
            "runs": len(runs), "cost_usd": total_usd, "cost_cop": _cop(total_usd, usd_cop),
            "unmeasured": sum(1 for r in runs if r["cost_usd"] is None),
            "without_booking_usd": sum(r["cost_usd"] for r in leftovers if r["cost_usd"] is not None),
            "without_booking_runs": len(leftovers),
        },
        "appointments": [{
            "id": b["id"], "service": b["service"], "status": b["status"], "price_cop": b["price_cop"],
            "created_at": _iso(b["created_at"]), "start_at": _iso(b["start_at"]),
            "runs": b["runs"], "unmeasured": b["unmeasured"], "tokens": b["tokens"],
            "cost_usd": b["cost_usd"], "cost_cop": _cop(b["cost_usd"], usd_cop),
        } for b in sorted(booked, key=lambda x: x["created_at"], reverse=True)],
        "runs": [{
            "id": r["id"], "started_at": _iso(r["started_at"]),
            "seconds": round((r["ended_at"] - r["started_at"]).total_seconds(), 1) if r["ended_at"] else None,
            "status": r["status"], "model": r["model"], "calls": r["calls"], "tokens": r["tokens"],
            "cost_usd": r["cost_usd"], "cost_cop": _cop(r["cost_usd"], usd_cop), "source": r["source"],
            "input": r["input"], "output": r["output"],
        } for r in runs],
        "truncated": len(run_rows) >= MAX_RUNS,
    }
