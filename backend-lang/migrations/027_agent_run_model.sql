-- Modelo con el que respondió cada ejecución del agente (Haiku, Gemini…): sirve para ver el costo por modelo y por cliente.
-- Acepta NULL a propósito: las ejecuciones anteriores quedan «sin modelo registrado», no se inventa.
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS model VARCHAR(80)
