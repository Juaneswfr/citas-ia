"""Freno de conversaciones cíclicas (services/agent_guard.py): detección y pausa."""
from datetime import datetime, timedelta, timezone

import pytest

from services import agent_guard
from fake_session import FakeSession

NOW = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc)


def msgs(*items, minutes_apart=1):
    """Del más nuevo al más viejo, como los entrega la consulta. Cada item: (quién, texto)."""
    sender = {"c": ("inbound", "customer"), "a": ("outbound", "agent"), "h": ("outbound", "human"),
              "s": ("outbound", "system")}
    return [{"direction": sender[who][0], "sender_type": sender[who][1], "content": text,
             "created_at": NOW - timedelta(minutes=i * minutes_apart)} for i, (who, text) in enumerate(items)]


def test_conversacion_normal_no_se_pausa():
    rows = msgs(("c", "las 3"), ("a", "¿A qué hora?"), ("c", "corte"), ("a", "¿Qué servicio?"), ("c", "hola"))
    assert agent_guard.detect_loop(rows, NOW) is None


def test_tres_respuestas_casi_iguales_seguidas_son_un_bucle():
    rows = msgs(("c", "?"), ("a", "Solo puedo ayudarte con citas. ¿Quieres agendar?"),
                ("c", "?"), ("a", "Solo puedo ayudarte con citas, ¿quieres agendar?"),
                ("c", "?"), ("a", "solo puedo ayudarte con citas ¡quieres agendar!"))
    assert agent_guard.detect_loop(rows, NOW) == agent_guard.REPEATING


def test_dos_respuestas_iguales_todavia_no():
    rows = msgs(("c", "?"), ("a", "No entendí."), ("c", "?"), ("a", "No entendí."), ("c", "hola"))
    assert agent_guard.detect_loop(rows, NOW) is None


def test_ofrecer_horas_distintas_es_avanzar_no_repetirse():
    rows = msgs(("c", "no puedo"), ("a", "¿Te sirve a las 3:00 pm?"), ("c", "tampoco"),
                ("a", "¿Te sirve a las 4:00 pm?"), ("c", "no"), ("a", "¿Te sirve a las 5:00 pm?"))
    assert agent_guard.detect_loop(rows, NOW) is None


def test_la_misma_oferta_con_las_mismas_cifras_si_es_repeticion():
    rows = msgs(*[("a", "¿Te sirve a las 3:00 pm?") for _ in range(3)])
    assert agent_guard.detect_loop(rows, NOW) == agent_guard.REPEATING


def test_respuestas_distintas_no_cuentan_como_repeticion():
    rows = msgs(("a", "¿Con quién quieres la cita?"), ("a", "¿Qué día te sirve?"), ("a", "¿A qué hora?"))
    assert agent_guard.detect_loop(rows, NOW) is None


def test_demasiadas_respuestas_sin_lograr_nada_se_pausa():
    rows = msgs(*[("a", f"Respuesta distinta número {i} sobre otro tema") for i in range(agent_guard.MAX_AGENT_TURNS)])
    assert "14 respuestas sin llegar a agendar" in agent_guard.detect_loop(rows, NOW)
    assert agent_guard.detect_loop(rows[1:], NOW) is None  # una menos: todavía no


def test_una_cita_confirmada_reinicia_la_cuenta():
    rows = msgs(*[("a", f"Charla sin fin número {i}") for i in range(6)],
                ("a", "Tu cita de Corte quedó confirmada para el 14/11/2026 a las 15:00."),
                *[("a", f"Charla de antes número {i}") for i in range(20)])
    assert agent_guard.detect_loop(rows, NOW) is None


@pytest.mark.parametrize("goal", ["Tu cita de Corte quedó reagendada para el 15/11/2026 a las 10:00.",
                                  "Listo, tu cita fue cancelada."])
def test_mover_o_cancelar_tambien_reinicia(goal):
    rows = msgs(("a", "Hola de nuevo"), ("a", goal), *[("a", "Hola de nuevo") for _ in range(10)])
    assert agent_guard.detect_loop(rows, NOW) is None


def test_si_una_persona_respondio_se_empieza_de_cero():
    rows = msgs(("a", "No entendí."), ("h", "Hola, soy Ana, ¿en qué te ayudo?"),
                ("a", "No entendí."), ("a", "No entendí."), ("a", "No entendí."))
    assert agent_guard.detect_loop(rows, NOW) is None


def test_mensajes_de_hace_mas_de_seis_horas_son_otra_conversacion():
    rows = msgs(("a", "No entendí."), ("a", "No entendí."), ("a", "No entendí."), minutes_apart=200)
    assert agent_guard.detect_loop(rows, NOW) is None
    assert agent_guard.detect_loop(msgs(("a", "No entendí."), ("a", "No entendí."), ("a", "No entendí.")), NOW)


def test_avisos_automaticos_del_sistema_no_cuentan_como_respuestas_del_agente():
    rows = msgs(*[("s", "Recordatorio de tu cita") for _ in range(20)])
    assert agent_guard.detect_loop(rows, NOW) is None


# ── Pausa ─────────────────────────────────────────────────────────────────────

class DB(FakeSession):
    def __init__(self): self.sql, self.committed = [], 0
    async def commit(self): self.committed += 1

    def handle(self, sql, p):
        self.sql.append((sql, p))
        return [{"who": "Ana Gómez"}] if "SELECT COALESCE(name, phone)" in sql else []


@pytest.mark.asyncio
async def test_pausar_apaga_al_cliente_deja_alerta_y_confirma():
    db = DB()
    await agent_guard.pause_agent(db, {"id": "conv1", "workspace_id": "ws-1", "customer_id": "cu1"},
                                  agent_guard.REPEATING)
    update = next(p for q, p in db.sql if "UPDATE customers SET agent_enabled = FALSE" in q)
    assert update == {"c": "cu1", "w": "ws-1"}  # acotado al negocio
    alert = next(p for q, p in db.sql if "INSERT INTO agent_alerts" in q)
    assert alert["w"] == "ws-1" and alert["conv"] == "conv1"
    assert "Ana Gómez" in alert["reason"] and "repitiendo la misma respuesta" in alert["reason"]
    assert "interruptor «Agente»" in alert["reason"] and db.committed == 1


@pytest.mark.asyncio
async def test_pausar_sin_cliente_solo_deja_la_alerta():
    db = DB()
    await agent_guard.pause_agent(db, {"id": "conv1", "workspace_id": "ws-1"}, "x")
    assert not any("UPDATE customers" in q for q, _ in db.sql)
    assert any("INSERT INTO agent_alerts" in q for q, _ in db.sql) and db.committed == 1
