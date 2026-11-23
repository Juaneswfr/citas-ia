-- Costo de IA de cada ejecución del agente: sirve para saber cuánto costó cada cita (la suma de las ejecuciones de su conversación).
-- Las columnas aceptan NULL a propósito: las ejecuciones anteriores a esta migración quedan «sin medir», no en cero.
-- Tokens de entrada que contó el agente en la ejecución
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS input_tokens INTEGER;

-- Tokens de salida que contó el agente en la ejecución
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS output_tokens INTEGER;

-- Llamadas al modelo dentro de la ejecución (con herramientas son varias)
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS llm_calls INTEGER;

-- Costo estimado por tokens (tarifa de Haiku de billing_service.py)
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS cost_usd NUMERIC(12,6);

-- Costo real de LangSmith para esta ejecución (la sincronización horaria lo llena)
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS ls_cost_usd NUMERIC(12,6);

-- Tokens según LangSmith
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS ls_tokens BIGINT;

-- Para sumar las ejecuciones de una conversación hasta el momento de la cita
CREATE INDEX IF NOT EXISTS idx_agent_runs_conv_started ON agent_runs(conversation_id, started_at)
