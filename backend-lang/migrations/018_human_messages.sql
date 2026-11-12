-- 018: Mensajes escritos por una persona del negocio (sender_type = 'human'): lo que responde
-- desde el chat de Hilo o desde la app de WhatsApp Business cuando el número está en coexistencia.
-- sent_via dice por dónde salió ('hilo' | 'business_app') para mostrarlo en el chat.
-- El índice sirve para no guardar dos veces el mismo mensaje cuando Kapso avisa de un envío.
-- (El runner envía cada trozo entre ';' a la BD: no dejar comentarios sueltos al final del archivo.)

ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_sender_type_check;

ALTER TABLE messages ADD CONSTRAINT messages_sender_type_check
    CHECK (sender_type IN ('customer','agent','system','human'));

ALTER TABLE messages ADD COLUMN IF NOT EXISTS sent_via TEXT
    CHECK (sent_via IS NULL OR sent_via IN ('hilo','business_app'));

CREATE INDEX IF NOT EXISTS idx_messages_provider_message_id
    ON messages (workspace_id, provider_message_id) WHERE provider_message_id IS NOT NULL;
