-- 012: calendar_id en appointments pasa a nullable.
-- Las citas manuales pueden crearse sin Google Calendar conectado.
ALTER TABLE appointments ALTER COLUMN calendar_id DROP NOT NULL;
