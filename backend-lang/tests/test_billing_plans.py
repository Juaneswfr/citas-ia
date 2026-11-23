"""Planes: tablero por plan, vista previa del impacto y edición. BD falsa; los cupos se simulan."""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from fake_session import FakeSession
from services import billing_plans as bp
from services.subscription_service import BillingNotFound
from test_billing_metrics import _client

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 11, 20, 15, tzinfo=timezone.utc)
PA, PE, PO = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222", "33333333-3333-3333-3333-333333333333"


def plan(pid, code, name, price, launch, apps, pros, active=True, extra=40_000):
    return {"id": pid, "code": code, "name": name, "description": None, "price_cop": price, "launch_price_cop": launch,
            "max_appointments": apps, "max_professionals": pros, "extra_professional_price_cop": extra, "is_active": active}


ARRANQUE = plan(PA, "emprendedor", "Emprendedor", 120_000, 50_000, 250, 3)
EQUIPO = plan(PE, "equipo", "Equipo", 285_000, 120_000, 550, 6)
OTRO = plan(PO, "otro", "Otro", 99_000, None, 100, 2)


def sub(ws, plan_id, status, *, discount=0, frozen=None, founder=False, trial_days_ago=None, activated=True,
        cancelling=False, updated_days_ago=0, sid=None):
    return {"id": sid or f"sub-{ws}", "workspace_id": ws, "billing_plan_id": plan_id, "status": status,
            "activated_at": NOW - timedelta(days=60) if activated else None,
            "trial_started_at": NOW - timedelta(days=trial_days_ago) if trial_days_ago is not None else None,
            "cancel_at_period_end": cancelling, "discount_cycles_remaining": discount, "frozen_price_cop": frozen,
            "is_founder": founder, "updated_at": NOW - timedelta(days=updated_days_ago), "workspace": f"Negocio {ws}"}


class DB(FakeSession):
    def __init__(self, plans=(ARRANQUE, EQUIPO), subs=(), addons=(), events=(), plan_row=None, name_taken=False):
        self.plans, self.subs, self.addons, self.events, self.plan_row = list(plans), list(subs), list(addons), list(events), plan_row
        self.name_taken = name_taken
        self.public_rows = [{k: v for k, v in p.items() if k not in ('id', 'is_active')} for p in self.plans if p['is_active'] and p['code']]
        self.log = []

    def written(self, needle):
        return [p for q, p in self.log if needle in q]

    def handle(self, q, p):
        self.log.append((q, p))
        if "lower(name) = lower(:n)" in q: return 1 if self.name_taken else None
        if "FROM billing_plans WHERE id" in q: return self.plan_row if self.plan_row is not None else {}
        if "is_active = TRUE AND code IS NOT NULL" in q: return self.public_rows
        if "FROM billing_plans" in q and "code IS NOT NULL" in q: return self.plans
        if "SELECT DISTINCT ON (s.workspace_id)" in q: return self.subs
        if "FROM subscription_addons" in q: return self.addons
        if "FROM billing_events e" in q: return self.events
        if "UPDATE billing_plans" in q: return {**self.plan_row, **{k: v for k, v in p.items() if k != "_id"}}
        return []


def usage(**by_ws):
    """{ws: (usadas, total, nivel, barberos, extra)} -> sustituto de get_entitlements."""
    async def fake(db, workspace_id, now=None):
        used, total, level, pros, extra = by_ws.get(workspace_id, (0, 250, "ok", 1, 0))
        return SimpleNamespace(used_appointments=used, total_appointments=total, quota_level=level,
                               professionals_active=pros, extra_professionals=extra)
    return fake


def costs(items=(), fx=4000):
    async def fake(db, days, today=None):
        return {"since": date(2026, 10, 22), "until": date(2026, 11, 20), "usd_cop": fx, "items": list(items),
                "totals": {"margin_cop": 1, "margin_pct": 2.5, "revenue_cop": 3}}
    return fake


@pytest.fixture
def patched(monkeypatch):
    def apply(ent=None, cost=None):
        monkeypatch.setattr(bp.bs, "get_entitlements", ent or usage())
        monkeypatch.setattr(bp.billing_costs, "costs", cost or costs())
    return apply


# ── Cuentas puras ────────────────────────────────────────────────────────────

def test_las_semanas_empiezan_el_lunes():
    assert bp.week_start(date(2026, 11, 20)) == date(2026, 11, 16)   # viernes -> lunes
    assert bp.week_start(date(2026, 11, 16)) == date(2026, 11, 16)
    assert bp.week_start(date(2026, 11, 22)) == date(2026, 11, 16)   # domingo


def test_rango_de_semanas_de_la_mas_antigua_a_la_actual():
    weeks = bp.week_range(date(2026, 11, 20), 4)
    assert weeks == [date(2026, 10, 26), date(2026, 11, 2), date(2026, 11, 9), date(2026, 11, 16)]


def test_las_semanas_sin_activaciones_salen_en_cero():
    mondays = bp.week_range(date(2026, 11, 20), 3)
    rows = [{"week": date(2026, 11, 9), "plan": "emprendedor", "n": 2}, {"week": date(2026, 11, 9), "plan": "equipo", "n": 1},
            {"week": date(2026, 11, 16), "plan": None, "n": 1}, {"week": date(2020, 1, 6), "plan": "emprendedor", "n": 9}]
    out = bp.fill_weeks(rows, mondays)
    assert [w["total"] for w in out] == [0, 3, 1]
    assert out[1]["by_plan"] == {"emprendedor": 2, "equipo": 1}
    assert out[2]["by_plan"] == {"otro": 1}          # una activación sin plan registrado no se pierde
    assert all(w["week"] in mondays for w in out)    # lo que cae fuera del rango se ignora


def test_precio_efectivo_con_descuento_sin_el_y_fundador():
    assert bp.effective_price(ARRANQUE, 2, None) == 50_000
    assert bp.effective_price(ARRANQUE, 0, None) == 120_000
    assert bp.effective_price(ARRANQUE, 0, 100_000) == 100_000      # valor congelado
    assert bp.effective_price(ARRANQUE, 1, 100_000) == 50_000       # mientras tenga ciclos con descuento, el de lanzamiento


# ── Validación de los cambios ────────────────────────────────────────────────

def test_solo_cuenta_lo_que_de_verdad_cambia():
    assert bp.validate_changes(ARRANQUE, {"price_cop": 120_000, "name": "Emprendedor"}) == {}
    assert bp.validate_changes(ARRANQUE, {"price_cop": 130_000, "name": "Emprendedor"}) == {"price_cop": 130_000}


def test_el_nombre_se_limpia_y_la_descripcion_vacia_queda_nula():
    out = bp.validate_changes({**ARRANQUE, "description": "x"}, {"name": "  Inicio  ", "description": "   "})
    assert out == {"name": "Inicio", "description": None}


@pytest.mark.parametrize("changes,match", [
    ({"code": "otro"}, "No se puede editar"),                     # el código no se edita
    ({"id": "x", "price_cop": 1}, "No se puede editar"),
    ({"name": " a "}, "al menos 2 letras"),
    ({"launch_price_cop": 130_000}, "lanzamiento no puede ser mayor"),
    ({"price_cop": 40_000}, "lanzamiento no puede ser mayor"),    # bajar el precio por debajo del de lanzamiento
])
def test_cambios_no_validos(changes, match):
    with pytest.raises(bp.PlanError, match=match):
        bp.validate_changes(ARRANQUE, changes)


def test_se_puede_quitar_el_precio_de_lanzamiento():
    assert bp.validate_changes(ARRANQUE, {"launch_price_cop": None}) == {"launch_price_cop": None}


def test_el_plan_donde_empieza_la_prueba_no_se_puede_desactivar():
    with pytest.raises(bp.PlanError, match="empieza la prueba"):
        bp.validate_changes(ARRANQUE, {"is_active": False})
    assert bp.validate_changes(EQUIPO, {"is_active": False}) == {"is_active": False}


def test_un_plan_con_id_que_no_es_uuid_no_existe():
    with pytest.raises(BillingNotFound):
        bp._uuid("no-es-un-uuid")
    assert bp._uuid(PA) == PA


# ── Tablero ──────────────────────────────────────────────────────────────────

def world():
    return [
        sub("w1", PA, "active", discount=2, trial_days_ago=40),                  # paga lanzamiento 50.000
        sub("w2", PA, "active", sid="s2"),                                       # paga 120.000 (+ un bloque de 50.000)
        sub("w3", PE, "active", frozen=285_000, founder=True),                   # fundador: 285.000
        sub("w4", PA, "trial", activated=False, trial_days_ago=3),
        sub("w5", PE, "cancelled", updated_days_ago=5),
        sub("w6", PA, "active", cancelling=True),
        sub("w7", PA, "paused"),
        sub("w8", PE, "cancelled", updated_days_ago=60),                         # fuera de los 30 días
    ]


async def test_estadisticas_de_cada_plan(patched):
    patched(ent=usage(w1=(200, 250, "warn", 3, 0), w2=(260, 250, "over", 5, 2), w4=(10, 250, "ok", 1, 0), w6=(100, 250, "ok", 2, 0)))
    out = await bp.dashboard(DB(subs=world(), addons=[{"subscription_id": "s2", "total": 50_000}]), 30, NOW)
    a = next(p for p in out["plans"] if p["code"] == "emprendedor")["stats"]
    assert a["subscribers"] == {"trial": 1, "active": 3, "past_due": 0, "paused": 1, "cancelled": 0, "expired": 0}
    assert a["paying"] == 3
    assert a["mrr_plan_cop"] == 50_000 + 120_000 + 120_000
    assert a["mrr_list_cop"] == 3 * 120_000 and a["discount_cop"] == 70_000
    assert a["addons_cop"] == 50_000 and a["arpa_cop"] == round((290_000 + 50_000) / 3)
    assert a["trials"] == 1 and a["cancelling"] == 1
    assert a["usage"]["near"] == 2 and a["usage"]["avg_pct"] == pytest.approx((80 + 104 + 4 + 40) / 4)
    assert a["usage"]["distribution"] == {"0_25": 1, "25_50": 1, "50_80": 0, "80_100": 1, "mas_100": 1}
    assert a["professionals"] == {"avg": 2.8, "extra": 2}
    assert a["conversion"] == {"trials": 2, "converted": 1, "pct": 50.0}


async def test_el_fundador_paga_su_valor_congelado_y_los_cancelados_se_cuentan_a_30_dias(patched):
    patched()
    out = await bp.dashboard(DB(subs=world()), 30, NOW)
    e = next(p for p in out["plans"] if p["code"] == "equipo")["stats"]
    assert e["mrr_plan_cop"] == 285_000 and e["discount_cop"] == 0       # congelado: no hay descuento que regalar
    assert e["cancelled_30d"] == 1 and e["subscribers"]["cancelled"] == 2


async def test_margen_por_plan_agrupa_lo_de_costos(patched):
    items = [{"plan": "Emprendedor", "plan_id": PA, "revenue_cop": 100_000, "cost_cop": 30_000},
             {"plan": "Emprendedor", "plan_id": PA, "revenue_cop": 50_000, "cost_cop": 10_000},
             {"plan": "Equipo", "plan_id": PE, "revenue_cop": 285_000, "cost_cop": None}]       # sin tasa del dólar: no se inventa
    patched(cost=costs(items))
    out = await bp.dashboard(DB(subs=world()), 30, NOW)
    by = {p["code"]: p["stats"]["margin"] for p in out["plans"]}
    assert by["emprendedor"] == {"revenue_cop": 150_000, "cost_cop": 40_000, "margin_cop": 110_000, "margin_pct": 73.3}
    assert by["equipo"]["margin_cop"] is None and by["equipo"]["cost_cop"] is None and by["equipo"]["margin_pct"] is None
    assert by["equipo"]["revenue_cop"] == 285_000


async def test_totales_y_serie_de_activaciones(patched):
    patched(ent=usage(w1=(10, 250, "ok", 1, 0)))
    events = [{"week": date(2026, 11, 9), "plan": "emprendedor", "n": 2}, {"week": date(2026, 11, 16), "plan": "equipo", "n": 1}]
    out = await bp.dashboard(DB(subs=world(), events=events), 30, NOW)
    t = out["totals"]
    assert t["paying"] == 4 and t["trials"] == 1 and t["plans_active"] == 2
    assert t["mrr_cop"] == 50_000 + 120_000 + 120_000 + 285_000
    assert t["discount_cop"] == 70_000 and t["arpa_cop"] == round(t["mrr_cop"] / 4)
    weeks = out["series"]["activations_by_week"]
    assert len(weeks) == 4 and weeks[-1]["week"] == date(2026, 11, 16) and weeks[-1]["by_plan"] == {"equipo": 1}
    assert out["days"] == 30 and out["usd_cop"] == 4000


async def test_los_dias_se_acotan_y_las_semanas_los_siguen(patched):
    patched()
    assert (await bp.dashboard(DB(), 1, NOW))["days"] == 7
    big = await bp.dashboard(DB(), 999, NOW)
    assert big["days"] == 90 and len(big["series"]["activations_by_week"]) == 12


async def test_un_negocio_con_un_plan_que_ya_no_se_lista_se_ignora(patched):
    patched()
    out = await bp.dashboard(DB(subs=[sub("wx", "99999999-9999-9999-9999-999999999999", "active")]), 30, NOW)
    assert sum(p["stats"]["paying"] for p in out["plans"]) == 0


async def test_sin_negocios_el_tablero_no_se_rompe(patched):
    patched()
    out = await bp.dashboard(DB(), 30, NOW)
    assert out["totals"]["paying"] == 0 and out["totals"]["arpa_cop"] == 0
    s = out["plans"][0]["stats"]
    assert s["usage"]["avg_pct"] is None and s["conversion"]["pct"] is None and s["arpa_cop"] == 0


# ── Vista previa ─────────────────────────────────────────────────────────────

async def prev(changes, subs, ent=None, plan_row=ARRANQUE, monkeypatch=None):
    return await bp.preview(DB(subs=subs, plan_row=plan_row), plan_row["id"], changes, NOW)


async def test_subir_el_precio_afecta_a_quien_paga_el_valor_real_no_al_de_lanzamiento_ni_al_fundador(monkeypatch):
    monkeypatch.setattr(bp.bs, "get_entitlements", usage())
    subs = [sub("w1", PA, "active", discount=2),                                   # lanzamiento: no cambia
            sub("w2", PA, "active"),                                               # valor real: +30.000
            sub("w3", PA, "past_due"),                                             # en mora también paga: +30.000
            sub("w4", PA, "active", frozen=120_000, founder=True),                 # fundador: protegido
            sub("w5", PA, "trial", activated=False)]                               # prueba: aún no paga
    out = await prev({"price_cop": 150_000}, subs)
    assert out["subscribers"] == 5 and out["paying"] == 4
    assert out["price"] == {"affected": 2, "protected_founders": 1, "mrr_delta_cop": 60_000}
    assert any("30 días" in w for w in out["warnings"])
    assert out["changes"] == {"price_cop": {"from": 120_000, "to": 150_000}}


async def test_bajar_el_precio_no_pide_aviso_de_30_dias(monkeypatch):
    monkeypatch.setattr(bp.bs, "get_entitlements", usage())
    out = await prev({"price_cop": 100_000}, [sub("w2", PA, "active")])
    assert out["price"]["mrr_delta_cop"] == -20_000
    assert not any("30 días" in w for w in out["warnings"]) and out["warnings"]


async def test_el_precio_de_lanzamiento_afecta_a_quien_aun_tiene_ciclos_con_descuento_incluso_al_fundador(monkeypatch):
    monkeypatch.setattr(bp.bs, "get_entitlements", usage())
    subs = [sub("w1", PA, "active", discount=2), sub("w2", PA, "active", discount=1, frozen=120_000, founder=True),
            sub("w3", PA, "active")]
    out = await prev({"launch_price_cop": 40_000}, subs)
    assert out["price"] == {"affected": 2, "protected_founders": 0, "mrr_delta_cop": -20_000}


async def test_bajar_el_limite_lista_a_los_negocios_que_ya_lo_pasaron(monkeypatch):
    monkeypatch.setattr(bp.bs, "get_entitlements", usage(w1=(180, 250, "ok", 2, 0), w2=(40, 250, "ok", 5, 2), w3=(90, 250, "ok", 1, 0)))
    subs = [sub("w1", PA, "active"), sub("w2", PA, "active"), sub("w3", PA, "active"), sub("w4", PA, "paused")]
    out = await prev({"max_appointments": 100, "max_professionals": 2}, subs)
    assert out["limits"]["over_appointments"] == [{"workspace_id": "w1", "workspace": "Negocio w1", "used": 180, "limit": 100}]
    assert out["limits"]["over_professionals"] == [{"workspace_id": "w2", "workspace": "Negocio w2", "active": 5, "limit": 2}]
    assert any("ya" in w for w in out["warnings"])


async def test_cambiar_solo_el_nombre_no_calcula_cupos_ni_precios(monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("no debería consultar el cupo")
    monkeypatch.setattr(bp.bs, "get_entitlements", boom)
    out = await prev({"name": "Inicio"}, [sub("w1", PA, "active")])
    assert out["has_changes"] and out["price"] == {"affected": 0, "protected_founders": 0, "mrr_delta_cop": 0}


async def test_sin_cambios_reales_la_vista_previa_lo_dice():
    out = await prev({"price_cop": 120_000}, [])
    assert out["has_changes"] is False and out["changes"] == {}


async def test_la_vista_previa_solo_cuenta_negocios_vivos_de_ese_plan(monkeypatch):
    monkeypatch.setattr(bp.bs, "get_entitlements", usage())
    subs = [sub("w1", PA, "active"), sub("w2", PE, "active"), sub("w3", PA, "cancelled")]
    assert (await prev({"price_cop": 150_000}, subs))["subscribers"] == 1


async def test_vista_previa_de_un_plan_que_no_existe():
    with pytest.raises(BillingNotFound):
        await bp.preview(DB(plan_row={}), PA, {"price_cop": 1}, NOW)


# ── Edición ──────────────────────────────────────────────────────────────────

async def test_editar_aplica_solo_lo_que_cambia_y_devuelve_el_impacto(monkeypatch):
    monkeypatch.setattr(bp.bs, "get_entitlements", usage())
    db = DB(subs=[sub("w2", PA, "active")], plan_row=ARRANQUE)
    res = await bp.update_plan(db, PA, {"price_cop": 130_000, "name": "Emprendedor"}, NOW)
    sql, params = next((q, p) for q, p in db.log if "UPDATE billing_plans" in q)
    assert "price_cop = :price_cop" in sql and "name" not in sql.split("WHERE")[0].replace("price_cop", "")
    assert params == {"price_cop": 130_000, "_id": PA}
    assert res["before"] == {"price_cop": 120_000} and res["impact"]["price"]["mrr_delta_cop"] == 10_000
    assert res["plan"]["price_cop"] == 130_000 and res["plan"]["id"] == PA


async def test_al_cambiar_los_barberos_se_mantiene_la_columna_heredada_igual(monkeypatch):
    monkeypatch.setattr(bp.bs, "get_entitlements", usage())
    db = DB(plan_row=ARRANQUE)
    await bp.update_plan(db, PA, {"max_professionals": 4}, NOW)
    params = next(p for q, p in db.log if "UPDATE billing_plans" in q)
    assert params["max_professionals"] == 4 and params["max_calendars"] == 4


async def test_editar_sin_cambios_reales_se_rechaza():
    with pytest.raises(bp.PlanError, match="nada que cambiar"):
        await bp.update_plan(DB(plan_row=ARRANQUE), PA, {"price_cop": 120_000}, NOW)


async def test_no_se_desactiva_un_plan_con_negocios(monkeypatch):
    monkeypatch.setattr(bp.bs, "get_entitlements", usage())
    db = DB(subs=[sub("w5", PE, "active"), sub("w6", PE, "trial", activated=False)], plan_row=EQUIPO)
    with pytest.raises(bp.PlanError, match="2 negocio"):
        await bp.update_plan(db, PE, {"is_active": False}, NOW)
    assert not db.written("UPDATE billing_plans")


async def test_un_plan_sin_negocios_si_se_desactiva(monkeypatch):
    monkeypatch.setattr(bp.bs, "get_entitlements", usage())
    db = DB(plan_row=OTRO)
    res = await bp.update_plan(db, PO, {"is_active": False}, NOW)
    assert db.written("UPDATE billing_plans") and res["plan"]["is_active"] is False


async def test_el_sql_solo_asigna_columnas_conocidas(monkeypatch):
    """Nunca un nombre de columna que venga del cliente: el SET sale de una lista fija."""
    monkeypatch.setattr(bp.bs, "get_entitlements", usage())
    db = DB(plan_row=ARRANQUE)
    with pytest.raises(bp.PlanError):
        await bp.update_plan(db, PA, {"price_cop = 0, code": "x"}, NOW)
    assert not db.written("UPDATE billing_plans")


# ── Rutas ────────────────────────────────────────────────────────────────────

def _audit(monkeypatch):
    calls = []

    async def log(**kw):
        calls.append(kw)
    monkeypatch.setattr("services.audit_service.AuditService.log", staticmethod(log))
    return calls


async def test_el_tablero_responde_y_acota_los_dias(monkeypatch):
    async def fake(db, days, now=None):
        return {"days": days, "plans": [], "series": {"activations_by_week": []}, "totals": {}}
    monkeypatch.setattr(bp, "dashboard", fake)
    async with _client("super_admin") as c:
        assert (await c.get("/zmanager/billing/plans?days=60")).json()["days"] == 60
        assert (await c.get("/zmanager/billing/plans?days=6")).status_code == 422
        assert (await c.get("/zmanager/billing/plans?days=91")).status_code == 422


@pytest.mark.parametrize("role", ["workspace_owner", "manager", "staff"])
async def test_los_planes_son_solo_del_super_admin(role):
    async with _client(role) as c:
        assert (await c.get("/zmanager/billing/plans")).status_code == 404
        assert (await c.post("/zmanager/billing/plans/p1/preview", json={"price_cop": 1})).status_code == 404
        assert (await c.put("/zmanager/billing/plans/p1?confirmed=true", json={"price_cop": 1})).status_code == 404


async def test_editar_un_plan_sin_confirmar_no_hace_nada():
    async with _client("super_admin") as c:
        res = await c.put(f"/zmanager/billing/plans/{PA}", json={"price_cop": 130_000})
    assert res.status_code == 422 and "confirmación" in res.json()["detail"]


@pytest.mark.parametrize("body", [
    {"price_cop": -1}, {"price_cop": 99_999_999}, {"max_appointments": 0}, {"max_professionals": 0},
    {"name": "x"}, {"extra_professional_price_cop": -5}, {"is_active": "quizás"},
])
async def test_valores_fuera_de_rango_se_rechazan_antes_de_tocar_nada(body):
    async with _client("super_admin") as c:
        assert (await c.put(f"/zmanager/billing/plans/{PA}?confirmed=true", json=body)).status_code == 422
        assert (await c.post(f"/zmanager/billing/plans/{PA}/preview", json=body)).status_code == 422


async def test_un_plan_que_no_existe_es_404_y_un_id_malo_tambien():
    async with _client("super_admin") as c:
        assert (await c.post(f"/zmanager/billing/plans/{PA}/preview", json={"price_cop": 1})).status_code == 404
        assert (await c.post("/zmanager/billing/plans/no-es-uuid/preview", json={"price_cop": 1})).status_code == 404
        assert (await c.put("/zmanager/billing/plans/no-es-uuid?confirmed=true", json={"price_cop": 1})).status_code == 404


async def test_una_regla_de_negocio_rota_responde_422_con_el_motivo(monkeypatch):
    async def fake(db, plan_id, changes, now=None):
        raise bp.PlanError("El precio de lanzamiento no puede ser mayor que el precio normal.")
    monkeypatch.setattr(bp, "preview", fake)
    async with _client("super_admin") as c:
        res = await c.post(f"/zmanager/billing/plans/{PA}/preview", json={"launch_price_cop": 999_999})
    assert res.status_code == 422 and "lanzamiento" in res.json()["detail"]


async def test_editar_con_exito_audita_antes_y_despues(monkeypatch):
    calls = _audit(monkeypatch)
    seen = {}

    async def fake(db, plan_id, changes, now=None):
        seen["changes"] = changes
        return {"plan": {**ARRANQUE, "id": PA, "price_cop": 130_000}, "before": {"price_cop": 120_000}, "impact": {"subscribers": 3}}
    monkeypatch.setattr(bp, "update_plan", fake)
    async with _client("super_admin") as c:
        res = await c.put(f"/zmanager/billing/plans/{PA}?confirmed=true", json={"price_cop": 130_000})
    assert res.status_code == 200 and res.json()["plan"]["price_cop"] == 130_000
    assert seen["changes"] == {"price_cop": 130_000}  # solo lo enviado (exclude_unset)
    (audit,) = calls
    assert audit["action"] == "billing.plan_update" and audit["entity_id"] == PA
    assert audit["before_data"] == {"price_cop": 120_000} and audit["after_data"] == {"price_cop": 130_000}


async def test_quitar_el_precio_de_lanzamiento_llega_como_nulo_explicito(monkeypatch):
    _audit(monkeypatch)
    seen = {}

    async def fake(db, plan_id, changes, now=None):
        seen["changes"] = changes
        return {"plan": {**ARRANQUE, "id": PA}, "before": {"launch_price_cop": 50_000}, "impact": {}}
    monkeypatch.setattr(bp, "update_plan", fake)
    async with _client("super_admin") as c:
        await c.put(f"/zmanager/billing/plans/{PA}?confirmed=true", json={"launch_price_cop": None})
    assert seen["changes"] == {"launch_price_cop": None}


# ── Cambiar el nombre de un plan ─────────────────────────────────────────────

async def test_el_margen_se_asigna_por_id_aunque_dos_planes_se_llamen_igual(patched):
    """Un plan antiguo con el mismo nombre que uno vigente no se come su margen: se agrupa por id, no por nombre."""
    viejo = plan(PO, None, "Emprendedor", 99_000, None, 100, 2)
    items = [{"plan": "Emprendedor", "plan_id": PA, "revenue_cop": 100_000, "cost_cop": 10_000},
             {"plan": "Emprendedor", "plan_id": PO, "revenue_cop": 7_000, "cost_cop": 1_000}]
    patched(cost=costs(items))
    out = await bp.dashboard(DB(plans=(ARRANQUE, EQUIPO, viejo), subs=[sub("w1", PO, "active")]), 30, NOW)
    by = {p["id"]: p["stats"]["margin"] for p in out["plans"]}
    assert by[PA]["revenue_cop"] == 100_000 and by[PA]["margin_cop"] == 90_000
    assert by[PO]["revenue_cop"] == 7_000 and by[PO]["margin_cop"] == 6_000


async def test_renombrar_un_plan_no_cambia_su_margen_ni_sus_estadisticas(patched):
    renombrado = {**ARRANQUE, "name": "Inicio"}
    items = [{"plan": "Inicio", "plan_id": PA, "revenue_cop": 100_000, "cost_cop": 30_000}]
    patched(cost=costs(items))
    out = await bp.dashboard(DB(plans=(renombrado, EQUIPO), subs=[sub("w1", PA, "active")]), 30, NOW)
    p = next(x for x in out["plans"] if x["id"] == PA)
    assert p["name"] == "Inicio" and p["code"] == "emprendedor"
    assert p["stats"]["paying"] == 1 and p["stats"]["margin"]["margin_cop"] == 70_000


async def test_no_se_puede_poner_a_un_plan_el_nombre_de_otro(monkeypatch):
    monkeypatch.setattr(bp.bs, "get_entitlements", usage())
    db = DB(plan_row=ARRANQUE, name_taken=True)
    with pytest.raises(bp.PlanError, match="Ya existe otro plan"):
        await bp.preview(db, PA, {"name": "Equipo"}, NOW)
    with pytest.raises(bp.PlanError, match="Ya existe otro plan"):
        await bp.update_plan(db, PA, {"name": "equipo"}, NOW)    # sin distinguir mayúsculas
    assert not db.written("UPDATE billing_plans")


async def test_la_busqueda_de_nombre_repetido_ignora_al_propio_plan(monkeypatch):
    monkeypatch.setattr(bp.bs, "get_entitlements", usage())
    db = DB(plan_row=ARRANQUE)
    await bp.preview(db, PA, {"name": "Inicio"}, NOW)
    sql, params = next((q, p) for q, p in db.log if "lower(name)" in q)
    assert "id <> :i" in sql and params == {"n": "Inicio", "i": PA}   # el plan no choca consigo mismo


async def test_renombrar_cambia_solo_el_nombre_y_no_toca_el_codigo(monkeypatch):
    monkeypatch.setattr(bp.bs, "get_entitlements", usage())
    db = DB(plan_row=ARRANQUE)
    res = await bp.update_plan(db, PA, {"name": "Inicio"}, NOW)
    sql, params = next((q, p) for q, p in db.log if "UPDATE billing_plans" in q)
    assert params == {"name": "Inicio", "_id": PA} and "code" not in sql.split("WHERE")[0]
    assert res["plan"]["name"] == "Inicio" and res["plan"]["code"] == "emprendedor"


async def test_el_mismo_nombre_no_cuenta_como_cambio_ni_como_repetido(monkeypatch):
    db = DB(plan_row=ARRANQUE, name_taken=True)   # aunque «exista», si no cambia no se busca
    out = await bp.preview(db, PA, {"name": "Emprendedor"}, NOW)
    assert out["has_changes"] is False and not db.written("lower(name)")


# ── Precios para la landing (público) ────────────────────────────────────────

async def test_los_precios_publicos_traen_solo_lo_que_se_publica():
    out = await bp.public_pricing(DB(plans=(ARRANQUE, EQUIPO)))
    assert [p["code"] for p in out["plans"]] == ["emprendedor", "equipo"]
    assert set(out["plans"][0]) == {"code", "name", "description", "price_cop", "launch_price_cop", "max_appointments",
                                    "max_professionals", "extra_professional_price_cop"}   # ni id, ni estadísticas
    assert out["trial_days"] == 7 and out["launch_discount_cycles"] == 3 and out["founder_cap"] == 30
    assert out["addons"] == {"appointment_price_cop": 500, "blocks": [50, 100, 200, 300]}


async def test_la_consulta_publica_solo_pide_planes_activos_con_codigo_y_en_orden_de_precio():
    db = DB()
    await bp.public_pricing(db)
    sql = next(q for q, _ in db.log if "is_active = TRUE AND code IS NOT NULL" in q)
    assert "ORDER BY price_cop" in sql


async def test_los_parametros_de_la_plataforma_cambian_lo_que_publica_la_landing():
    db = DB()
    orig = db.handle

    def handle(q, p):
        if "FROM platform_settings" in q:
            return [{"key": "trial_days", "value": 14}, {"key": "founder_cap", "value": 50}, {"key": "launch_discount_cycles", "value": 2}]
        return orig(q, p)
    db.handle = handle
    out = await bp.public_pricing(db)
    assert (out["trial_days"], out["founder_cap"], out["launch_discount_cycles"]) == (14, 50, 2)


def _public_client(monkeypatch, fake):
    """La app SIN autenticación: es público."""
    import httpx
    from fastapi import FastAPI
    from api.routes import billing
    from core.database import get_db
    monkeypatch.setattr(bp, "public_pricing", fake)
    app = FastAPI()
    app.include_router(billing.router)
    app.dependency_overrides[get_db] = lambda: FakeSession()
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://t")


async def test_los_precios_publicos_no_piden_sesion_y_se_guardan_un_minuto(monkeypatch):
    async def fake(db):
        return {"plans": [{"code": "emprendedor"}], "trial_days": 7}
    async with _public_client(monkeypatch, fake) as c:
        res = await c.get("/billing/pricing")
    assert res.status_code == 200 and res.json()["plans"] == [{"code": "emprendedor"}]
    assert res.headers["cache-control"] == "public, max-age=60"


async def test_si_falla_la_lectura_la_landing_recibe_una_lista_vacia_y_no_un_error(monkeypatch):
    async def boom(db):
        raise RuntimeError('column "launch_price_cop" does not exist')   # p. ej. migración 022 sin aplicar
    async with _public_client(monkeypatch, boom) as c:
        res = await c.get("/billing/pricing")
    assert res.status_code == 200 and res.json() == {"plans": []}
    assert res.headers["cache-control"] == "no-store"          # un error no se guarda en cachés
