"""Cuentas del plan de pagos: ciclo, descuento, prorrateo y nivel de cupo. Sin BD."""
from datetime import date, datetime, timedelta, timezone

from services import billing_service as b


# ── Ciclo de facturación ─────────────────────────────────────────────────────

def test_ciclo_empieza_el_dia_de_activacion():
    assert b.cycle_bounds(5, date(2026, 1, 20)) == (date(2026, 1, 5), date(2026, 2, 5))


def test_antes_del_dia_ancla_el_ciclo_viene_del_mes_anterior():
    assert b.cycle_bounds(5, date(2026, 2, 3)) == (date(2026, 1, 5), date(2026, 2, 5))


def test_el_mismo_dia_ancla_ya_es_ciclo_nuevo():
    assert b.cycle_bounds(5, date(2026, 2, 5)) == (date(2026, 2, 5), date(2026, 3, 5))


def test_mes_sin_ese_dia_se_cobra_el_ultimo_dia_sin_desplazar_el_ancla():
    assert b.cycle_bounds(31, date(2026, 2, 10)) == (date(2026, 1, 31), date(2026, 2, 28))
    assert b.cycle_bounds(31, date(2026, 3, 5)) == (date(2026, 2, 28), date(2026, 3, 31))
    assert b.cycle_bounds(31, date(2028, 2, 29)) == (date(2028, 2, 29), date(2028, 3, 31))  # bisiesto


def test_ciclo_cruza_el_cambio_de_año():
    assert b.cycle_bounds(15, date(2026, 12, 20)) == (date(2026, 12, 15), date(2027, 1, 15))
    assert b.cycle_bounds(15, date(2027, 1, 2)) == (date(2026, 12, 15), date(2027, 1, 15))


# ── Descuento de lanzamiento ─────────────────────────────────────────────────

def test_precios_de_lanzamiento_del_documento():
    assert b.launch_price(120_000) == 50_000
    assert b.launch_price(285_000) == 120_000


def test_precio_del_ciclo_con_y_sin_descuento():
    assert b.price_for_cycle(120_000, 50_000, 3, None) == 50_000
    assert b.price_for_cycle(120_000, 50_000, 0, None) == 120_000  # desde el cuarto ciclo
    assert b.price_for_cycle(120_000, 50_000, 0, 100_000) == 100_000  # fundador: valor real congelado
    assert b.price_for_cycle(285_000, 120_000, 2, None) == 120_000


# ── Cambios de plan ──────────────────────────────────────────────────────────

def test_subir_de_plan_ejemplo_del_documento():
    # Emprendedor con descuento → Equipo con descuento, a los 15 días de un ciclo de 30.
    assert b.prorate_upgrade(50_000, 120_000, 15, 30) == 35_000


def test_prorrateo_no_es_negativo_ni_con_ciclo_vacio():
    assert b.prorate_upgrade(120_000, 50_000, 15, 30) == 0
    assert b.prorate_upgrade(50_000, 120_000, 15, 0) == 0
    assert b.prorate_upgrade(50_000, 120_000, -3, 30) == 0


def test_barbero_adicional_paga_los_dias_que_le_quedan():
    assert b.professional_prorata(40_000, 15, 30) == 20_000
    assert b.professional_prorata(40_000, 40, 30) == 40_000  # nunca más del mes completo


def test_barberos_extra_solo_por_encima_del_limite():
    assert b.extra_professionals(2, 3) == 0
    assert b.extra_professionals(3, 3) == 0
    assert b.extra_professionals(5, 3) == 2
    assert b.extra_professionals(9, None) == 0


# ── Cupo de citas ────────────────────────────────────────────────────────────

def test_niveles_de_cupo_emprendedor():
    lvl = lambda used: b.quota_level(used, 250, 20, 80)
    assert lvl(0) == "ok"
    assert lvl(199) == "ok"
    assert lvl(200) == "warn"       # 80 %
    assert lvl(249) == "warn"
    assert lvl(250) == "over"       # se acabó, aún agenda dentro del margen
    assert lvl(269) == "over"
    assert lvl(270) == "blocked"    # pasado el margen de 20


def test_el_bloque_adicional_amplia_el_cupo():
    assert b.quota_level(260, 300, 20, 80) == "warn"
    assert b.quota_level(300, 300, 20, 80) == "over"


def test_cupo_cero_no_divide_por_cero():
    assert b.quota_level(0, 0, 20, 80) == "over"
    assert b.quota_level(20, 0, 20, 80) == "blocked"


# ── Varios ───────────────────────────────────────────────────────────────────

def test_numero_normalizado_para_reclamar_la_oferta_una_vez():
    assert b.normalize_phone("+57 300 111-2233") == "573001112233"
    assert b.normalize_phone(None) == ""


def test_costo_estimado_de_ia():
    assert b.ai_cost_usd(1_000_000, 0) == 1.0
    assert b.ai_cost_usd(0, 1_000_000) == 5.0
    assert b.ai_cost_usd(2_000, 100) == 0.0025


NOW = datetime(2026, 3, 10, 12, tzinfo=timezone.utc)


def test_prueba_vencida_el_dia_8_aunque_el_worker_no_haya_corrido():
    sub = {"status": "trial", "trial_ends_at": NOW - timedelta(minutes=1)}
    assert b.effective_status(sub, NOW, None, NOW.date(), 5) == "expired"
    sub["trial_ends_at"] = NOW + timedelta(days=1)
    assert b.effective_status(sub, NOW, None, NOW.date(), 5) == "trial"


def test_mora_con_gracia_de_5_dias():
    sub = {"status": "past_due", "past_due_since": NOW - timedelta(days=4)}
    assert b.effective_status(sub, NOW, None, NOW.date(), 5) == "past_due"
    sub["past_due_since"] = NOW - timedelta(days=5)
    assert b.effective_status(sub, NOW, None, NOW.date(), 5) == "paused"


def test_cancelacion_tiene_efecto_al_final_del_ciclo_pagado():
    sub = {"status": "active", "cancel_at_period_end": True}
    assert b.effective_status(sub, NOW, date(2026, 3, 20), date(2026, 3, 10), 5) == "active"
    assert b.effective_status(sub, NOW, date(2026, 3, 10), date(2026, 3, 10), 5) == "cancelled"
