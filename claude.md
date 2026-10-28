# Implementación y decisiones de diseño

Citas-IA: backend FastAPI + LangGraph en backend-lang, front TanStack Start en front, datos en Supabase/PostgreSQL.

- Decisión (FR-105): front/drizzle.config.ts lee solo DATABASE_URL y falla si falta; no hay credencial por defecto.
- Pendiente (pregunta abierta 8): rotar la credencial que sigue en el historial git.
- Decisión (T001, D-U1): roles y rate_limits van en `backend-lang/migrations/007_roles_rate_limits.sql`; el 006 queda reservado para `006_convergencia_remota.sql` (otra tarea).
- Decisión (T001): todo cambio de CHECK con datos va en una transacción en orden DROP → UPDATE → ADD; el UPDATE primero viola el CHECK vigente. El CHECK de `member_role` se localiza por catálogo (`pg_constraint`) porque su nombre puede variar en la remota.
- Decisión (T001, D15): `rate_limits` tiene RLS activo SIN políticas y sin FORCE. El backend se conecta como propietario y no queda sujeto a RLS; los demás roles quedan denegados. No se usan políticas con el esquema auth de Supabase porque la remota no lo tiene.
- Pendiente (T001): aplicar 006 y 007 en la remota con backup previo (`pg_dump`) y gate de verificación de catálogo; no lo hizo esta tarea.
