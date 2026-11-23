"""Análisis semana a semana y precipicio de precio. BD falsa."""
from datetime import date

import pytest

from fake_session import FakeSession
from services import billing_insights as bi

pytestmark = pytest.mark.asyncio

TODAY = date(2026, 11, 20)  # viernes; su semana empieza el lunes 16


# ── Semanas ──────────────────────────────────────────────────────────────────

def test_las_semanas_van_de_lunes_a_lunes_y_la_ultima_es_la_actual():
    ms = bi.mondays(TODAY, 4)
    assert ms[-1] == date(2026, 11, 16) and len(ms) == 4
    assert all(m.weekday() == 0 for m in ms)
    assert ms[0] == date(2026, 10, 26)


# ── Cuándo llega al precio completo ──────────────────────────────────────────

def test_sin_factura_del_siguiente_ciclo_ese_ciclo_ya_es_el_primero_con_descuento():
    # le quedan 3 ciclos con descuento: el siguiente (5 dic) y dos más; el completo es el 5 mar
    assert bi.first_full_price_cycle(date(2026, 12, 5), 5, 3, False) == date(2027, 3, 5)


def test_si_la_factura_del_siguiente_ciclo_ya_salio_esa_ya_gasto_un_descuento():
    assert bi.first_full_price_cycle(date(2026, 12, 5), 5, 3, True) == date(2027, 4, 5)


def test_el_ancla_31_cae_en_el_ultimo_dia_de_un_mes_corto():
    assert bi.first_full_price_cycle(date(2026, 12, 31), 31, 2, False) == date(2027, 2, 28)


def sub(plan="emprendedor", left=1, anchor=5, invoiced=False, price=120_000, launch=50_000, frozen=None):
    return {"plan": plan, "anchor_day": anchor, "discount_left": left, "next_invoiced": invoiced,
            "price": price, "launch": launch, "frozen": frozen}


def by_month(months):
    return {m["month"]: m for m in months}


def test_cuenta_negocios_y_cuanto_suben_por_mes():
    # hoy 20 nov, ancla 5: el ciclo siguiente empieza el 5 dic. Le queda 1 descuento: ese es el último, completo el 5 ene.
    out = by_month(bi.cliff_months(TODAY, [sub(left=1), sub(left=1, plan="equipo", price=285_000, launch=120_000), sub(left=3)]))
    assert out["2027-01"]["businesses"] == 2
    assert out["2027-01"]["extra_cop"] == 70_000 + 165_000
    assert out["2027-01"]["by_plan"] == {"emprendedor": 1, "equipo": 1}
    assert out["2027-03"]["businesses"] == 1


def test_siempre_hay_seis_meses_aunque_esten_vacios():
    months = bi.cliff_months(TODAY, [])
    assert [m["month"] for m in months] == ["2026-11", "2026-12", "2027-01", "2027-02", "2027-03", "2027-04"]
    assert all(m["businesses"] == 0 and m["extra_cop"] == 0 for m in months)


def test_el_fundador_con_valor_congelado_igual_o_menor_no_es_riesgo():
    # su precio después del descuento es el congelado, que es el mismo que ya paga: no sube nada
    assert all(m["businesses"] == 0 for m in bi.cliff_months(TODAY, [sub(left=1, frozen=50_000)]))


def test_el_fundador_con_valor_congelado_mayor_al_descuento_si_sube_a_ese_valor():
    out = by_month(bi.cliff_months(TODAY, [sub(left=1, frozen=100_000)]))
    assert out["2027-01"]["extra_cop"] == 50_000


def test_un_plan_sin_lanzamiento_no_aparece():
    assert all(m["businesses"] == 0 for m in bi.cliff_months(TODAY, [sub(left=2, launch=None)]))


def test_sin_descuento_pendiente_no_aparece():
    assert all(m["businesses"] == 0 for m in bi.cliff_months(TODAY, [sub(left=0)]))


def test_mas_alla_de_seis_meses_no_se_cuenta():
    assert all(m["businesses"] == 0 for m in bi.cliff_months(TODAY, [sub(left=9)]))


# ── Lectura completa ─────────────────────────────────────────────────────────

class DB(FakeSession):
    def __init__(self, fx=True, rates=True, fixed=None):
        self.fx = [{"usd_cop": 4000, "day": TODAY}] if fx else []
        self.rates = [{"category": "utility", "usd_price": 0.001}, {"category": "marketing", "usd_price": 0.01}] if rates else []
        self.settings = [{"key": "fixed_costs_cop_month", "value": fixed}] if fixed is not None else []
        self.log = []
        self.booked = []

    def handle(self, q, p):
        self.log.append((q, p))
        if "FROM fx_rates" in q: return self.fx
        if "FROM meta_template_rates" in q: return self.rates
        if "FROM platform_settings" in q: return self.settings
        if "WITH booked AS" in q: return self.booked
        if "FROM agent_usage" in q: return [{"week": date(2026, 11, 16), "usd": 2.0}]
        if "FROM followup_sends fs" in q:
            return [{"week": date(2026, 11, 16), "kind": "reminder", "sent": 10, "in_window": 4},
                    {"week": date(2026, 11, 16), "kind": "reactivation", "sent": 2, "in_window": 0}]
        if "FROM billing_invoices\n" in q or "FROM billing_invoices WHERE status = 'paid'" in q.replace("\n                ", " "):
            return [{"amount_cop": 140_000, "period_start": date(2026, 11, 5), "period_end": date(2026, 12, 5)}]
        if "FROM appointments\n                FROM" in q: return []
        if "COUNT(*) AS total, COUNT(*) FILTER" in q and "date_trunc" in q:
            return [{"week": date(2026, 11, 16), "total": 9, "assistant": 6}]
        if "JOIN services s" in q:
            return [{"id": "a1", "value_cop": 300_000, "start_at": TODAY, "status": "completed", "workspace": "Barbería", "service": "Corte"}]
        if "FROM subscriptions s" in q: return []
        if "COUNT(*) AS total, COUNT(*) FILTER" in q: return {"total": 40, "assistant": 25}
        return []


async def test_una_semana_junta_ingreso_costo_y_citas():
    out = await bi.insights(DB(), 4, TODAY)
    assert len(out["weekly"]) == 4
    w = out["weekly"][-1]
    assert w["week"] == date(2026, 11, 16)
    # IA: 2 US$ × 4000; WhatsApp: utilidad 6 cobrables × 0,001 + marketing 2 × 0,01 = 0,026 US$ × 4000 = 104
    assert w["ai_cop"] == 8000 and w["whatsapp_cop"] == 104 and w["cost_cop"] == 8104
    assert w["revenue_cop"] == round(140_000 * 7 / 30)
    assert w["margin_cop"] == w["revenue_cop"] - 8104
    assert (w["appointments"], w["assistant"]) == (9, 6)
    assert (w["templates_sent"], w["templates_billable"], w["templates_free"]) == (12, 8, 4)


async def test_una_semana_sin_nada_es_cero_no_falta():
    out = await bi.insights(DB(), 4, TODAY)
    first = out["weekly"][0]
    assert (first["appointments"], first["templates_sent"], first["ai_cop"]) == (0, 0, 0)


async def test_los_fijos_se_reparten_por_semana():
    out = await bi.insights(DB(fixed=300_000), 4, TODAY)
    assert out["weekly"][0]["fixed_cop"] == 70_000 and out["weekly"][0]["cost_cop"] == 70_000


async def test_sin_dolar_no_hay_costo_ni_margen_pero_si_los_conteos():
    out = await bi.insights(DB(fx=False), 4, TODAY)
    w = out["weekly"][-1]
    assert w["ai_cop"] is None and w["cost_cop"] is None and w["margin_cop"] is None
    assert w["appointments"] == 9 and w["templates_sent"] == 12


async def test_sin_tarifa_de_una_categoria_lo_avisa():
    db = DB(rates=False)
    out = await bi.insights(db, 4, TODAY)
    assert out["rates_missing"] == ["marketing", "utility"]


async def test_trae_la_cita_mas_cara_y_los_totales():
    out = await bi.insights(DB(), 4, TODAY)
    assert out["top_appointments"][0]["value_cop"] == 300_000
    assert out["appointments_all_time"] == {"total": 40, "assistant": 25}


async def test_las_semanas_se_acotan():
    assert (await bi.insights(DB(), 1, TODAY))["weeks"] == 2
    assert (await bi.insights(DB(), 99, TODAY))["weeks"] == bi.MAX_WEEKS


async def test_las_consultas_no_restan_ni_suman_parametros_a_fechas():
    db = DB()
    await bi.insights(db, 4, TODAY)
    assert all(isinstance(p.get("since"), date) for _, p in db.log if "since" in p)


# ── Las citas que más costaron de IA ─────────────────────────────────────────

def cita(i, usd, tokens=1000, runs=2, measured=2, with_ls=0):
    return {"id": i, "created_at": TODAY, "workspace": "Barbería", "service": "Corte", "usd": usd, "tokens": tokens,
            "runs": runs, "measured": measured, "with_ls": with_ls}


def test_el_ranking_va_de_la_mas_cara_a_la_mas_barata_con_promedio_y_mediana():
    out = bi.summarize_ai_cost([cita("a", 0.01), cita("b", 0.05), cita("c", 0.03)], 4000)
    assert [t["id"] for t in out["top"]] == ["b", "c", "a"]
    assert out["measured"] == 3 and out["avg_usd"] == 0.03 and out["median_usd"] == 0.03
    assert out["top"][0]["cop"] == 200 and out["median_cop"] == 120


def test_una_cita_sin_ninguna_ejecucion_medida_no_cuenta_como_gratis():
    out = bi.summarize_ai_cost([cita("vieja", 0, measured=0), cita("nueva", 0.02)], 4000)
    assert out["measured"] == 1 and out["without_measure"] == 1
    assert [t["id"] for t in out["top"]] == ["nueva"]


def test_sin_citas_medidas_no_inventa_promedios():
    out = bi.summarize_ai_cost([cita("vieja", 0, measured=0)], 4000)
    assert out["measured"] == 0 and out["avg_usd"] is None and out["median_usd"] is None and out["top"] == []


def test_sin_dolar_el_costo_va_en_dolares_y_no_en_pesos():
    out = bi.summarize_ai_cost([cita("a", 0.02)], None)
    assert out["top"][0]["usd"] == 0.02 and out["top"][0]["cop"] is None and out["avg_cop"] is None


def test_solo_trae_las_diez_mas_caras():
    out = bi.summarize_ai_cost([cita(str(i), 0.001 * (i + 1)) for i in range(15)], 4000)
    assert len(out["top"]) == 10 and out["measured"] == 15 and out["top"][0]["id"] == "14"


@pytest.mark.parametrize("measured,ls,expected", [(0, 0, "estimate"), (3, 0, "estimate"), (3, 3, "langsmith"), (3, 1, "mixed")])
def test_de_donde_sale_el_costo_de_una_cita(measured, ls, expected):
    assert bi.source_of_run_costs(measured, ls) == expected


async def test_el_analisis_incluye_el_costo_de_ia_por_cita():
    db = DB()
    db.booked = [cita("a", 0.04, with_ls=2), cita("b", 0.01)]
    out = await bi.insights(db, 4, TODAY)
    assert out["ai_per_appointment"]["available"] is True
    assert out["ai_per_appointment"]["top"][0]["id"] == "a" and out["ai_per_appointment"]["top"][0]["source"] == "langsmith"


async def test_sin_la_migracion_24_el_resto_del_analisis_sigue_funcionando():
    class Old(DB):
        def handle(self, q, p):
            if "WITH booked AS" in q:
                raise RuntimeError('column "cost_usd" of relation "agent_runs" does not exist')
            return super().handle(q, p)
    out = await bi.insights(Old(), 4, TODAY)
    assert out["ai_per_appointment"] == {"available": False}
    assert len(out["weekly"]) == 4
