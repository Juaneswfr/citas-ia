-- 011: channel_id en appointments pasa a nullable.
-- Las citas manuales pueden crearse sin canal de WhatsApp.
ALTER TABLE appointments ALTER COLUMN channel_id DROP NOT NULL;
