"""Costo por barbería: lectura de LangSmith (cliente falso), agregación por día, sincronización y costo por cita."""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from fake_session import FakeSession
from integrations import langsmith_costs as ls
from services import billing_costs as bc

pytestmark = pytest.mark.asyncio

BOGOTA_NOON = datetime(2026, 11, 20, 17, tzinfo=timezone.utc)  # 12:00 en Bogotá


def run(ws="w1", start=BOGOTA_NOON, cost=0.01, prompt=1000, completion=100, total=None, meta=None):
    return SimpleNamespace(
        metadata=meta if meta is not None else {"workspace_id": ws}, start_time=start, total_cost=cost,
        prompt_tokens=prompt, completion_tokens=completion, total_tokens=total if total is not None else prompt + completion)


class FakeClient:
    """Se comporta como `langsmith.Client.list_runs`: registra con qué se le pidió."""

    def __init__(self, runs=(), error=None):
        self.runs, self.error, self.calls = list(runs), error, []

    def list_runs(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return iter(self.runs)


# ── Agregación ───────────────────────────────────────────────────────────────

def test_suma_las_llamadas_por_negocio_y_dia():
    out = ls.aggregate([run("w1", cost=0.01), run("w1", cost=0.02), run("w2", cost=0.5)])
    assert out[("w1", date(2026, 11, 20))] == {"runs": 2, "tokens": 2200, "cost": pytest.approx(0.03), "without_cost": 0}
    assert out[("w2", date(2026, 11, 20))]["runs"] == 1


def test_el_dia_se_corta_en_hora_de_bogota_no_en_utc():
    """11:30 p. m. en Bogotá (04:30 UTC del día siguiente) cuenta para el día de Bogotá."""
    late = datetime(2026, 11, 21, 4, 30, tzinfo=timezone.utc)
    early = datetime(2026, 11, 20, 5, 30, tzinfo=timezone.utc)  # 12:30 a. m. del 20 en Bogotá
    out = ls.aggregate([run(start=late), run(start=early)])
    assert set(out) == {("w1", date(2026, 11, 20))}


def test_una_hora_sin_zona_se_toma_como_utc():
    assert ("w1", date(2026, 11, 20)) in ls.aggregate([run(start=datetime(2026, 11, 20, 17))])


def test_ignora_llamadas_sin_negocio_o_sin_fecha():
    out = ls.aggregate([run(meta={}), run(meta={"workspace_id": None}), run(start=None), run("w1")])
    assert list(out) == [("w1", date(2026, 11, 20))] and out[("w1", date(2026, 11, 20))]["runs"] == 1


def test_sin_costo_de_langsmith_se_estima_por_tokens_y_se_avisa():
    out = ls.aggregate([run(cost=None, prompt=1_000_000, completion=0), run(cost=0.25)])
    day = out[("w1", date(2026, 11, 20))]
    assert day["without_cost"] == 1 and day["runs"] == 2
    assert day["cost"] == pytest.approx(1.0 + 0.25)  # 1 millón de tokens de entrada = US$1 en la estimación


def test_total_de_tokens_si_langsmith_no_lo_trae_se_suma():
    day = ls.aggregate([run(prompt=300, completion=50, total=0)])[("w1", date(2026, 11, 20))]
    assert day["tokens"] == 350


def test_lee_los_metadatos_de_extra_si_no_hay_propiedad_metadata():
    r = SimpleNamespace(extra={"metadata": {"workspace_id": "w9"}}, start_time=BOGOTA_NOON, total_cost=0.1,
                        prompt_tokens=1, completion_tokens=1, total_tokens=2)
    assert ("w9", date(2026, 11, 20)) in ls.aggregate([r])


# ── Cliente ──────────────────────────────────────────────────────────────────

async def test_le_pide_a_langsmith_solo_las_llamadas_del_agente_en_el_rango():
    client = FakeClient([run()])
    out = await ls.fetch_costs(date(2026, 11, 19), date(2026, 11, 20), client)
    (call,) = client.calls
    assert call["is_root"] is True and 'has(tags, "citas")' in call["filter"]
    assert call["start_time"] == datetime(2026, 11, 19, 5, tzinfo=timezone.utc)  # medianoche de Bogotá en UTC
    assert "2026-11-21T05:00:00Z" in call["filter"]  # hasta el final del 20 en Bogotá
    assert "total_cost" in call["select"] and "extra" in call["select"]
    assert out[("w1", date(2026, 11, 20))]["runs"] == 1


async def test_un_error_del_cliente_se_convierte_en_langsmith_error():
    with pytest.raises(ls.LangSmithError, match="ConnectionError"):
        await ls.fetch_costs(date(2026, 11, 20), date(2026, 11, 20), FakeClient(error=ConnectionError("sin red")))


async def test_sin_clave_no_se_intenta(monkeypatch):
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    assert ls.is_configured() is False
    with pytest.raises(ls.LangSmithError, match="LANGSMITH_API_KEY"):
        await ls.fetch_costs(date(2026, 11, 20), date(2026, 11, 20))
    assert (await ls.ping())["ok"] is False


async def test_el_ping_reporta_ok_o_el_error():
    ok = await ls.ping(FakeClient([run()]))
    assert ok["ok"] is True
    bad = await ls.ping(FakeClient(error=PermissionError("403 Forbidden")))
    assert bad["ok"] is False and "403" in bad["detail"]


def test_la_clave_y_el_proyecto_salen_del_entorno(monkeypatch):
    monkeypatch.setenv("LANGCHAIN_API_KEY", "k")
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.setenv("LANGCHAIN_PROJECT", "zumit")
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
    assert ls.is_configured() and ls.project_name() == "zumit"
    monkeypatch.setenv("LANGSMITH_PROJECT", "otro")
    assert ls.project_name() == "otro"


# ── Sincronización ───────────────────────────────────────────────────────────

class DB(FakeSession):
    def __init__(self, workspaces=("w1", "w2")):
        self.workspaces, self.log, self.rolled_back, self.commits = list(workspaces), [], 0, 0

    def written(self, needle):
        return [p for q, p in self.log if needle in q]

    async def rollback(self):
        self.rolled_back += 1

    async def commit(self):
        self.commits += 1

    def handle(self, q, p):
        self.log.append((q, p))
        if "SELECT id FROM workspaces" in q: return [{"id": w} for w in self.workspaces]
        return []


TODAY = date(2026, 11, 20)


async def test_guarda_el_costo_por_negocio_y_dia_y_registra_la_sincronizacion():
    db = DB()
    res = await bc.sync(db, days=2, client=FakeClient([run("w1", cost=0.02), run("w2", cost=0.5)]), today=TODAY)
    assert res["ok"] and res["runs"] == 2 and res["workspaces"] == 2 and res["cost_usd"] == pytest.approx(0.52)
    rows = {p["w"]: p for p in db.written("INSERT INTO agent_usage")}
    assert rows["w1"]["c"] == 0.02 and rows["w1"]["r"] == 1 and rows["w1"]["d"] == date(2026, 11, 20)
    (logged,) = db.written("INSERT INTO langsmith_sync_log")
    assert logged["e"] is None and logged["f"] == date(2026, 11, 19) and logged["t"] == TODAY
    assert db.commits == 1


async def test_la_sincronizacion_es_idempotente_sobrescribe_no_suma():
    """El upsert reemplaza los valores de LangSmith del día; volver a correrla no duplica el costo."""
    db = DB()
    await bc.sync(db, client=FakeClient([run("w1", cost=0.02)]), today=TODAY)
    sql = next(q for q, _ in db.log if "INSERT INTO agent_usage" in q)
    assert "ls_cost_usd = :c" in sql and "ls_cost_usd + " not in sql and "ls_runs + " not in sql


async def test_un_negocio_borrado_o_de_pruebas_se_omite_sin_romper_nada():
    db = DB(workspaces=("w1",))
    res = await bc.sync(db, client=FakeClient([run("w1"), run("fantasma")]), today=TODAY)
    assert res["ok"] and res["workspaces"] == 1 and len(db.written("INSERT INTO agent_usage")) == 1


async def test_si_langsmith_falla_no_lanza_y_deja_el_error_registrado():
    db = DB()
    res = await bc.sync(db, client=FakeClient(error=TimeoutError("lento")), today=TODAY)
    assert res["ok"] is False and "TimeoutError" in res["error"]
    (logged,) = db.written("INSERT INTO langsmith_sync_log")
    assert "TimeoutError" in logged["e"]
    assert db.rolled_back >= 1 and not db.written("INSERT INTO agent_usage")


async def test_los_dias_se_acotan_entre_1_y_30():
    db = DB()
    res = await bc.sync(db, days=999, client=FakeClient([]), today=TODAY)
    assert res["day_from"] == TODAY - timedelta(days=29)
    res = await bc.sync(db, days=0, client=FakeClient([]), today=TODAY)
    assert res["day_from"] == TODAY


# ── Costo por cita ───────────────────────────────────────────────────────────

def test_de_donde_sale_el_costo():
    assert bc.source_of(30, 30) == "langsmith"
    assert bc.source_of(30, 0) == "estimate" and bc.source_of(0, 0) == "estimate"
    assert bc.source_of(30, 12) == "mixed"


def test_costo_por_cita():
    assert bc.per_booking(2.0, 100, 4000) == {"usd": 0.02, "cop": 80}
    assert bc.per_booking(2.0, 100, None) == {"usd": 0.02, "cop": None}  # sin tasa del dólar no inventa pesos


def test_sin_citas_no_se_divide_por_cero():
    assert bc.per_booking(5.0, 0, 4000) == {"usd": None, "cop": None}


# ── Costo por ejecución del agente (cada cita) ───────────────────────────────

def test_suma_las_llamadas_de_una_misma_ejecucion_del_agente():
    out = ls.aggregate_by_run([run(meta={"workspace_id": "w1", "agent_run_id": "r1"}, cost=0.01),
                               run(meta={"workspace_id": "w1", "agent_run_id": "r1"}, cost=0.02),
                               run(meta={"workspace_id": "w1", "agent_run_id": "r2"}, cost=0.5)])
    assert out["r1"] == {"runs": 2, "tokens": 2200, "cost": pytest.approx(0.03), "without_cost": 0}
    assert out["r2"]["cost"] == 0.5


def test_las_llamadas_sin_id_de_ejecucion_se_saltan_pero_siguen_en_el_total_del_dia():
    runs = [run(), run(meta={"workspace_id": "w1", "agent_run_id": "r1"})]
    assert list(ls.aggregate_by_run(runs)) == ["r1"]
    assert ls.aggregate(runs)[("w1", date(2026, 11, 20))]["runs"] == 2


def test_sin_costo_de_langsmith_la_ejecucion_se_estima_por_tokens():
    out = ls.aggregate_by_run([run(meta={"agent_run_id": "r1"}, cost=None, prompt=1000, completion=100)])
    assert out["r1"]["without_cost"] == 1 and out["r1"]["cost"] > 0


async def test_la_sincronizacion_guarda_el_costo_de_cada_ejecucion_con_el_cast_de_uuid():
    db = DB()
    res = await bc.sync(db, client=FakeClient([run("w1", cost=0.02, meta={"workspace_id": "w1", "agent_run_id": "r1"})]), today=TODAY)
    assert res["ok"] and res["agent_runs"] == 1
    sql = next(q for q, _ in db.log if "UPDATE agent_runs" in q)
    assert "CAST(:i AS UUID)" in sql
    (p,) = db.written("UPDATE agent_runs")
    assert p == {"i": "r1", "c": 0.02, "t": 1100}


async def test_si_falla_el_costo_por_ejecucion_se_conserva_el_costo_por_negocio():
    """Sin la migración 024 el UPDATE falla: va en SAVEPOINT, así lo demás de la sincronización se guarda igual."""
    class Old(DB):
        def handle(self, q, p):
            if "UPDATE agent_runs" in q:
                raise RuntimeError('column "ls_cost_usd" of relation "agent_runs" does not exist')
            return super().handle(q, p)
    db = Old()
    res = await bc.sync(db, client=FakeClient([run("w1", cost=0.02, meta={"workspace_id": "w1", "agent_run_id": "r1"})]), today=TODAY)
    assert res["ok"] and res["agent_runs"] == 0 and db.rolled_back == 0
    assert len(db.written("INSERT INTO agent_usage")) == 1 and db.commits == 1


# ── El agente guarda lo que gastó cada ejecución ─────────────────────────────

async def test_el_agente_guarda_tokens_y_costo_de_la_ejecucion(monkeypatch):
    from services import agent_service as agent_mod
    db = DB()
    monkeypatch.setattr(agent_mod, "AsyncSessionLocal", lambda: db)
    await agent_mod.AgentService._save_run_usage("run-1", {"calls": 3, "input": 4000, "output": 300})
    (p,) = db.written("UPDATE agent_runs")
    assert p["id"] == "run-1" and (p["i"], p["o"], p["n"]) == (4000, 300, 3) and p["c"] > 0
    assert db.commits == 1


async def test_si_no_se_puede_guardar_el_costo_de_la_ejecucion_no_lanza(monkeypatch):
    from services import agent_service as agent_mod

    class Boom(DB):
        def handle(self, q, p):
            raise RuntimeError('column "input_tokens" of relation "agent_runs" does not exist')
    monkeypatch.setattr(agent_mod, "AsyncSessionLocal", lambda: Boom())
    await agent_mod.AgentService._save_run_usage("run-1", {"calls": 1, "input": 10, "output": 1})   # no debe lanzar
    await agent_mod.AgentService._save_run_usage(None, {"calls": 1})                                  # sin ejecución, no hace nada
