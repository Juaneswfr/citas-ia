-- Estado visible de cada conversación: quién tiene la pelota. Sin esta migración todo sigue igual (el guardado del estado falla en silencio).
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS state VARCHAR(20);
ALTER TABLE conversations DROP CONSTRAINT IF EXISTS conversations_state_check;
ALTER TABLE conversations ADD CONSTRAINT conversations_state_check CHECK (state IS NULL OR state IN ('awaiting_agent','awaiting_customer','booked','needs_human'));
CREATE INDEX IF NOT EXISTS idx_conversations_state_last ON conversations(state, last_message_at)
