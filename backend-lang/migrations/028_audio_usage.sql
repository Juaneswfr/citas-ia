-- Consumo de la transcripción de audios (Gemini) por negocio y día: sirve para sumarlo al costo de IA en Zumit Manager.
-- cost_usd es una ESTIMACIÓN (tokens o segundos × tarifa de audio_transcription.py), no lo que factura Google.
-- seconds acepta NULL a propósito: la duración solo se conoce en notas de voz ogg/opus; en otros formatos no se inventa.
CREATE TABLE IF NOT EXISTS audio_usage (
    workspace_id  UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    day           DATE NOT NULL,
    audios        INTEGER NOT NULL DEFAULT 0,
    seconds       NUMERIC(12,2),
    input_tokens  BIGINT NOT NULL DEFAULT 0,
    output_tokens BIGINT NOT NULL DEFAULT 0,
    cost_usd      NUMERIC(12,6) NOT NULL DEFAULT 0,
    PRIMARY KEY (workspace_id, day)
)
