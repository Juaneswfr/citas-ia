"""Cuánto cuesta cada barbería y cuánto se gana con ella: IA + WhatsApp + fijos contra lo cobrado. BD falsa."""
from datetime import date, datetime, timezone

import pytest

from fake_session import FakeSession
from services import billing_costs as bc

pytestmark = pytest.mark.asyncio

TODAY = date(2026, 11, 20)  # con 30 días: del 22 de octubre al 20 de noviembre (el 21 ya no entra)


# ── Ingreso repartido por días ───────────────────────────────────────────────

def test_un_ciclo_dentro_de_la_ventana_cuenta_completo():
    assert bc.accrue(120_000, date(2026, 11, 1), date(2026, 12, 1), date(2026, 10, 1), date(2027, 1, 1)) == 120_000


def test_un_ciclo_que_cruza_la_ventana_cuenta_solo_sus_dias():
    # ciclo 5 nov - 5 dic (30 días); la ventana termina el 21 nov: 16 días de 30
    assert bc.accrue(120_000, date(2026, 11, 5), date(2026, 12, 5), date(2026, 10, 22), date(2026, 11, 21)) == pytest.approx(64_000)


def test_la_parte_de_un_ciclo_anterior_tambien_cuenta():
    # ciclo 5 oct - 5 nov (31 días); la ventana empieza el 22 oct: 14 días de 31
    assert bc.accrue(120_000, date(2026, 10, 5), date(2026, 11, 5), date(2026, 10, 22), date(2026, 11, 21)) == pytest.approx(120_000 * 14 / 31)


@pytest.mark.parametrize("p_start,p_end", [
    (date(2026, 1, 1), date(2026, 2, 1)),     # termina antes de la ventana
    (date(2027, 1, 1), date(2027, 2, 1)),     # empieza después
])
def test_un_ciclo_fuera_de_la_ventana_no_cuenta(p_start, p_end):
    assert bc.accrue(120_000, p_start, p_end, date(2026, 10, 22), date(2026, 11, 21)) == 0


def test_un_periodo_sin_dias_no_divide_por_cero():
    assert bc.accrue(50_000, date(2026, 11, 5), date(2026, 11, 5), date(2026, 10, 22), date(2026, 11, 21)) == 0


# ── Categoría de cada plantilla ──────────────────────────────────────────────

@pytest.mark.parametrize("kind,category", [
    ("reminder", "utility"), ("post_visit", "utility"), ("payment_due", "utility"), ("cancellation", "utility"),
    ("reactivation", "marketing"), ("algo_nuevo", "utility"),
])
def test_la_categoria_sale_de_la_plantilla(kind, category):
    assert bc.category_of(kind) == category


# ── Costo de WhatsApp: cada tarifa va por su lado ────────────────────────────

UTIL, MKT = 0.0008, 0.0125


def sends(**by_kind):
    """sends(reminder=(10, 4), reactivation=(5, 0)) -> [{kind, sent, in_window}]"""
    return [{"kind": k, "sent": s, "in_window": w} for k, (s, w) in by_kind.items()]


def test_utilidad_dentro_de_la_ventana_no_se_cobra_y_marketing_siempre():
    wa = bc.whatsapp_cost(sends(reminder=(10, 4), reactivation=(5, 5)), {"utility": UTIL, "marketing": MKT})
    assert (wa["sent"], wa["billable"], wa["free"]) == (15, 11, 4)  # 6 utilidad cobrables + 5 marketing (su ventana no cuenta)
    assert wa["cost_usd"] == pytest.approx(6 * UTIL + 5 * MKT)


def test_las_dos_tarifas_son_independientes_al_cambiar_una_la_otra_no_se_mueve():
    base = bc.whatsapp_cost(sends(reminder=(10, 0), reactivation=(10, 0)), {"utility": UTIL, "marketing": MKT})
    util_cara = bc.whatsapp_cost(sends(reminder=(10, 0), reactivation=(10, 0)), {"utility": 0.01, "marketing": MKT})
    mkt_cara = bc.whatsapp_cost(sends(reminder=(10, 0), reactivation=(10, 0)), {"utility": UTIL, "marketing": 0.05})
    by = lambda wa, kind: next(r for r in wa["by_kind"] if r["kind"] == kind)["cost_usd"]  # noqa: E731
    assert by(util_cara, "reactivation") == by(base, "reactivation")      # marketing no cambió
    assert by(util_cara, "reminder") == pytest.approx(10 * 0.01)
    assert by(mkt_cara, "reminder") == by(base, "reminder")               # utilidad no cambió
    assert by(mkt_cara, "reactivation") == pytest.approx(10 * 0.05)


def test_si_solo_cargaste_utilidad_marketing_queda_sin_calcular_y_utilidad_si():
    wa = bc.whatsapp_cost(sends(reminder=(10, 0), reactivation=(4, 0)), {"utility": UTIL})
    assert wa["rates_missing"] == ["marketing"]
    assert wa["cost_usd"] == pytest.approx(10 * UTIL)  # lo de utilidad se calcula igual
    mkt = next(r for r in wa["by_kind"] if r["kind"] == "reactivation")
    assert mkt["cost_usd"] is None and mkt["billable"] == 4  # no es 0: es «no se sabe»


def test_si_solo_cargaste_marketing_utilidad_queda_sin_calcular_y_marketing_si():
    wa = bc.whatsapp_cost(sends(reminder=(10, 0), reactivation=(4, 0)), {"marketing": MKT})
    assert wa["rates_missing"] == ["utility"] and wa["cost_usd"] == pytest.approx(4 * MKT)


def test_sin_ninguna_tarifa_avisa_las_dos():
    assert bc.whatsapp_cost(sends(reminder=(1, 0), reactivation=(1, 0)), {})["rates_missing"] == ["marketing", "utility"]


def test_una_categoria_sin_tarifa_no_se_avisa_si_no_hubo_mensajes_cobrables():
    # todos los recordatorios cayeron en ventana abierta: son gratis, no hace falta su tarifa
    wa = bc.whatsapp_cost(sends(reminder=(10, 10)), {})
    assert wa["rates_missing"] == [] and wa["billable"] == 0 and wa["cost_usd"] == 0


def test_cada_tipo_de_mensaje_se_cobra_con_la_tarifa_de_su_categoria():
    wa = bc.whatsapp_cost(sends(reminder=(2, 0), post_visit=(3, 0), payment_due=(1, 0), cancellation=(1, 0), reactivation=(2, 0)),
                          {"utility": UTIL, "marketing": MKT})
    assert wa["cost_usd"] == pytest.approx(7 * UTIL + 2 * MKT)


def test_pesos_solo_si_hay_tasa_del_dolar():
    assert bc._money(2.0, 4000) == 8000
    assert bc._money(2.0, None) is None          # hay dólares y falta la tasa: no se inventa un cero
    assert bc._money(0.0, None, fixed=500) == 500  # sin dólares, lo fijo sí se puede mostrar
    assert bc._money(2.0, 4000, fixed=500) == 8500


# ── El cálculo completo ──────────────────────────────────────────────────────

W_PAY, W_PAY2, W_TRIAL, W_GONE = "w-pay", "w-pay2", "w-trial", "w-borrado"


class CostDB(FakeSession):
    def __init__(self, fx=4000, rates=None, settings=None, ai=None, wa=None, invoices=None, bookings=None, info=None):
        self.fx = {"usd_cop": fx, "day": TODAY} if fx else None
        self.rates = [{"category": c, "usd_price": v} for c, v in (rates if rates is not None else {"utility": UTIL, "marketing": MKT}).items()]
        self.settings = [{"key": k, "value": v} for k, v in (settings or {}).items()]
        self.ai, self.wa, self.invoices, self.bookings = ai or [], wa or [], invoices or [], bookings or []
        self.info = info if info is not None else [
            {"id": W_PAY, "name": "Barbería Paga", "plan": "Emprendedor", "plan_id": "plan-a", "status": "active"},
            {"id": W_PAY2, "name": "Salón Callado", "plan": "Equipo", "plan_id": "plan-e", "status": "active"},
            {"id": W_TRIAL, "name": "En prueba", "plan": "Emprendedor", "plan_id": "plan-a", "status": "trial"},
        ]
        self.log = []

    def handle(self, q, p):
        self.log.append((q, p))
        if "FROM fx_rates" in q: return self.fx or []
        if "FROM meta_template_rates" in q: return self.rates
        if "FROM platform_settings" in q: return self.settings
        if "FROM agent_usage" in q: return self.ai
        if "FROM appointments" in q: return self.bookings
        if "FROM followup_sends fs" in q: return self.wa
        if "FROM billing_invoices" in q: return self.invoices
        if "FROM workspaces w" in q: return self.info
        if "FROM langsmith_sync_log" in q: return []
        return []


def ai_row(ws, usd, days=30, days_ls=30, runs=400, tokens=800_000):
    return {"workspace_id": ws, "days": days, "days_ls": days_ls, "runs": runs, "tokens": tokens, "cost_usd": usd}


def invoice(ws, amount=120_000, start=date(2026, 11, 5), end=date(2026, 12, 5)):
    return {"workspace_id": ws, "amount_cop": amount, "period_start": start, "period_end": end}


def wa_row(ws, kind, sent, in_window=0):
    return {"workspace_id": ws, "kind": kind, "sent": sent, "in_window": in_window}


async def test_costo_total_ingreso_y_margen_de_cada_barberia():
    db = CostDB(
        ai=[ai_row(W_PAY, 1.5), ai_row(W_TRIAL, 0.5)],
        wa=[wa_row(W_PAY, "reminder", 100, 20), wa_row(W_PAY, "reactivation", 10), wa_row(W_TRIAL, "reminder", 5)],
        invoices=[invoice(W_PAY)], bookings=[{"workspace_id": W_PAY, "n": 50}])
    out = await bc.costs(db, 30, today=TODAY)
    pay = next(i for i in out["items"] if i["workspace_id"] == W_PAY)
    # WhatsApp: 80 de utilidad cobrables (100 - 20 en ventana) + 10 de marketing
    wa_usd = 80 * UTIL + 10 * MKT
    assert pay["whatsapp"]["billable"] == 90 and pay["whatsapp"]["free"] == 20
    assert pay["whatsapp"]["cost_usd"] == pytest.approx(wa_usd, abs=1e-5)
    assert pay["cost_cop"] == round((1.5 + wa_usd) * 4000)
    assert pay["revenue_cop"] == 64_000                      # 16 de los 30 días del ciclo caen en la ventana
    assert pay["margin_cop"] == 64_000 - pay["cost_cop"]
    assert pay["margin_pct"] == pytest.approx(pay["margin_cop"] * 100 / 64_000, abs=0.1)
    assert pay["per_booking"]["cop"] == round((1.5 + wa_usd) / 50 * 4000)
    assert pay["ai"]["cost_usd"] == 1.5 and pay["ai"]["source"] == "langsmith"


async def test_los_costos_fijos_se_reparten_solo_entre_quienes_pagan_y_por_los_dias():
    db = CostDB(settings={"fixed_costs_cop_month": 300_000}, ai=[ai_row(W_TRIAL, 0.1)], invoices=[invoice(W_PAY)])
    out = await bc.costs(db, 15, today=TODAY)
    by = {i["workspace_id"]: i for i in out["items"]}
    assert by[W_PAY]["fixed_cop"] == 75_000 and by[W_PAY2]["fixed_cop"] == 75_000   # 300.000 x 15/30 / 2 negocios que pagan
    assert by[W_TRIAL]["fixed_cop"] == 0                                              # la prueba no carga costos fijos
    assert out["totals"]["fixed_cop"] == 150_000 and out["fixed_costs_cop_month"] == 300_000


async def test_sin_costos_fijos_configurados_no_se_asigna_nada():
    out = await bc.costs(CostDB(invoices=[invoice(W_PAY)]), 30, today=TODAY)
    assert out["totals"]["fixed_cop"] == 0 and all(i["fixed_cop"] == 0 for i in out["items"])


async def test_el_costo_por_cita_no_incluye_los_fijos():
    db = CostDB(settings={"fixed_costs_cop_month": 1_000_000}, ai=[ai_row(W_PAY, 2.0)], bookings=[{"workspace_id": W_PAY, "n": 100}])
    item = next(i for i in (await bc.costs(db, 30, today=TODAY))["items"] if i["workspace_id"] == W_PAY)
    assert item["per_booking"]["cop"] == 80  # 2 USD / 100 citas x 4000, sin el millón de fijos


async def test_una_barberia_que_paga_pero_no_usa_nada_aparece_con_su_ingreso():
    out = await bc.costs(CostDB(invoices=[invoice(W_PAY2)]), 30, today=TODAY)
    idle = next(i for i in out["items"] if i["workspace_id"] == W_PAY2)
    assert idle["cost_cop"] == 0 and idle["revenue_cop"] == 64_000 and idle["margin_cop"] == 64_000 and idle["ai"]["calls"] == 0


async def test_las_pruebas_cuestan_y_se_suman_aparte():
    db = CostDB(ai=[ai_row(W_TRIAL, 0.5)], wa=[wa_row(W_TRIAL, "reactivation", 4)])
    out = await bc.costs(db, 30, today=TODAY)
    trial = next(i for i in out["items"] if i["workspace_id"] == W_TRIAL)
    assert trial["paying"] is False and trial["revenue_cop"] == 0 and trial["margin_cop"] == -trial["cost_cop"]
    assert out["totals"]["trial_cost_cop"] == round((0.5 + 4 * MKT) * 4000)


async def test_los_que_mas_pierden_salen_primero():
    db = CostDB(ai=[ai_row(W_PAY, 0.1), ai_row(W_TRIAL, 3.0)], invoices=[invoice(W_PAY)])
    names = [i["workspace_id"] for i in (await bc.costs(db, 30, today=TODAY))["items"]]
    assert names[0] == W_TRIAL  # margen más negativo


async def test_si_falta_una_tarifa_solo_esa_categoria_queda_sin_calcular():
    db = CostDB(rates={"utility": UTIL}, wa=[wa_row(W_PAY, "reminder", 10), wa_row(W_PAY, "reactivation", 4)])
    out = await bc.costs(db, 30, today=TODAY)
    pay = next(i for i in out["items"] if i["workspace_id"] == W_PAY)
    assert out["rates_missing"] == ["marketing"] and pay["whatsapp"]["rates_missing"] == ["marketing"]
    assert pay["whatsapp"]["cost_usd"] == pytest.approx(10 * UTIL)   # utilidad se calculó
    assert out["meta_rates"] == {"utility": UTIL}


async def test_sin_tasa_del_dolar_no_inventa_pesos_ni_margen():
    db = CostDB(fx=None, ai=[ai_row(W_PAY, 1.0)], invoices=[invoice(W_PAY)])
    out = await bc.costs(db, 30, today=TODAY)
    pay = next(i for i in out["items"] if i["workspace_id"] == W_PAY)
    assert out["usd_cop"] is None
    assert pay["cost_cop"] is None and pay["margin_cop"] is None and pay["margin_pct"] is None
    assert pay["revenue_cop"] == 64_000 and pay["ai"]["cost_usd"] == 1.0   # el ingreso y los dólares siguen a la vista
    assert out["totals"]["cost_cop"] is None and out["totals"]["margin_cop"] is None


async def test_un_negocio_borrado_se_ignora():
    out = await bc.costs(CostDB(ai=[ai_row(W_GONE, 9.0)]), 30, today=TODAY)
    assert all(i["workspace_id"] != W_GONE for i in out["items"])


async def test_la_ventana_incluye_hoy_y_no_mañana():
    db = CostDB()
    out = await bc.costs(db, 30, today=TODAY)
    assert out["since"] == date(2026, 10, 22) and out["until"] == TODAY   # 30 días contando hoy
    usage = next(p for q, p in db.log if "FROM agent_usage" in q)
    assert usage == {"since": date(2026, 10, 22)}                          # y la consulta recibe exactamente esa fecha
    invoices = next(p for q, p in db.log if "FROM billing_invoices" in q)
    assert invoices == {"since": date(2026, 10, 22), "until": date(2026, 11, 21)}  # el día de mañana, exclusivo


async def test_los_dias_se_acotan_entre_1_y_90():
    assert (await bc.costs(CostDB(), 9999, today=TODAY))["days"] == 90
    assert (await bc.costs(CostDB(), 0, today=TODAY))["days"] == 1


async def test_los_parametros_de_fecha_viajan_como_fechas_no_como_enteros():
    """Un entero restado a una fecha en SQL rompe en Postgres; aquí las fechas se calculan en Python y se pasan ya hechas."""
    db = CostDB()
    await bc.costs(db, 30, today=TODAY)
    dated = [p for q, p in db.log if p and ("since" in p or "until" in p)]
    assert dated and all(isinstance(v, date) for p in dated for k, v in p.items() if k in ("since", "until"))
    assert not any("d" in p for q, p in db.log if p)


async def test_el_ingreso_de_dos_ciclos_en_la_ventana_se_suma():
    db = CostDB(invoices=[invoice(W_PAY, start=date(2026, 10, 5), end=date(2026, 11, 5)), invoice(W_PAY)])
    pay = next(i for i in (await bc.costs(db, 30, today=TODAY))["items"] if i["workspace_id"] == W_PAY)
    assert pay["revenue_cop"] == round(120_000 * 14 / 31 + 64_000)


async def test_los_totales_suman_a_las_barberias():
    db = CostDB(ai=[ai_row(W_PAY, 1.0), ai_row(W_PAY2, 2.0)], invoices=[invoice(W_PAY), invoice(W_PAY2, 285_000)])
    out = await bc.costs(db, 30, today=TODAY)
    t = out["totals"]
    assert t["revenue_cop"] == sum(i["revenue_cop"] for i in out["items"])
    assert t["cost_cop"] == sum(i["cost_cop"] for i in out["items"])
    assert t["margin_cop"] == t["revenue_cop"] - t["cost_cop"]
    assert t["margin_pct"] == round(t["margin_cop"] * 100 / t["revenue_cop"], 1)


async def test_cada_fila_dice_a_que_plan_pertenece_por_su_id():
    out = await bc.costs(CostDB(invoices=[invoice(W_PAY)]), 30, today=TODAY)
    by = {i["workspace_id"]: i for i in out["items"]}
    assert by[W_PAY]["plan_id"] == "plan-a" and by[W_PAY2]["plan_id"] == "plan-e"
