# Implementación y decisiones de diseño

Citas-IA: backend FastAPI + LangGraph en backend-lang, front TanStack Start en front, datos en Supabase/PostgreSQL.

- Decisión (FR-105): front/drizzle.config.ts lee solo DATABASE_URL y falla si falta; no hay credencial por defecto.
- Pendiente (pregunta abierta 8): rotar la credencial que sigue en el historial git.

## Estado de esquema remoto (auditoría t_843e8992, 2026-10-28)
- La remota `hilo` tiene 19 tablas (18 canónicas + `alembic_version`), no 13 como decía CLAUDE.md; el canon 001..005 suma 19. RLS activo en 15 tablas pero **0 políticas**.
- Diferencias vs canon: falta `kapso_webhook_events`, CHECK `kapso_customers_setup_status_check`, índices `channels_phone_number_id_uq`/`channels_webhook_token_uq`, UNIQUE `kapso_customer_id`; PK de `kapso_customers` es `id` (canon: `workspace_id`); defaults distintos (`id` gen_random_uuid vs uuid_generate_v4, `channels.connection_type`, `kapso_customers.setup_status`).
- Deuda Alembic documentada presente (5 columnas). `rate_limits`, `auth_tokens`, `oauth_states` no existen (pendientes de tareas).
- Gate T001: parada; 006 no aplicada. El diseño de 006 debe cubrir la lista anterior (incl. PK de kapso_customers y `alembic_version`).
