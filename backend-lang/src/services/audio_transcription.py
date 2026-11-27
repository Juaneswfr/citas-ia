"""Transcripción de audios (notas de voz) que los clientes mandan por WhatsApp.

Usa Gemini 3.5 Transcribe (`gemini-3.5-transcribe`) por la Interactions API de Google (`POST /v1beta/interactions`),
con httpx y sin SDK, y la misma `GOOGLE_API_KEY` que ya usa el agente. Claude no transcribe audio.
Lo transcrito lo dijo un cliente: es un DATO sin confianza que entra al agente igual que un mensaje de
texto (con su alcance y sus herramientas cerradas al negocio), nunca como instrucciones.

Nunca lanza: si falta la clave, el formato no sirve o la API falla, devuelve None y quien llama avisa
al cliente. No se registra el contenido transcrito, solo el tipo de error.

Costo: cada `Transcription` trae el consumo que informó Google (tokens) y una ESTIMACIÓN en dólares (`cost_usd`).
Las tarifas están en un solo lugar (`USD_*`) para corregirlas cuando Google las cambie; lo que de verdad se
factura se ve en el panel de Google AI Studio.
"""
import base64
import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from core.config import get_settings

log = logging.getLogger(__name__)

API_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
TIMEOUT_S = 30
# Una nota de voz de WhatsApp en opus pesa ~100-300 KB; 5 MB cubre varios minutos y acota el costo.
# (Google admite hasta 20 MB por petición con el audio dentro; no hace falta subir el archivo aparte.)
MAX_AUDIO_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARS = 2000  # lo mismo que se le permite al agente leer de un mensaje (MAX_MSG_CHARS = 1500 + margen)
# Español de Latinoamérica (código BCP-47 que lista Google). Vacío = detectar solo, pero un audio con ruido
# se transcribe mejor si ya se sabe el idioma.
LANGUAGE_CODES = ["es-419"]

# Tarifas de gemini-3.5-transcribe según la página de precios de Google (nivel de pago, por millón de tokens).
# Confirmarlas ahí: son lo único que decide el costo que se muestra en Zumit Manager.
USD_PER_M_IN = 2.00         # audio de entrada (Google lo estima en ~0,003 USD/min)
USD_PER_M_OUT = 12.00       # texto de salida (~0,002 USD/min)
USD_PER_MINUTE = 0.005      # cuando Google no informó los tokens (suma de las dos estimaciones por minuto)
BYTES_PER_SECOND = 2000     # nota de voz de WhatsApp (opus ~16 kbps): solo si no hay tokens ni duración


@dataclass(frozen=True)
class Transcription:
    """Texto del audio y lo que costó. `text` puede venir vacío (silencio): también se cobró."""
    text: str
    size_bytes: int = 0
    seconds: Optional[float] = None
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def cost_usd(self) -> float:
        """Estimación en dólares: tokens si Google los informó, si no la duración, si no el peso del archivo."""
        if self.input_tokens or self.output_tokens:
            return (self.input_tokens * USD_PER_M_IN + self.output_tokens * USD_PER_M_OUT) / 1e6
        seconds = self.seconds if self.seconds is not None else self.size_bytes / BYTES_PER_SECOND
        return seconds / 60 * USD_PER_MINUTE


def _num(value) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0 else 0.0


def ogg_seconds(data: bytes) -> Optional[float]:
    """Duración de un ogg/opus (nota de voz de WhatsApp) leyendo la posición final de la última página.

    Opus cuenta a 48 kHz. None si no se puede leer: no se inventa. Se ignora el «pre-skip» (unos 6 ms).
    """
    i = data.rfind(b"OggS")
    if i < 0 or len(data) < i + 14:
        return None
    granule = int.from_bytes(data[i + 6:i + 14], "little", signed=True)
    if granule <= 0 or granule > 3600 * 48000:  # -1 = página sin posición; más de una hora no es una nota de voz
        return None
    return round(granule / 48000, 2)


def _text_of(body: dict) -> str:
    """Texto de la respuesta: `output_text` si viene, si no el texto de los pasos de salida del modelo."""
    out = body.get("output_text")
    if isinstance(out, str):
        return out
    parts = []
    for step in body.get("steps") or []:
        if not isinstance(step, dict) or step.get("type") == "user_input":
            continue
        for part in step.get("content") or []:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
    return " ".join(parts)


def _parse(body, size_bytes: int, seconds: Optional[float]) -> Optional[Transcription]:
    if not isinstance(body, dict) or body.get("status") not in (None, "completed"):
        return None
    usage = body.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    text = " ".join(_text_of(body).split())[:MAX_TEXT_CHARS]
    return Transcription(
        text=text, size_bytes=size_bytes, seconds=seconds,
        input_tokens=int(_num(usage.get("total_input_tokens"))),
        output_tokens=int(_num(usage.get("total_output_tokens"))),
    )


def detect_audio(data: bytes) -> Optional[str]:
    """Tipo MIME del audio según la firma del archivo, o None si Google no lo admite.

    Las notas de voz llegan en ogg/opus; también se admiten mp3, aac, m4a, wav y webm. AMR (que WhatsApp
    también permite) no lo acepta la API: se avisa al cliente.
    """
    if data[:4] == b"OggS":
        return "audio/ogg"
    if data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio/mpeg"
    if len(data) > 1 and data[0] == 0xFF and data[1] & 0xF6 == 0xF0:  # cabecera ADTS: AAC crudo
        return "audio/aac"
    if data[4:8] == b"ftyp":
        return "audio/m4a"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "audio/wav"
    if data[:4] == b"\x1aE\xdf\xa3":
        return "audio/webm"
    return None


async def transcribe(
    data: bytes, *, api_key: Optional[str] = None, model: Optional[str] = None,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> Optional[Transcription]:
    """Transcripción del audio, o None si no se pudo (sin clave, formato no admitido, error de la API).

    Un audio sin voz (silencio, ruido) devuelve una Transcription con `text=""`: la API respondió y se cobró.
    """
    if api_key is None or model is None:
        settings = get_settings()
        api_key = settings.google_api_key if api_key is None else api_key
        model = settings.transcribe_model if model is None else model
    if not api_key or not data:
        return None
    mime = detect_audio(data)
    if mime is None:
        log.warning("[audio] formato no admitido | bytes=%d", len(data))
        return None
    payload = {
        "model": model,
        "input": [{"type": "audio", "data": base64.b64encode(data).decode("ascii"), "mime_type": mime}],
        "generation_config": {"transcription_config": {"language_codes": LANGUAGE_CODES}},
    }
    try:
        async with httpx.AsyncClient(transport=transport, timeout=TIMEOUT_S) as client:
            resp = await client.post(API_URL, headers={"x-goog-api-key": api_key}, json=payload)
        if resp.status_code >= 400:
            # 400/403/429 suelen ser de la cuenta (clave mala, sin cupo, tope): conviene verlos en el log.
            log.error("[audio] la API rechazó el audio | http=%s | bytes=%d", resp.status_code, len(data))
            return None
        result = _parse(resp.json(), len(data), ogg_seconds(data) if mime == "audio/ogg" else None)
    except (httpx.HTTPError, ValueError, AttributeError) as e:
        log.error("[audio] no se pudo transcribir | err=%s", type(e).__name__)
        return None
    if result is None:
        log.error("[audio] respuesta sin completar o con otra forma | bytes=%d", len(data))
        return None
    log.info("[audio] transcrito | bytes=%d | chars=%d | usd~%.5f", len(data), len(result.text), result.cost_usd)
    return result
