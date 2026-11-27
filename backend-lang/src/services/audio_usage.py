"""Consumo de la transcripción de audios por negocio y día (`audio_usage`, migración 028).

Se suma al costo de IA en Zumit Manager › Costos. Falla «abierto»: si la tabla aún no existe o la BD falla, el
audio se atiende igual y solo se deja una línea en el log. Nunca debe tumbar la respuesta al cliente.
"""
import logging

from sqlalchemy import text

from core.database import AsyncSessionLocal
from services.audio_transcription import Transcription

log = logging.getLogger(__name__)


async def record(workspace_id: str, t: Transcription) -> None:
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(
                text("""
                    INSERT INTO audio_usage (workspace_id, day, audios, seconds, input_tokens, output_tokens, cost_usd)
                    VALUES (:w, (NOW() AT TIME ZONE 'America/Bogota')::date, 1, :s, :i, :o, :c)
                    ON CONFLICT (workspace_id, day) DO UPDATE SET
                        audios = audio_usage.audios + 1,
                        seconds = CASE WHEN audio_usage.seconds IS NULL AND EXCLUDED.seconds IS NULL THEN NULL
                                       ELSE COALESCE(audio_usage.seconds, 0) + COALESCE(EXCLUDED.seconds, 0) END,
                        input_tokens = audio_usage.input_tokens + EXCLUDED.input_tokens,
                        output_tokens = audio_usage.output_tokens + EXCLUDED.output_tokens,
                        cost_usd = audio_usage.cost_usd + EXCLUDED.cost_usd
                """),
                {"w": workspace_id, "s": t.seconds, "i": t.input_tokens, "o": t.output_tokens, "c": round(t.cost_usd, 6)},
            )
            await db.commit()
    except Exception as e:
        log.warning("[audio] no se guardó el consumo | workspace=%s | err=%s", workspace_id, type(e).__name__)
