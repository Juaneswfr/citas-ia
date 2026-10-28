# Implementación y decisiones de diseño

Citas-IA: backend FastAPI + LangGraph en backend-lang, front TanStack Start en front, datos en Supabase/PostgreSQL.

- Decisión (FR-105): front/drizzle.config.ts lee solo DATABASE_URL y falla si falta; no hay credencial por defecto.
- Pendiente (pregunta abierta 8): rotar la credencial que sigue en el historial git.

<!-- integrado desde feat/003-t001 (T001) -->
# Implementación y decisiones de diseño

CitasIA / Hilo: SaaS multi-tenant de citas por WhatsApp. Backend FastAPI + LangGraph en `backend-lang/`; esquema canónico en
`backend-lang/migrations/` (plan D14), aplicado en orden 001..N. Front en `front/`.

## T001 — Convergencia remota (006) y roles/rate_limits (007)

### Decisiones
- **Convergencia (D-U1 opción a):** la BD remota (creada por Alembic) no se reconstruye ni se borran datos. `006` agrega lo que falta
  frente a 001..005 y es idempotente (aplicada dos veces en efímero: exit 0; en una BD creada desde 001..005 no cambia nada).
  Contenido: `kapso_webhook_events` (003 exacta), CHECK `kapso_customers_setup_status_check`, UNIQUE(kapso_customer_id) solo si no
  existe (DO block), índices únicos `channels_phone_number_id_uq` y `channels_webhook_token_uq`, defaults como 004.
- **Sin RLS (D-U6):** 006 y 007 no crean ni borran políticas ni habilitan RLS (`grep POLICY|ROW LEVEL` = 0). `rate_limits` sin RLS.
  Riesgo aceptado: el aislamiento entre workspaces depende solo de la aplicación (JWT, require_workspace_access).
- **PK surrogate de kapso_customers (D-U5):** se conserva PK(id) + UNIQUE(workspace_id) en la remota; no se migra a PK(workspace_id).
- **idx_channels_phone_number_id** (parcial, no único, de Alembic): se conserva; la unicidad la cubre `channels_phone_number_id_uq`.
- **Defaults:** `channels.connection_type` sin default (antes 'coexistence' en remota) y `kapso_customers.setup_status` 'none'
  (antes 'pending'). Los INSERT de `api/routes/channels.py` no fijan connection_type: en la remota guardarán NULL, como el canónico.
- **member_role (007):** orden obligatorio DROP del CHECK (buscado por catálogo) → UPDATE owner→workspace_owner → ADD del CHECK nuevo.
  El DOWN (comentado al final de 007) hace lo inverso y borra rate_limits; probado en efímero (DOWN + re-UP exit 0).
- **rate_limits (D15):** PK (key, window_start), índice por window_start. `hits` DEFAULT 0: el upsert
  `INSERT (key, window_start) ... ON CONFLICT DO UPDATE SET hits = hits + 1` devuelve 0 y luego 1; para contar desde 1 hay que
  insertar `hits = 1` en VALUES (lo debe tener en cuenta T004).

### Deudas aceptadas (no se tocan en T001)
- Columnas extra de Alembic: appointments.reminder_sent, reminder_1h_sent, reminder_24h_sent, users.password_hash, kapso_customers.id.
- `gen_random_uuid()` en la remota vs `uuid_generate_v4()` en el canónico: equivalentes (la remota no tiene uuid-ossp).
- Tabla `alembic_version` (b1a2c3d4e5f6): no se actualiza; las migraciones SQL directas no la usan.
- PK surrogate de kapso_customers (D-U5).
- Las 11 políticas `*_select` de 001 no existen en la remota (sin esquema `auth`); fuera del gate por D-U6.

### Estado del gate (2026-10-28 18:38 UTC)
- Efímero limpio PG 17.10, 001..005 + 006 + 006 + 007: criterios 12/12, PASS. Tests de migraciones: 5 passed.
- Copia fiel (pg_dump 17.11 de la remota restaurado sin stubs) + 006 + 007 en una transacción: PASS; solo diferencias permitidas.
- **Remota (PG 17.11): aplicada** en una transacción (006 + 007, COMMIT) y verificada por catálogo en solo lectura: PASS, catálogo
  idéntico a la copia ensayada. Backup previo: `scratch/t001/remote_backup_20261028T183712Z.dump` (sha256 51368880…910b).
- T002 hecha (security): los guards de workspaces.py, services.py y billing.py usan `workspace_owner`; suite backend-lang 83 passed, 5 skipped.
- Pendiente inmediato: T003/T004 (security.py / lógica de `require_workspace_access`).

## T004 — is_active, CORS explícito y rate limit de login
- **is_active (FR-005):** el guard de `PATCH /workspaces/{id}` sigue siendo `manager` (matriz fila 6); si el body trae `is_active` (no None) el handler exige `super_admin` o `member_role == workspace_owner` (fila 7), si no 403 con el texto de `_insufficient`. 404 sin cambios.
- **CORS (FR-009):** `CORS_ALLOWED_ORIGINS` coma-separada → `Settings.cors_allowed_origins`; default solo `FRONTEND_URL`. `*` o entrada vacía → falla al cargar Settings (mensaje nombra la variable). `allow_credentials=True`; métodos y cabeceras explícitos (Authorization, Content-Type, X-XSRF-TOKEN, X-Correlation-ID); si el front usa otra cabecera personalizada hay que añadirla. `main.py` lee `get_settings()` al importarse.
- **Rate limit (FR-008, D15):** `rate_limit_hit` (ventana fija, upsert con `hits = 1` en VALUES → cuenta desde 1; ver nota de T001) sobre `rate_limits`, sin migraciones ni RLS. `enforce_login_rate_limit`: bloqueo previo (`login:block:{ip}`, ventana 900 s, solo lectura) → cuenta `login:min:{ip}` (60 s); el 11.º intento registra el bloqueo y responde 429 + Retry-After. Se ejecuta antes de consultar usuario/bcrypt; cada intento cuenta. Cualquier fallo de BD → 503 (fail-closed). El Retry-After del bloqueo se calcula hasta el fin de la ventana fija de 900 s (puede ser menor a 15 min: límite de ventana fija).
- **Limpieza:** `rate_limit_purge(older_than_seconds)` la llama `_reminder_loop` cada 30 min con 24 h; nunca el request de login.
- **trust_proxy_headers:** `nginx/nginx.conf` setea `X-Real-IP $remote_addr` y es el único ingress en docker-compose (backend sin puerto publicado), así que `TRUST_PROXY_HEADERS=true` es seguro en ese despliegue. Default False: sin proxy confiable un cliente podría falsificar X-Real-IP y evadir el límite. Nunca se lee X-Forwarded-For.
- **Fixtures:** ningún test existente hacía login por la ruta, así que no se adaptó ninguna fixture ni se tocó ninguna aserción. Único cambio de infraestructura de tests: `pythonpath = ["src"]` en pyproject (pytest del venv principal importaba el `src` del repo principal).
- **Pendientes:** rate limit de `/auth/register` (T010/T012, reutiliza `rate_limit_hit`); rate limit de webhooks (T034); tests de matriz y rate limit end-to-end (T006); aplicar `TRUST_PROXY_HEADERS=true` y `CORS_ALLOWED_ORIGINS` en el .env de producción.
