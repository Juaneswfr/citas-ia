from datetime import date

from services.appointment_agent import _SYSTEM, _chat_name, _thread_id
from services.platform_health import _kapso_cycle


def test_ciclo_kapso_antes_y_despues_del_corte():
    assert _kapso_cycle(date(2026, 11, 26)) == (date(2026, 10, 27), date(2026, 11, 27))
    assert _kapso_cycle(date(2026, 11, 27)) == (date(2026, 11, 27), date(2026, 12, 27))
    assert _kapso_cycle(date(2026, 1, 5)) == (date(2025, 12, 27), date(2026, 1, 27))


def test_prompt_asume_hoy_si_solo_dan_la_hora():
    assert "asume que es HOY" in _SYSTEM
    assert "8ppm" in _SYSTEM


def test_prompt_consulta_disponibilidad_antes_de_confirmar():
    assert "consultar_disponibilidad ANTES de pedir la confirmación" in _SYSTEM


def test_hilo_es_negocio_y_telefono():
    ctx = {"workspace": {"name": "Cuenta demo"}, "customer_name": "Juanes",
           "customer_phone": "573243273969", "conversation_id": "abc"}
    assert _thread_id(ctx) == "Cuenta demo | 573243273969"


def test_hilo_sin_negocio_o_telefono_no_queda_vacio():
    assert _thread_id({"customer_phone": "573243273969"}) == "573243273969"
    assert _thread_id({"conversation_id": "abc"}) == "abc"


def test_nombre_del_run_es_telefono_chat():
    assert _chat_name("573243273969", 1) == "573243273969 | Chat"
    assert _chat_name("573243273969", 2) == "573243273969 | Chat 2"
    assert _chat_name("", 1) == "Chat"


def test_tarifa_por_modelo():
    from services.billing_service import ai_cost_usd
    haiku = ai_cost_usd(1_000_000, 1_000_000)
    assert haiku == 6.0
    assert ai_cost_usd(1_000_000, 1_000_000, "anthropic:claude-haiku-4-5-20251001") == haiku
    assert ai_cost_usd(1_000_000, 1_000_000, "google_genai:gemini-3.5-flash-lite") == 2.8
    assert ai_cost_usd(1_000_000, 1_000_000, "otro:modelo-desconocido") == haiku


def test_texto_de_respuesta_con_bloques_de_gemini():
    from types import SimpleNamespace
    from services.appointment_agent import _reply_text
    assert _reply_text(SimpleNamespace(content="hola")) == "hola"
    assert _reply_text(SimpleNamespace(content=[{"type": "text", "text": "hola"}], text="hola")) == "hola"


def test_prompt_pone_lo_variable_al_final_para_la_cache():
    from services.appointment_agent import build_system_prompt
    ctx = {"workspace": {"name": "Cuenta demo", "timezone": "America/Bogota", "business_type": "salon"}}
    p = build_system_prompt(ctx, "svc-1 | Corte", "cal-1 | Juan", "Ninguna.")
    # lo fijo (reglas) viene antes que servicios, citas y hora
    assert p.index("FORMATO:") < p.index("SERVICIOS ACTUALES") < p.index("CITAS PRÓXIMAS") < p.index("AHORA MISMO")
    # el prefijo no depende de la hora ni de los datos del negocio que cambian
    other = build_system_prompt(ctx, "svc-2 | Otro", "cal-9 | Ana", "Una cita.")
    cut = p.index("SERVICIOS ACTUALES")
    assert p[:cut] == other[:cut]
