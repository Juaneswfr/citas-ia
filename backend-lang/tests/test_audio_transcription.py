"""Audios de WhatsApp: transcripción con Gemini 3.5 Transcribe y su paso por el webhook de mensajes.

Sin red ni BD: la API de Google se simula con httpx.MockTransport y el webhook con las mismas piezas
falsas de test_receipts.py.
"""
import base64
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
import pytest

from services import audio_transcription as at, inbound_message_service as inbound
from services.whatsapp_provider import ProviderError

pytestmark = pytest.mark.asyncio


def _ogg(seconds=None):
    """Un ogg mínimo: la última página lleva la posición final (48 kHz) de la que sale la duración."""
    granule = -1 if seconds is None else int(seconds * 48000)
    return b"OggS\x00\x04" + granule.to_bytes(8, "little", signed=True) + b"\x00" * 40


OGG = _ogg()
KEY = "g-test"


def _ok(text="hola", usage=None):
    body = {"id": "i1", "status": "completed",
            "steps": [{"type": "model_output", "content": [{"type": "text", "text": text}]}]}
    if usage is not None:
        body["usage"] = usage
    return httpx.Response(200, json=body)


async def _transcribe(handler, data=OGG):
    return await at.transcribe(data, api_key=KEY, model="m", transport=httpx.MockTransport(handler))


# ── detect_audio ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("data,expected", [
    (OGG, "audio/ogg"),
    (b"ID3" + b"0" * 20, "audio/mpeg"),
    (b"\xff\xfb" + b"0" * 20, "audio/mpeg"),
    (b"\xff\xf1" + b"0" * 20, "audio/aac"),       # AAC crudo (ADTS)
    (b"\xff\xf9" + b"0" * 20, "audio/aac"),
    (b"\x00\x00\x00\x20ftypM4A " + b"0" * 20, "audio/m4a"),
    (b"RIFF\x00\x00\x00\x00WAVE" + b"0" * 20, "audio/wav"),
    (b"\x1aE\xdf\xa3" + b"0" * 20, "audio/webm"),
    (b"#!AMR\n" + b"0" * 20, None),               # AMR: lo admite WhatsApp pero no la API
    (b"GIF89a" + b"0" * 20, None),
    (b"", None),
])
def test_detect_audio(data, expected):
    assert at.detect_audio(data) == expected


# ── Duración de un ogg/opus ───────────────────────────────────────────────────

def test_ogg_seconds_reads_the_final_position():
    assert at.ogg_seconds(_ogg(12.5)) == 12.5
    assert at.ogg_seconds(_ogg(3.0) + _ogg(20.0)) == 20.0   # manda la última página


@pytest.mark.parametrize("data", [b"", b"OggS", _ogg(), _ogg(99999), b"RIFFWAVE" + b"0" * 30])
def test_ogg_seconds_is_none_when_it_cannot_be_read(data):
    assert at.ogg_seconds(data) is None   # sin posición, absurdo o no es ogg: no se inventa


# ── transcribe ────────────────────────────────────────────────────────────────

async def test_transcribe_sends_the_audio_inline_with_language_model_and_key():
    seen = {}

    def handler(request: httpx.Request):
        seen["key"] = request.headers["x-goog-api-key"]
        seen["auth"] = request.headers.get("authorization")
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return _ok("  quiero   un corte\nmañana  ")

    out = await _transcribe(handler)
    assert out is not None and out.text == "quiero un corte mañana"
    assert seen["key"] == KEY and seen["auth"] is None and seen["url"] == at.API_URL
    body = seen["body"]
    assert body["model"] == "m"
    assert body["input"] == [{"type": "audio", "data": base64.b64encode(OGG).decode(), "mime_type": "audio/ogg"}]
    assert body["generation_config"]["transcription_config"]["language_codes"] == at.LANGUAGE_CODES


async def test_the_text_can_come_in_output_text_and_the_input_echo_is_ignored():
    out = await _transcribe(lambda _: httpx.Response(200, json={"status": "completed", "output_text": "directo"}))
    assert out.text == "directo"
    echo = {"status": "completed", "steps": [
        {"type": "user_input", "content": [{"type": "text", "text": "NO debe salir"}]},
        {"type": "model_output", "content": [{"type": "text", "text": "sí"}, {"type": "audio"}]}]}
    assert (await _transcribe(lambda _: httpx.Response(200, json=echo))).text == "sí"


@pytest.mark.parametrize("response", [
    httpx.Response(400, json={"error": "bad"}), httpx.Response(403), httpx.Response(429), httpx.Response(500),
    httpx.Response(200, content=b"no es json"),
    httpx.Response(200, json=["no", "es", "un", "objeto"]),
    httpx.Response(200, json={"status": "failed", "steps": []}),
    httpx.Response(200, json={"status": "in_progress"}),
])
async def test_transcribe_returns_none_instead_of_raising(response):
    assert await _transcribe(lambda _: response) is None


async def test_transcribe_survives_network_failure():
    def boom(request):
        raise httpx.ConnectError("sin red")

    assert await _transcribe(boom) is None


async def test_transcribe_without_key_or_with_unsupported_format_never_calls_the_api():
    def never(_):
        raise AssertionError("no debía llamar a la API")

    assert await at.transcribe(OGG, api_key="", model="m", transport=httpx.MockTransport(never)) is None
    assert await _transcribe(never, data=b"#!AMR\n" + b"0" * 20) is None
    assert await _transcribe(never, data=b"") is None


async def test_transcribe_caps_the_text_the_agent_receives():
    out = await _transcribe(lambda _: _ok("hola " * 2000))
    assert out is not None and len(out.text) <= at.MAX_TEXT_CHARS


@pytest.mark.parametrize("response", [
    httpx.Response(200, json={"status": "completed", "steps": []}),
    httpx.Response(200, json={"status": "completed", "output_text": "   "}),
    _ok(""),
])
async def test_silence_is_returned_with_empty_text_because_it_was_still_billed(response):
    out = await _transcribe(lambda _: response)
    assert out is not None and out.text == "" and out.cost_usd > 0


# ── Consumo y costo estimado ──────────────────────────────────────────────────

async def test_usage_in_tokens_is_read_and_priced():
    usage = {"total_input_tokens": 750, "total_output_tokens": 90, "total_tokens": 840,
             "input_tokens_by_modality": [{"modality": "audio", "tokens": 750}]}
    out = await _transcribe(lambda _: _ok("hola", usage), data=_ogg(30.0))
    assert (out.input_tokens, out.output_tokens, out.seconds) == (750, 90, 30.0)
    assert out.cost_usd == pytest.approx((750 * at.USD_PER_M_IN + 90 * at.USD_PER_M_OUT) / 1e6)


async def test_the_duration_comes_from_the_ogg_and_is_none_for_other_formats():
    assert (await _transcribe(lambda _: _ok(), data=_ogg(12.5))).seconds == 12.5
    assert (await _transcribe(lambda _: _ok(), data=b"ID3" + b"0" * 30)).seconds is None


@pytest.mark.parametrize("usage", [None, "x", [], {"total_input_tokens": "mucho", "total_output_tokens": -4}])
async def test_without_usable_usage_the_cost_falls_back_to_the_duration_or_the_file_size(usage):
    out = await _transcribe(lambda _: _ok("hola", usage), data=_ogg(60.0))
    assert out.input_tokens == 0 and out.output_tokens == 0
    assert out.cost_usd == pytest.approx(at.USD_PER_MINUTE)  # 60 s medidos en el propio ogg
    mp3 = b"ID3" + b"0" * 3997
    out = await _transcribe(lambda _: _ok("hola", usage), data=mp3)
    assert out.seconds is None
    assert out.cost_usd == pytest.approx(len(mp3) / at.BYTES_PER_SECOND / 60 * at.USD_PER_MINUTE)


# ── Webhook de mensajes ───────────────────────────────────────────────────────

@pytest.fixture
def chat(monkeypatch):
    log = SimpleNamespace(replies=[], agent=[], saved=[], last_outbound=None, locked=0, usage=[],
                          download=OGG, download_error=None, transcript="quiero cita mañana",
                          key="g-test", no_answer=False)

    async def find_or_create(customer_phone, phone_number_id):
        return {"id": "conv-1", "workspace_id": "ws-1", "channel_id": "ch-1", "customer_id": "c-1"}

    async def save_message(**k):
        log.saved.append((k["direction"], k["content"], k.get("message_type", "text")))
        return {"id": "msg-1"}

    async def run(conversation, message):
        log.agent.append(message)

    async def reply(conversation, body):
        log.replies.append(body)

    async def last_outbound(conversation):
        return log.last_outbound

    async def download_media(self, media_id, phone_number_id, max_bytes):
        log.max_bytes = max_bytes
        if log.download_error:
            raise ProviderError(log.download_error)
        return log.download

    async def transcribe(data):
        if log.no_answer:  # la API falló: no hay nada que cobrar ni registrar
            return None
        return at.Transcription(text=log.transcript or "", size_bytes=len(data), seconds=12.0)

    async def record(workspace_id, t):
        log.usage.append((workspace_id, t.text, t.seconds))

    @asynccontextmanager
    async def lock(conversation_id):
        log.locked += 1
        yield

    monkeypatch.setattr(inbound.ConversationService, "find_or_create", find_or_create)
    monkeypatch.setattr(inbound.ConversationService, "save_message", save_message)
    monkeypatch.setattr(inbound.AgentService, "run", run)
    monkeypatch.setattr(inbound, "_reply", reply)
    monkeypatch.setattr(inbound, "_last_outbound", last_outbound)
    monkeypatch.setattr(inbound, "_conversation_lock", lock)
    monkeypatch.setattr(inbound.KapsoProvider, "download_media", download_media)
    monkeypatch.setattr(inbound.audio_transcription, "transcribe", transcribe)
    monkeypatch.setattr(inbound.audio_usage, "record", record)
    monkeypatch.setattr(inbound, "get_settings", lambda: SimpleNamespace(
        google_api_key=log.key, kapso_api_key="k", kapso_base_url="https://api.kapso.ai"))
    return log


def _audio(media_id="A1"):
    return {"phone_number_id": "PID", "message": {"from": "573001112233", "type": "audio", "audio": {"id": media_id}}}


async def test_audio_is_transcribed_and_goes_to_the_agent(chat):
    await inbound.handle_kapso_message(_audio())
    assert chat.agent == ["quiero cita mañana"] and chat.replies == []
    assert chat.saved == [("inbound", "🎤 quiero cita mañana", "audio")]  # el equipo ve lo que dijo
    assert chat.locked == 1  # el agente corre en fila, como con el texto
    assert chat.max_bytes == at.MAX_AUDIO_BYTES
    assert chat.usage == [("ws-1", "quiero cita mañana", 12.0)]  # el consumo queda registrado por negocio


async def test_silent_audio_gets_a_notice_never_reaches_the_agent_but_is_still_recorded_as_cost(chat):
    chat.transcript = ""
    await inbound.handle_kapso_message(_audio())
    assert chat.agent == [] and chat.replies == [inbound.AUDIO_UNREADABLE]
    assert chat.saved == [("inbound", "[audio]", "audio")]
    assert chat.usage == [("ws-1", "", 12.0)]  # Google lo cobró aunque no hubiera voz


async def test_when_the_api_fails_nothing_is_recorded(chat):
    chat.no_answer = True
    await inbound.handle_kapso_message(_audio())
    assert chat.agent == [] and chat.replies == [inbound.AUDIO_UNREADABLE] and chat.usage == []


async def test_oversize_audio_gets_its_own_notice(chat):
    chat.download_error = "too_large"
    await inbound.handle_kapso_message(_audio())
    assert chat.agent == [] and chat.replies == [inbound.AUDIO_TOO_LONG] and chat.usage == []


async def test_download_failure_asks_to_resend(chat):
    chat.download_error = "http_500"
    await inbound.handle_kapso_message(_audio())
    assert chat.agent == [] and chat.replies == [inbound.FILE_ERROR]


async def test_audio_without_media_id_asks_to_resend(chat):
    await inbound.handle_kapso_message(_audio(media_id=""))
    assert chat.agent == [] and chat.replies == [inbound.FILE_ERROR]


async def test_without_google_key_it_behaves_as_before(chat):
    chat.key = ""
    await inbound.handle_kapso_message(_audio())
    assert chat.agent == [] and chat.replies == [inbound.ONLY_TEXT]
    assert chat.saved == [("inbound", "[audio]", "audio")]


async def test_the_unreadable_notice_is_not_repeated_back_to_back(chat):
    chat.transcript = ""
    await inbound.handle_kapso_message(_audio("A1"))
    chat.last_outbound = inbound.AUDIO_UNREADABLE
    await inbound.handle_kapso_message(_audio("A2"))
    assert chat.replies == [inbound.AUDIO_UNREADABLE] and len(chat.saved) == 2


async def test_audio_sent_from_the_business_phone_is_labelled_and_never_transcribed(chat, monkeypatch):
    item = {"phone_number_id": "PID", "message": {
        "to": "573001112233", "id": "wamid.X", "type": "audio", "audio": {"id": "A9"},
        "kapso": {"origin": "business_app"}}}

    async def not_duplicate(workspace_id, wamid):
        return False

    monkeypatch.setattr(inbound.ConversationService, "message_exists", staticmethod(not_duplicate))
    await inbound.handle_kapso_message(item)
    assert chat.saved == [("outbound", "[audio]", "audio")] and chat.agent == []
