-- Inicio de sesión con Google: la cuenta se reconoce por el `sub` de Google, no por la contraseña.
-- Una cuenta creada con Google no tiene contraseña. Todo es idempotente.
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT;
ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS google_sub TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS users_google_sub_key ON users (google_sub) WHERE google_sub IS NOT NULL;
