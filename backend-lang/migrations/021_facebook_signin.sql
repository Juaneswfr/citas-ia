-- Inicio de sesión con Facebook: la cuenta se reconoce por el `id` de Facebook, no por la contraseña.
-- Una cuenta creada con Facebook no tiene contraseña (020 ya hizo password_hash opcional). Todo es idempotente.
ALTER TABLE users ADD COLUMN IF NOT EXISTS facebook_sub TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS users_facebook_sub_key ON users (facebook_sub) WHERE facebook_sub IS NOT NULL;
