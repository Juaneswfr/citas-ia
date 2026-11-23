"""
Costo real de la IA por negocio, leído de LangSmith.

El agente ya manda `workspace_id` en los metadatos de cada llamada al modelo y la etiqueta «citas»
(`appointment_agent._loop`), así que LangSmith sabe cuánto costó cada llamada. Aquí solo se leen y se suman por negocio y
por día (zona de Bogotá, igual que `agent_usage`).

LangSmith conserva los trazos poco tiempo (14 días en el plan base): por eso `billing_costs.sync` guarda los totales en
nuestra BD cada hora y no se consulta LangSmith al abrir la pantalla.

Lo que no se pudo comprobar sin llamar a LangSmith: la forma exacta de `list_runs` con `select` y `filter`. Está escrito
contra el SDK instalado; la prueba de conexión de Zumit Manager (Estado) y la primera sincronización lo confirman.
"""
import asyncio
import logging
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Optional
from zoneinfo import ZoneInfo

from services.billing_service import ai_cost_usd

log = logging.getLogger(__name__)

BOGOTA = ZoneInfo("America/Bogota")
TAG = "citas"
SELECT = ["id", "start_time", "extra", "total_tokens", "prompt_tokens", "completion_tokens", "total_cost"]
MAX_RUNS = 50_000  # tope de seguridad por sincronización


class LangSmithError(Exception):
    """LangSmith no está configurado o no respondió."""


def api_key() -> str:
    return os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY") or ""


def project_name() -> str:
    return os.environ.get("LANGSMITH_PROJECT") or os.environ.get("LANGCHAIN_PROJECT") or "default"


def is_configured() -> bool:
    return bool(api_key())


def _metadata(run: Any) -> dict:
    meta = getattr(run, "metadata", None)
    if isinstance(meta, dict):
        return meta
    extra = getattr(run, "extra", None) or {}
    return extra.get("metadata", {}) if isinstance(extra, dict) else {}


def aggregate(runs: Iterable[Any]) -> dict[tuple[str, date], dict]:
    """Suma las llamadas por (negocio, día de Bogotá).

    Si LangSmith no calculó el costo de una llamada (modelo sin precio cargado) se estima con sus tokens y se cuenta en
    `without_cost`, para que la pantalla avise de que ese día es parcialmente una estimación.
    """
    out: dict[tuple[str, date], dict] = defaultdict(lambda: {"runs": 0, "tokens": 0, "cost": 0.0, "without_cost": 0})
    for run in runs:
        workspace_id = _metadata(run).get("workspace_id")
        start = getattr(run, "start_time", None)
        if not workspace_id or start is None:
            continue
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        prompt = int(getattr(run, "prompt_tokens", 0) or 0)
        completion = int(getattr(run, "completion_tokens", 0) or 0)
        tokens = int(getattr(run, "total_tokens", 0) or 0) or prompt + completion
        cost = getattr(run, "total_cost", None)
        bucket = out[(str(workspace_id), start.astimezone(BOGOTA).date())]
        bucket["runs"] += 1
        bucket["tokens"] += tokens
        if cost is None:
            bucket["without_cost"] += 1
            bucket["cost"] += ai_cost_usd(prompt, completion)
        else:
            bucket["cost"] += float(cost)
    return dict(out)


def aggregate_by_run(runs: Iterable[Any]) -> dict[str, dict]:
    """Suma las llamadas al modelo por ejecución del agente (`agent_run_id` en los metadatos).

    Una ejecución puede llamar al modelo varias veces (una por herramienta): se suman. Las llamadas anteriores a que el
    agente mandara `agent_run_id` no traen ese dato y se saltan (siguen contando en el total del negocio y del día).
    """
    out: dict[str, dict] = defaultdict(lambda: {"runs": 0, "tokens": 0, "cost": 0.0, "without_cost": 0})
    for run in runs:
        run_id = _metadata(run).get("agent_run_id")
        if not run_id:
            continue
        prompt = int(getattr(run, "prompt_tokens", 0) or 0)
        completion = int(getattr(run, "completion_tokens", 0) or 0)
        cost = getattr(run, "total_cost", None)
        bucket = out[str(run_id)]
        bucket["runs"] += 1
        bucket["tokens"] += int(getattr(run, "total_tokens", 0) or 0) or prompt + completion
        if cost is None:
            bucket["without_cost"] += 1
            bucket["cost"] += ai_cost_usd(prompt, completion)
        else:
            bucket["cost"] += float(cost)
    return dict(out)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def day_window(day_from: date, day_to: date) -> tuple[datetime, datetime]:
    """Desde el inicio de `day_from` hasta el final de `day_to`, en hora de Bogotá."""
    start = datetime.combine(day_from, datetime.min.time(), tzinfo=BOGOTA)
    end = datetime.combine(day_to + timedelta(days=1), datetime.min.time(), tzinfo=BOGOTA)
    return start, end


def _fetch(day_from: date, day_to: date, client: Optional[Any] = None) -> list[Any]:
    """Bloqueante: las llamadas al modelo de ese rango. Se ejecuta en un hilo."""
    if client is None:
        if not is_configured():
            raise LangSmithError("LangSmith no está configurado (falta LANGSMITH_API_KEY).")
        from langsmith import Client
        client = Client(api_key=api_key())
    start, end = day_window(day_from, day_to)
    runs = []
    for run in client.list_runs(
        project_name=project_name(), is_root=True, start_time=start.astimezone(timezone.utc),
        filter=f'and(has(tags, "{TAG}"), lt(start_time, "{_iso(end)}"))', select=SELECT,
    ):
        runs.append(run)
        if len(runs) >= MAX_RUNS:
            log.warning("[langsmith] tope de %d llamadas alcanzado; el resto se sincroniza en la próxima pasada", MAX_RUNS)
            break
    return runs


async def fetch_all(day_from: date, day_to: date, client: Optional[Any] = None) -> tuple[dict[tuple[str, date], dict], dict[str, dict]]:
    """Una sola lectura de LangSmith: el costo por (negocio, día) y el costo por ejecución del agente."""
    try:
        runs = await asyncio.to_thread(_fetch, day_from, day_to, client)
    except LangSmithError:
        raise
    except Exception as exc:
        raise LangSmithError(f"{type(exc).__name__}: {exc}") from exc
    return aggregate(runs), aggregate_by_run(runs)


async def fetch_costs(day_from: date, day_to: date, client: Optional[Any] = None) -> dict[tuple[str, date], dict]:
    """Costo por (negocio, día) entre dos fechas. Lanza `LangSmithError` si no se pudo leer."""
    return (await fetch_all(day_from, day_to, client))[0]


async def ping(client: Optional[Any] = None) -> dict:
    """Prueba de conexión barata: pide una sola llamada reciente. Devuelve {ok, detail}."""
    if client is None and not is_configured():
        return {"ok": False, "detail": "Falta LANGSMITH_API_KEY."}

    def _ping() -> str:
        c = client
        if c is None:
            from langsmith import Client
            c = Client(api_key=api_key())
        next(iter(c.list_runs(project_name=project_name(), is_root=True, limit=1, select=["id"])), None)
        return f"Conectado al proyecto «{project_name()}»."

    try:
        return {"ok": True, "detail": await asyncio.to_thread(_ping)}
    except Exception as exc:
        return {"ok": False, "detail": f"{type(exc).__name__}: {str(exc)[:200]}"}
