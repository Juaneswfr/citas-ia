

27-10-2026
  Backend Python:
  - supabase==2.10.0 + postgrest → asyncpg==0.29.0
  - core/database.py nuevo — pool asyncpg con codecs UUID/JSONB
  - core/config.py — DATABASE_URL reemplaza las 3 vars de Supabase
  - api/main.py — pool se inicializa/cierra en lifespan
  - Todos los routes (auth, services, workspaces, appointments, channels, billing, conversations) — Supabase queries → asyncpg
   directo
  - Todos los services (audit, conversation, agent, calendar) + reminder_worker — mismo cambio
  - supabase_client.py eliminado

  Frontend:
  - @supabase/supabase-js desinstalado, drizzle-orm + pg + jose instalados
  - drizzle.config.ts + src/db/schema.ts (13 tablas) + src/db/client.ts nuevos
  - auth-context.tsx — JWT en localStorage, sin Supabase auth
  - _authenticated.tsx — verifica JWT localStorage en lugar de supabase.auth.getSession()
  - auth-middleware.ts — jwtVerify con jose, sin Supabase
  - auth-attacher.ts — lee de localStorage
  - auth/callback.tsx — redirige a /login (OAuth eliminado)
  - verify-email.tsx — sin Supabase
  - .env actualizado

  No migré / riesgos:
  - Las 13 tablas aún no existen en el nuevo Postgres — necesitas npx drizzle-kit migrate para crearlas
  - Los datos de Supabase aún no migraron — necesitas un pg_dump desde Supabase y un psql import al nuevo Postgres
  - Usuarios existentes no tienen password_hash — deberán resetear contraseña tras la migración
  - La columna reminder_24h_sent/reminder_2h_sent en appointments puede no existir en Supabase — verifica antes de migrar
  datos