-- 009: Toggle de agente por cliente
-- Permite deshabilitar el bot para un cliente específico sin afectar al resto.
ALTER TABLE customers ADD COLUMN IF NOT EXISTS agent_enabled BOOLEAN NOT NULL DEFAULT TRUE;
