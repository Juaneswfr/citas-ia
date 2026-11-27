"""Consumo de la transcripción de audios por negocio y día: falla «abierto», nunca tumba la respuesta al cliente."""
import pytest

from fake_session import FakeSession
from services import audio_usage
from services.audio_transcription import Transcription

pytestmark = pytest.mark.asyncio


class Recorder(FakeSession):
    def __init__(self):
        self.calls, self.commits = [], 0

    def handle(self, sql, params):
        self.calls.append((sql, params))
        return []

    async def commit(self):
        self.commits += 1


async def test_guarda_una_fila_por_negocio_y_dia_con_el_costo_estimado(monkeypatch):
    db = Recorder()
    monkeypatch.setattr(audio_usage, "AsyncSessionLocal", lambda: db)
    t = Transcription(text="hola", size_bytes=4000, seconds=30.0, input_tokens=500, output_tokens=20)
    await audio_usage.record("ws-1", t)
    sql, params = db.calls[0]
    assert "INSERT INTO audio_usage" in sql and "ON CONFLICT (workspace_id, day)" in sql  # suma, no pisa
    assert params == {"w": "ws-1", "s": 30.0, "i": 500, "o": 20, "c": round(t.cost_usd, 6)}
    assert db.commits == 1


async def test_la_duracion_desconocida_se_guarda_como_nula(monkeypatch):
    db = Recorder()
    monkeypatch.setattr(audio_usage, "AsyncSessionLocal", lambda: db)
    await audio_usage.record("ws-1", Transcription(text="", size_bytes=2000))
    assert db.calls[0][1]["s"] is None


async def test_si_la_bd_falla_no_lanza(monkeypatch):
    class Broken(Recorder):
        def handle(self, sql, params):
            raise RuntimeError('relation "audio_usage" does not exist')

    monkeypatch.setattr(audio_usage, "AsyncSessionLocal", lambda: Broken())
    await audio_usage.record("ws-1", Transcription(text="hola"))  # sin la migración 028: solo se deja en el log
