# Tasks: Producto final de citas por WhatsApp

**Feature**: `003-producto-final-citas` | **Branch**: master | **Fecha**: 2026-10-28
**Input**: [plan.md](./plan.md), [spec.md](./spec.md) y los 5 insumos de esta carpeta.

**Leyenda**: `[P]` = puede correr en paralelo con otras tareas cuyas dependencias ya estén cumplidas y no comparta archivos con ellas. `(nuevo)` = archivo a crear; su carpeta existe en `f0e97b0`. `(solo ejecución)` / `(solo lectura)` = el reviewer lo ejecuta o lo lee, no lo edita. Orden de capas por historia: dba → security → backend → frontend → reviewer (excepciones en plan.md). Esquema canónico: `backend-lang/migrations/` (plan D14); ninguna tarea edita `front/drizzle/` ni `front/src/db/schema.ts` (T005 edita solo `front/drizzle.config.ts`, por seguridad). Los tests los crea la última tarea backend/security de cada historia; el reviewer no crea código ni tests. El detalle técnico de cada tarea está en `plan.md` (decisiones D1–D17) y en los FR que cubre (tabla final). Decisiones del usuario del 2026-10-28 (D-U1…D-U4, spec): T001 hace la convergencia remota antes de roles/rate_limits (migraciones renumeradas 006…015); el arnés de estrés está autorizado (T036, T037, T043, T050); T005 está cumplida en `94f8e44`. Ninguna tarea queda marcada `[B]` por estas decisiones; siguen bloqueadas solo las partes que dependen de las preguntas abiertas 4, 9 y 10.

---

## Fase 1 — Seguridad y esquema

## T001 — Convergencia remota (006) + roles y rate_limits (007): CHECK de member_role con workspace_owner y tabla rate_limits
- **Agente:** dba
- **Depende de:** —
- **Paralelo:** No
- **Historia:** US-001
- **Archivos:** backend-lang/migrations/006_convergencia_remota.sql (nuevo), backend-lang/migrations/007_roles_rate_limits.sql (nuevo), backend-lang/migrations/001_initial_schema.sql (solo lectura), backend-lang/migrations/003_kapso_webhook_events.sql (solo lectura), backend-lang/migrations/004_kapso_onboarding.sql (solo lectura), backend-lang/migrations/005_kapso_number_webhooks.sql (solo lectura)
- **Instrucción (D-U5, D-U6):** no crear políticas RLS; no migrar kapso_customers a PK(workspace_id); la clave surrogate se acepta (D-U5).
- **Alcance (decisión D-U1 de la spec, opción a: convergencia, sin reconstruir ni borrar datos):** (1) **`006_convergencia_remota.sql`**, idempotente (`CREATE TABLE/INDEX IF NOT EXISTS`, `DROP CONSTRAINT IF EXISTS` + `ADD CONSTRAINT`), agrega a la BD remota lo que le falta frente a 001..005 según el reporte del gate R1: tabla `kapso_webhook_events` (003), constraint `kapso_customers_setup_status_check` (004), índices únicos `channels_phone_number_id_uq` y `channels_webhook_token_uq` (004/005) y defaults alineados con 001..005. Sin políticas ni habilitación de RLS (D-U6: la remota es PostgreSQL 17 sin esquema `auth` y el sistema usa JWT propio; el aislamiento lo hace la aplicación). La clave surrogate `kapso_customers.id` se acepta como equivalente a la canónica y no se migra a PK(`workspace_id`) (D-U5, deuda conocida). **No borra** las columnas extra de Alembic (`appointments.reminder_sent`, `reminder_1h_sent`, `reminder_24h_sent`, `users.password_hash`, `kapso_customers.id`): quedan como deuda documentada (spec, D-U1). (2) **`007_roles_rate_limits.sql`**: en una sola transacción y en este orden obligatorio, `DROP CONSTRAINT IF EXISTS` del CHECK de `member_role` → `UPDATE workspace_members SET member_role='workspace_owner' WHERE member_role='owner'` → `ADD CONSTRAINT … CHECK (member_role IN ('workspace_owner','manager','staff','viewer'))` (el orden UPDATE primero falla contra el CHECK actual). Crear `rate_limits(key, window_start, hits)` (plan D15). (3) **Secuencia obligatoria de aplicación**: (a) validar en un PostgreSQL efímero 001..005 + 006 + 007, y además aplicar 006 dos veces para probar la idempotencia; (b) backup lógico previo de la remota (`pg_dump`, sin imprimir la cadena de conexión) y aplicación de 006 y 007 en transacción; (c) `auth_tokens` (T009) y `oauth_states` (T023) se crean en sus tareas. **Gate de verificación de T001 (condición de parada):** tras aplicar, una consulta de catálogo (`information_schema`, `pg_constraint`, `pg_indexes`) confirma en la remota la tabla `kapso_webhook_events`, el CHECK `kapso_customers_setup_status_check`, los índices únicos `channels_phone_number_id_uq` y `channels_webhook_token_uq`, los defaults, el CHECK nuevo de `member_role` con `workspace_owner` (aplicado en orden DROP→UPDATE→ADD) con 0 filas `owner`, y la tabla `rate_limits`. El gate **no** exige RLS ni políticas en ninguna tabla (D-U6) ni la PK(`workspace_id`) de `kapso_customers` (D-U5). Cualquier diferencia restante distinta de las columnas extra de Alembic y de la clave surrogate de `kapso_customers` → no se cierra T001 y no arrancan T002–T004/T009; se revierte (`ROLLBACK` o restauración del backup) y se reporta. Tablas que solo existen en el esquema canónico y faltan en drizzle (confirman D14, no se tocan aquí): `agent_runs`, `tool_calls`, `agent_alerts` (se migra en T039), `kapso_webhook_events`, `kapso_customers`. Tablas que faltan en el esquema canónico y crean otras tareas: `auth_tokens` (T009), `oauth_states` (T023).

## T002 — Reemplazar el rol "owner" por workspace_owner en 4 guards
- **Agente:** security
- **Depende de:** T001 (gate de convergencia aprobado)
- **Paralelo:** Sí [P]
- **Historia:** US-001
- **Archivos:** backend-lang/src/api/routes/workspaces.py, backend-lang/src/api/routes/services.py, backend-lang/src/api/routes/billing.py

## T003 — JWT con member_role, login determinista, 403 sin membresías y refresh/membresía contra BD (fail-closed 503)
- **Agente:** security
- **Depende de:** T001 (gate de convergencia aprobado)
- **Paralelo:** Sí [P]
- **Historia:** US-001
- **Archivos:** backend-lang/src/core/security.py, backend-lang/src/api/routes/auth.py
- **Alcance:** incluye FR-007 completo: membresía activa más antigua y, si `users.role` es nulo (o no es `super_admin`) y no hay membresías activas, 403 "tu cuenta no tiene negocio asignado" sin emitir token (se quita el respaldo `"viewer"` de `auth.py:125`). FR-004/FR-108: si la BD falla al validar la membresía o en `POST /auth/refresh`, responde 503 (nunca 401), para que el front distinga "sesión inválida" de "BD caída"; `workspace_id` inexistente → 404 para `super_admin`, 403 para el resto.

## T004 — is_active solo owner, CORS explícito y rate limit de login sobre rate_limits
- **Agente:** security
- **Depende de:** T002, T003 (y, por ellas, T001 con el gate de convergencia aprobado: usa `rate_limits` de `007_roles_rate_limits.sql`)
- **Paralelo:** No
- **Historia:** US-001
- **Archivos:** backend-lang/src/api/routes/workspaces.py, backend-lang/src/schemas/workspace.py, backend-lang/src/api/main.py, backend-lang/src/api/routes/auth.py, backend-lang/src/core/security.py

## T005 — Quitar la credencial por defecto de front/drizzle.config.ts (solo DATABASE_URL, falla si falta)
- **Agente:** security
- **Depende de:** —
- **Paralelo:** Sí [P]
- **Historia:** US-001
- **Archivos:** front/drizzle.config.ts
- **Estado:** **cumplida** en el commit `94f8e44` de `master` (decisión D-U4 de la spec). Queda pendiente solo la revisión de T008, que lee el archivo en ese commit; el `git grep` del alcance se anota allí si no quedó registrado.
- **Alcance:** FR-105. El archivo está versionado en `f0e97b0` y trae como respaldo una URL de PostgreSQL con usuario y contraseña (`***`; no se copia en ningún documento, log ni commit). Leer solo `process.env.DATABASE_URL` y lanzar un error explícito si falta. Comprobar con `git grep` que ningún otro archivo versionado trae URLs de BD con credenciales y anotar el resultado (sin valores). La rotación de la credencial no es parte de esta tarea (pregunta abierta 8 de la spec; la clave de Kapso ya la rotó el usuario y el historial no se reescribe, D-U3).

## T006 — Equipo (listar, invitar, remover), POST /workspaces/ con membresía y tests de roles, login sin membresía y rate limit
- **Agente:** backend
- **Depende de:** T004
- **Paralelo:** No
- **Historia:** US-001
- **Archivos:** backend-lang/src/api/routes/workspaces.py, backend-lang/src/schemas/workspace.py, backend-lang/src/services/email_service.py, backend-lang/tests/test_roles_matrix.py (nuevo), backend-lang/tests/test_auth_rate_limit.py (nuevo), backend-lang/tests/test_channels_roles.py
- **Alcance:** `test_roles_matrix.py` implementa, fila a fila y para los 5 roles, la "Matriz objetivo rol × endpoint" de la spec (fuente de verdad de SC-001; no `arbol-rutas.md` §3), en esta tarea solo las filas de endpoints existentes (las "nuevo" las añade T061), con las reglas comunes de 401 sin JWT y 403 con workspace ajeno. Incluye el caso de FR-007 "`users.role` nulo y sin membresías → login 403 sin token" y el de varias membresías (elección determinista). También el caso `GET /billing/workspaces/{id}/subscription` → 2xx con el workspace en `trial` (FR-092, H1); como el CHECK con `trial` llega en T009 y la consulta ampliada en T057, ese caso se crea marcado `xfail(strict=True)` con motivo "T009/T057" y T058 quita la marca. El caso 2xx con suscripción `active` (US-001 escenario 1) no lleva marca. `DELETE /workspaces/{id}/members/{uid}` sobre el último `workspace_owner` → 409 sin borrar la membresía (FR-010); el endpoint lo implementa aquí y `test_roles_matrix.py` lo cubre junto a la fila 10. US-001(b) / FR-004: `workspace_id` inexistente (UUID válido sin fila) en `GET /workspaces/{id}` → 404 con `super_admin` y 403 con `workspace_owner` de otro workspace (regla común, sin revelar existencia). US-001(c) / FR-004, FR-108: con la BD simulada caída (doble del pool que lanza error), `POST /auth/refresh` y un endpoint con `require_workspace_access` → 503, nunca 401 ni 2xx.

## T007 — UI por rol y pantalla Equipo
- **Agente:** frontend
- **Depende de:** T006
- **Paralelo:** No
- **Historia:** US-001
- **Archivos:** front/src/lib/auth-context.tsx, front/src/routes/_authenticated.tsx, front/src/routes/_authenticated/team.tsx (nuevo), front/src/lib/api/workspaces.ts

## T008 — Revisión US-001: matriz rol × endpoint, rate limit de login y sin credenciales versionadas (SC-001, SC-003, SC-011, FR-105)
- **Agente:** reviewer
- **Depende de:** T007, T005
- **Paralelo:** No
- **Historia:** US-001
- **Archivos:** backend-lang/tests/test_roles_matrix.py (solo ejecución), backend-lang/tests/test_auth_rate_limit.py (solo ejecución), backend-lang/tests/test_channels_roles.py (solo ejecución), front/src/routes/_authenticated/team.tsx (solo lectura), front/drizzle.config.ts (solo lectura)
- **Alcance:** criterio de aprobación de SC-001: cada fila existente de la "Matriz objetivo rol × endpoint" de la spec tiene su caso en `test_roles_matrix.py` y pasa (solo el caso `trial` de la fila 32 va `xfail(strict=True)` hasta T058). Una fila sin caso o con resultado distinto = rechazo. No se compara contra `arbol-rutas.md` §3.

## T009 — Cuenta: email_verified_at, auth_tokens, CHECK de subscriptions.status con trial, plan Trial y slug único
- **Agente:** dba
- **Depende de:** T001
- **Paralelo:** No
- **Historia:** US-002
- **Archivos:** backend-lang/migrations/008_auth_tokens_trial.sql (nuevo)
- **Alcance:** `DROP CONSTRAINT IF EXISTS` + `ADD CONSTRAINT … CHECK (status IN ('trial','active','pending_payment','suspended','cancelled','expired'))` en `subscriptions`; plan semilla `Trial` (precio 0) en `billing_plans`; `trial` para cada workspace sin fila en `subscriptions` (único mecanismo de backfill, US-013(b)); `users.email_verified_at`; tabla `auth_tokens` (D-U1; sin RLS, D-U6); índice único de `workspaces.slug` si falta.

## T010 — Registro transaccional con trial, slug alternativo, 400 genérico (enumeración aceptada, D16) y 503 con rollback
- **Agente:** backend
- **Depende de:** T009, T003, T004
- **Paralelo:** No
- **Historia:** US-002
- **Archivos:** backend-lang/src/api/routes/auth.py, backend-lang/src/schemas/auth.py
- **Alcance:** email repetido → se conserva el 400 con el mensaje genérico actual (`auth.py:37-40`) y no se crea ninguna fila (FR-012, plan D16). Carrera con email repetido: dos `POST /auth/register` simultáneos con el mismo email (la comprobación de `auth.py:35` está fuera de la transacción) → uno 2xx y el otro **400** genérico, nunca 500 (se captura la violación de unicidad de `users.email` en el INSERT). Colisión de slug (`UNIQUE`, `001_initial_schema.sql:33`; hoy `auth.py:58-67` no la captura → 500 probable): se captura y se reintenta con un slug alternativo; si se agotan los reintentos → 400, nunca 500 (FR-018). Ambos casos entran en `test_auth_flows.py` (T012).

## T011 — Endpoints de verificación de correo y recuperación de contraseña (502 si falla el email)
- **Agente:** backend
- **Depende de:** T010, T006
- **Paralelo:** No
- **Historia:** US-002
- **Archivos:** backend-lang/src/api/routes/auth.py, backend-lang/src/schemas/auth.py, backend-lang/src/services/email_service.py

## T012 — Tokens de un solo uso, respuesta uniforme, gate de email verificado, rate limit de registro y tests de cuenta
- **Agente:** security
- **Depende de:** T011, T004
- **Paralelo:** No
- **Historia:** US-002
- **Archivos:** backend-lang/src/api/routes/auth.py, backend-lang/src/core/security.py, backend-lang/src/api/routes/kapso.py, backend-lang/src/api/routes/channels.py, backend-lang/tests/test_auth_flows.py (nuevo)
- **Alcance:** usa el helper de rate limit de `core/security.py` creado en T004 (D15). `test_auth_flows.py` cubre email repetido → 400 genérico sin filas, la carrera de dos registros simultáneos con el mismo email → 400 (no 500), la colisión de slug → reintento o 400 (no 500) (FR-018, T010) y el 429 de registro (FR-012, FR-104).

## T013 — Front de verificación, reset, redirección con sesión y ocultar login social
- **Agente:** frontend
- **Depende de:** T012, T007
- **Paralelo:** No
- **Historia:** US-002
- **Archivos:** front/src/routes/verify-email.tsx, front/src/routes/login.tsx, front/src/routes/signup.tsx, front/src/routes/reset-password.tsx (nuevo), front/src/lib/auth-context.tsx, front/src/lib/api/auth.ts
- **Alcance:** FR-108 (US-001(c)): `auth-context.tsx` solo cierra la sesión ante 401; ante 503/5xx o error de red en `POST /auth/refresh` o en la carga del workspace conserva el token y el usuario, y muestra un error recuperable con "Reintentar" (sin redirigir a `/login`). **Caso de prueba** (el front no tiene framework de tests; lo ejecuta T014 a mano con el backend de dev o un doble de `fetch`): con sesión iniciada, `POST /auth/refresh` → 503 ⇒ el token sigue en almacenamiento, la ruta no cambia a `/login` y aparece el error con "Reintentar"; al volver a 200 y pulsar "Reintentar", el panel carga sin nuevo login; con 401 ⇒ sí cierra sesión.

## T014 — Revisión US-002
- **Agente:** reviewer
- **Depende de:** T013
- **Paralelo:** No
- **Historia:** US-002
- **Archivos:** backend-lang/tests/test_auth_flows.py (solo ejecución), front/src/routes/verify-email.tsx (solo lectura), front/src/routes/reset-password.tsx (solo lectura), front/src/lib/auth-context.tsx (solo lectura)
- **Alcance:** además de US-002, ejecuta el caso de prueba de FR-108 descrito en T013 (sesión conservada ante 503) y lo anota como aprobado o rechazado.

---

## Fase 2 — Configuración del negocio

## T015 — workspaces.settings (working_hours, onboarding, tono, ciudad) y unicidad de servicios
- **Agente:** dba
- **Depende de:** T009
- **Paralelo:** No
- **Historia:** US-003
- **Archivos:** backend-lang/migrations/009_workspace_settings.sql (nuevo)

## T016 — Validación IANA, settings tipados, preset idempotente, tono en el prompt y tests
- **Agente:** backend
- **Depende de:** T015, T004, T006
- **Paralelo:** No
- **Historia:** US-003
- **Archivos:** backend-lang/src/schemas/workspace.py, backend-lang/src/api/routes/workspaces.py, backend-lang/src/api/routes/services.py, backend-lang/src/services/appointment_agent.py, backend-lang/tests/test_workspace_settings.py (nuevo)

## T017 — Onboarding sin errores tragados, horario editable y progreso real
- **Agente:** frontend
- **Depende de:** T016, T007
- **Paralelo:** No
- **Historia:** US-003
- **Archivos:** front/src/routes/_authenticated/onboarding.tsx, front/src/routes/_authenticated/settings.tsx, front/src/routes/_authenticated.tsx, front/src/lib/api/workspaces.ts

## T018 — Revisión US-003
- **Agente:** reviewer
- **Depende de:** T017
- **Paralelo:** No
- **Historia:** US-003
- **Archivos:** backend-lang/tests/test_workspace_settings.py (solo ejecución), front/src/routes/_authenticated/onboarding.tsx (solo lectura)

## T019 — Rescate del stash: redacción en ChannelOut, decrypt_token y URL del webhook Kapso
- **Agente:** backend
- **Depende de:** T012
- **Paralelo:** No
- **Historia:** US-004
- **Archivos:** backend-lang/src/schemas/channel.py, backend-lang/src/services/embedded_signup_service.py, backend-lang/src/services/kapso_onboarding.py, backend-lang/src/api/routes/webhooks.py, backend-lang/src/api/routes/kapso.py
- **Alcance:** FR-109: el cliente Kapso de `kapso_onboarding.py` reintenta 429/5xx/timeout como máximo 2 veces con backoff al crear el setup link; agotados los reintentos, `kapso.py` responde 502 con `detail` legible y sin tocar filas de `channels`. El test lo crea T020.

## T020 — Prueba de no fuga de tokens y acceso solo owner verificado al onboarding de Kapso
- **Agente:** security
- **Depende de:** T019, T006
- **Paralelo:** No
- **Historia:** US-004
- **Archivos:** backend-lang/tests/test_channels_roles.py, backend-lang/tests/test_kapso_onboarding.py, backend-lang/src/schemas/channel.py
- **Alcance:** `test_kapso_onboarding.py` añade el caso de SC-013: un doble del evento `whatsapp.phone_number.created` (firmado, sin tráfico real) llega al webhook de Kapso → `GET /workspaces/{id}/channels` devuelve el canal `active` con su número, y el tiempo medido desde el evento queda ≤ 2 min. Añade también el caso de FR-109 (US-004(c)): doble de Kapso que responde 503 → `POST …/kapso/onboarding-link` hace 3 intentos en total (1 + 2 reintentos) y devuelve 502 con `detail`, 0 filas nuevas en `channels`; doble que responde 503 y luego 200 → 2xx con el setup link. Lo ejecuta T022.

## T021 — Conectar WhatsApp por Kapso en onboarding y Ajustes, y reparar Embedded Signup
- **Agente:** frontend
- **Depende de:** T020, T017
- **Paralelo:** No
- **Historia:** US-004
- **Archivos:** front/src/routes/_authenticated/onboarding.tsx, front/src/routes/_authenticated/settings.tsx, front/src/lib/api/channels.ts
- **Alcance:** FR-109: un 502 de `POST …/kapso/onboarding-link` muestra el `detail` y un botón "Reintentar" que repite la llamada.

## T022 — Revisión US-004 (gate de fase 2 para SC-013 y SC-018)
- **Agente:** reviewer
- **Depende de:** T021
- **Paralelo:** No
- **Historia:** US-004
- **Archivos:** backend-lang/tests/test_kapso_onboarding.py (solo ejecución), backend-lang/tests/test_channels_roles.py (solo ejecución), front/src/routes/_authenticated/settings.tsx (solo lectura)

## T023 — Calendars (connected_by_user_id, token push, sync) y tabla oauth_states
- **Agente:** dba
- **Depende de:** T015
- **Paralelo:** No
- **Historia:** US-005
- **Archivos:** backend-lang/migrations/010_calendar_oauth.sql (nuevo)
- **Alcance:** la tabla `oauth_states` se crea sin RLS (D-U1; RLS retirado por D-U6).

## T024 — OAuth de Calendar con JWT, state firmado y nonce de un solo uso
- **Agente:** security
- **Depende de:** T023, T012, T004
- **Paralelo:** Sí [P]
- **Historia:** US-005
- **Archivos:** backend-lang/src/api/routes/auth.py, backend-lang/src/core/security.py
- **Alcance:** FR-031: además de `require_workspace_access("workspace_owner")`, comprobación explícita de `member_role == 'workspace_owner'` sobre el workspace pedido, porque el atajo de SA (`security.py:101-103`) dejaría pasar a `super_admin`; SA → 403 (fila 3 de la matriz).

## T025 — Validar X-Goog-Channel-Token en el webhook de Google Calendar (401)
- **Agente:** security
- **Depende de:** T023, T019
- **Paralelo:** Sí [P]
- **Historia:** US-005
- **Archivos:** backend-lang/src/api/routes/webhooks.py, backend-lang/src/services/calendar_service.py

## T026 — Listar y elegir calendario; Google no bloqueante con reintentos; tests de OAuth (SC-002)
- **Agente:** backend
- **Depende de:** T024, T025, T020
- **Paralelo:** No
- **Historia:** US-005
- **Archivos:** backend-lang/src/api/routes/channels.py, backend-lang/src/schemas/channel.py, backend-lang/src/services/calendar_service.py, backend-lang/src/integrations/google_calendar.py, backend-lang/tests/test_google_oauth.py (nuevo)
- **Alcance:** los endpoints de listar y elegir calendario exigen `require_workspace_access("workspace_owner")` (FR-034); `test_google_oauth.py` cubre que `manager`, `staff` y `viewer` reciben 403 en ambos. También cubre: `GET /auth/google/calendar/url` con `super_admin` → 403 (FR-031, comprobación explícita de T024; fila 3 de la matriz); y webhook de Google sin `X-Goog-Channel-Token` válido → 401 y sin sync (FR-036, US-005 escenario 4 y borde (a); la validación la implementa T025).

## T027 — Selector de calendario, desconectar y manejo de calendar_error
- **Agente:** frontend
- **Depende de:** T026, T021, T013
- **Paralelo:** No
- **Historia:** US-005
- **Archivos:** front/src/routes/_authenticated/settings.tsx, front/src/routes/_authenticated/onboarding.tsx, front/src/lib/api/channels.ts, front/src/lib/api/auth.ts

## T028 — Revisión US-005 (SC-002)
- **Agente:** reviewer
- **Depende de:** T027
- **Paralelo:** No
- **Historia:** US-005
- **Archivos:** backend-lang/tests/test_google_oauth.py (solo ejecución), backend-lang/src/api/routes/auth.py (solo lectura)

## T029 — Auditoría serializable, desactivar servicio (soft delete) y tests
- **Agente:** backend
- **Depende de:** T002, T016
- **Paralelo:** No
- **Historia:** US-006
- **Archivos:** backend-lang/src/services/audit_service.py, backend-lang/src/api/routes/services.py, backend-lang/tests/test_services_audit.py (nuevo)
- **Alcance:** regla de FR-038 (filas 13 y 14 de la matriz objetivo): `PATCH /workspaces/{id}/services/{sid}` conserva `require_workspace_access("manager")` y `DELETE` exige `workspace_owner`. `test_services_audit.py` cubre: `manager` con `PATCH is_active=false` → 200 y el servicio queda inactivo; `manager` con `DELETE` → 403; `workspace_owner` con `DELETE` → 2xx (soft delete, histórico conservado); fila en `audit_logs` al cambiar el precio (FR-039).

## T030 — Formulario de servicio, switch persistente, desactivar y estado vacío
- **Agente:** frontend
- **Depende de:** T029, T007
- **Paralelo:** Sí [P]
- **Historia:** US-006
- **Archivos:** front/src/routes/_authenticated/services.tsx, front/src/components/service-form-dialog.tsx, front/src/hooks/use-services.ts

## T031 — Revisión US-006
- **Agente:** reviewer
- **Depende de:** T030
- **Paralelo:** No
- **Historia:** US-006
- **Archivos:** backend-lang/tests/test_services_audit.py (solo ejecución), front/src/routes/_authenticated/services.tsx (solo lectura)

---

## Fase 3 — Mensajería confiable

## T032 — Índice único de mensaje del proveedor, last_inbound_at y pending_booking
- **Agente:** dba
- **Depende de:** T023
- **Paralelo:** No
- **Historia:** US-007
- **Archivos:** backend-lang/migrations/011_conversations_dedup.sql (nuevo)

## T033 — Dedup por wamid, tareas con referencia fuerte, drenado al apagar, no-texto, secreto vacío y canal inexistente
- **Agente:** backend
- **Depende de:** T032, T025
- **Paralelo:** No
- **Historia:** US-007
- **Archivos:** backend-lang/src/api/routes/webhooks.py, backend-lang/src/services/conversation_service.py, backend-lang/src/api/main.py

## T034 — Límite de 1 MB en Meta, firma inválida 403 (Meta) / 401 (Kapso) y rate limit de webhooks sobre rate_limits (sin X-Workspace-ID)
- **Agente:** security
- **Depende de:** T033, T004
- **Paralelo:** No
- **Historia:** US-007
- **Archivos:** backend-lang/src/api/routes/webhooks.py, backend-lang/src/api/main.py
- **Alcance:** usa el helper de rate limit de T004 (D15). Conserva 403 para firma de Meta inválida (`webhooks.py:122`) y 401 para Kapso (`webhooks.py:288`), sin escribir filas (FR-049); el 413 se evalúa antes de la firma (FR-043).

## T035 — Lock por conversación, timeout del pool, reintentos Meta y token por canal
- **Agente:** backend
- **Depende de:** T033, T019
- **Paralelo:** Sí [P]
- **Historia:** US-007
- **Archivos:** backend-lang/src/services/agent_service.py, backend-lang/src/core/database.py, backend-lang/src/services/whatsapp_service.py

## T036 — docker-compose (montaje del front tras confirmar), bcrypt<5, tests funcionales de confiabilidad y arnés de estrés
- **Agente:** backend
- **Depende de:** T034, T035
- **Paralelo:** No
- **Historia:** US-007
- **Archivos:** docker-compose.yml, backend-lang/pyproject.toml, backend-lang/requirements.txt, backend-lang/tests/test_webhook_reliability.py (nuevo), backend-lang/tests/stress/ (nuevo; ejecución autorizada, D-U2)
- **Alcance:** (0) Arnés de estrés autorizado (D-U2, FR-052): `tests/stress/` corre en local contra PostgreSQL efímero (Docker; si Docker no está disponible en WSL, PostgreSQL local) con tráfico simulado y dobles de Kapso, Meta y Google; incluye el preflight de cero tráfico real de `pruebas-estres.md` §4 (aborta si detecta egress a WhatsApp/Meta/Kapso/Google). (1) **Confirmar con el usuario antes de cambiar el montaje** de `docker-compose.yml` (`./front/dist` frente a `front-app/dist` desplegado por FTP; pregunta abierta 9 de la spec). Sin respuesta, el montaje no se toca y solo se aplica `bcrypt>=4.3,<5`. (2) `test_webhook_reliability.py` cubre el gate alternativo (SC-006, SC-010, SC-012) y el rechazo de firma: 403 en Meta, 401 en Kapso, 413 antes de la firma, 0 filas escritas (FR-043, FR-049). Cubre además los escenarios de US-007 que implementan T035 y T033: (3) escenario 2 / FR-046, serialización: dos inbound del mismo cliente con < 2 s de diferencia (`asyncio.gather`, agente doble con latencia) → las dos corridas de `agent_runs` de esa conversación no se solapan en el tiempo (`started_at` de la segunda ≥ `finished_at` de la primera), y dos conversaciones distintas sí corren en paralelo; (4) escenario 4 / FR-049, no-texto: un mensaje `audio` y uno `image` (Meta y Kapso) → 1 outbound "por ahora solo leo texto" cada uno y ninguna corrida del agente.

## T037 — Revisión US-007: escenarios de estrés E1, E2, E8, E9, E11 con arnés y tests funcionales de confiabilidad
- **Agente:** reviewer
- **Depende de:** T036, T004
- **Paralelo:** No
- **Historia:** US-007
- **Archivos:** backend-lang/tests/test_webhook_reliability.py (solo ejecución), backend-lang/tests/stress/ (solo ejecución, autorizada D-U2), specs/003-producto-final-citas/pruebas-estres-resultados.md (nuevo)
- **Alcance:** gate por defecto con arnés (D-U2): SC-006, SC-007, SC-008, SC-010, SC-012 medidos con el preflight de cero tráfico real aprobado. El gate alternativo de la spec solo aplica como respaldo si el arnés no puede correr (se anota el motivo en `pruebas-estres-resultados.md`).

---

## Fase 4 — Reserva correcta

## T038 — Exclusión de solapes en appointments y columnas de cancelación/confirmación
- **Agente:** dba
- **Depende de:** T032
- **Paralelo:** No
- **Historia:** US-008
- **Archivos:** backend-lang/migrations/012_appointments_exclusion.sql (nuevo)

## T039 — agent_alerts: severidad low/medium/high/critical y resolved_at
- **Agente:** dba
- **Depende de:** T038
- **Paralelo:** No
- **Historia:** US-008
- **Archivos:** backend-lang/migrations/013_agent_alerts.sql (nuevo), backend-lang/src/services/agent_service.py (solo lectura)
- **Alcance:** añadir `resolved_at TIMESTAMPTZ`; `UPDATE` de datos (`info→low`, `warning→medium`, `error→high`; `resolved_at = created_at` donde `resolved = true`); `DROP CONSTRAINT` + `ADD CONSTRAINT … CHECK (severity IN ('low','medium','high','critical'))`; `DEFAULT 'medium'`; índice por `(workspace_id) WHERE resolved_at IS NULL`. Se despliega junto con T042 (plan R11).

## T040 — Filtro de tenant, precio desde services e identidad system_agent en create_appointment
- **Agente:** security
- **Depende de:** T003, T016
- **Paralelo:** Sí [P]
- **Historia:** US-008
- **Archivos:** backend-lang/src/api/routes/appointments.py, backend-lang/src/services/appointment_agent.py

## T041 — Disponibilidad unificada, 409 por solape y borrado compensatorio en Google
- **Agente:** backend
- **Depende de:** T038, T040, T026, T016
- **Paralelo:** No
- **Historia:** US-008
- **Archivos:** backend-lang/src/api/routes/appointments.py, backend-lang/src/services/calendar_service.py, backend-lang/src/services/appointment_agent.py

## T042 — Agente: pending_booking, datos del negocio, saludo, alternativas, alertas con nuevas severidades y tests
- **Agente:** backend
- **Depende de:** T041, T035, T039
- **Paralelo:** No
- **Historia:** US-008
- **Archivos:** backend-lang/src/services/appointment_agent.py, backend-lang/src/services/agent_service.py, backend-lang/src/services/conversation_service.py, backend-lang/tests/test_appointment_agent.py, backend-lang/tests/test_booking_race.py (nuevo)
- **Alcance (tests funcionales; son el gate alternativo de respaldo y complementan el arnés de T036, D-U2)**: `test_booking_race.py` cubre (1) SC-004: N = 2 y 10 confirmaciones concurrentes (`asyncio.gather`) del mismo hueco → 1 cita y 0 eventos huérfanos en el doble de Google; y (2) SC-009 / FR-064: doble de Google con 5 s de latencia en `.execute()`; mientras una reserva espera a Google, `GET /` responde 200 en < 200 ms (prueba que Google corre en hilo, implementado en T026). T026 no crea este caso de latencia.

## T043 — Revisión US-008: carrera E3, agente E4 y Google degradado E5 con arnés (gate alternativo solo de respaldo)
- **Agente:** reviewer
- **Depende de:** T042, T037
- **Paralelo:** No
- **Historia:** US-008
- **Archivos:** backend-lang/tests/test_appointment_agent.py (solo ejecución), backend-lang/tests/test_booking_race.py (solo ejecución), backend-lang/tests/stress/ (solo ejecución, autorizada D-U2), specs/003-producto-final-citas/pruebas-estres-resultados.md

## T044 — PATCH de citas: enum, cancelar con Google y reagendar con end_at y 409
- **Agente:** backend
- **Depende de:** T041
- **Paralelo:** No
- **Historia:** US-009
- **Archivos:** backend-lang/src/api/routes/appointments.py, backend-lang/src/schemas/appointment.py, backend-lang/src/services/calendar_service.py

## T045 — Tools cancelar_cita y reagendar_cita y botones del recordatorio
- **Agente:** backend
- **Depende de:** T044, T042, T034
- **Paralelo:** No
- **Historia:** US-009
- **Archivos:** backend-lang/src/services/appointment_agent.py, backend-lang/src/api/routes/webhooks.py, backend-lang/src/services/conversation_service.py

## T046 — Aislamiento de las tools por customer y workspace, y tests de PATCH y tools
- **Agente:** security
- **Depende de:** T045
- **Paralelo:** No
- **Historia:** US-009
- **Archivos:** backend-lang/src/services/appointment_agent.py, backend-lang/tests/test_appointment_agent.py, backend-lang/tests/test_appointments_patch.py (nuevo)

## T047 — Revisión US-009
- **Agente:** reviewer
- **Depende de:** T046
- **Paralelo:** No
- **Historia:** US-009
- **Archivos:** backend-lang/tests/test_appointment_agent.py (solo ejecución), backend-lang/tests/test_appointments_patch.py (solo ejecución)

---

## Fase 5 — Ciclo de vida y avisos

## T048 — Columnas de recordatorio y su índice
- **Agente:** dba
- **Depende de:** T039
- **Paralelo:** No
- **Historia:** US-010
- **Archivos:** backend-lang/migrations/014_reminders.sql (nuevo)
- **Alcance:** columnas `reminder_24h_sent` y `reminder_2h_sent` (FR-076; `ADD COLUMN IF NOT EXISTS`, H12; en la remota `reminder_24h_sent` ya existe como columna extra de Alembic, D-U1: se reutiliza si su tipo es `boolean NOT NULL DEFAULT false` y, si no, se alinea sin borrarla) y nueva `reminder_2h_skip_reason TEXT NULL` en `appointments` (motivo "omitido: ventana cerrada" de FR-107; no hay columna equivalente en plan ni esquema), más su índice.

## T049 — Ventana de 24 h, plantilla, worker de recordatorios exactamente una vez y tests
- **Agente:** backend
- **Depende de:** T048, T035, T044, T045
- **Paralelo:** No
- **Historia:** US-010
- **Archivos:** backend-lang/src/workers/reminder_worker.py, backend-lang/src/services/whatsapp_service.py, backend-lang/src/services/conversation_service.py, backend-lang/src/api/routes/appointments.py, backend-lang/tests/test_reminder_worker.py (nuevo)
- **Alcance:** recordatorio de 24 h (FR-072) y de 2 h (FR-107). `test_reminder_worker.py` cubre para el de 2 h: cita `confirmed` a 2 h ± 15 min con ventana abierta → 1 texto libre por el proveedor del canal y `reminder_2h_sent=true`; con ventana de 24 h cerrada → no se envía, se marca `reminder_2h_sent=true` con `reminder_2h_skip_reason='omitido: ventana cerrada'` y no se reintenta; fallo 5xx del proveedor → no se marca y se reintenta en el ciclo siguiente; 2 instancias del worker → 1 solo envío. Ciclo ≤ 10 min y tolerancia ±15 min (plan D8; hoy 30 min y ±5 min en `reminder_worker.py:22`, `:142-143`): `test_reminder_worker.py` asserta que el intervalo configurado es ≤ 600 s y que una cita a 24 h + 14 min / 2 h − 14 min entra y a ± 16 min no. Casos borde de US-010 (ambos recordatorios, 24 h y 2 h): (a) workspace con suscripción `suspended` o canal `disconnected` → el worker no llama al proveedor, no marca `reminder_*_sent` y deja un log de advertencia con `appointment_id` y motivo (FR-075, FR-063); (b) cliente sin teléfono válido (vacío o no E.164) → no se envía, no se marca enviado y se crea una `agent_alerts` (SUPUESTO severidad `medium`) con la cita y el motivo, una sola vez por cita aunque el ciclo se repita. `test_reminder_worker.py` cubre los dos casos con el proveedor doble asertando 0 llamadas.

## T050 — Revisión US-010: recordatorios masivos E7 y fallos de envío E6 con arnés (gate alternativo solo de respaldo)
- **Agente:** reviewer
- **Depende de:** T049
- **Paralelo:** No
- **Historia:** US-010
- **Archivos:** backend-lang/tests/test_reminder_worker.py (solo ejecución), backend-lang/tests/stress/ (solo ejecución, autorizada D-U2), specs/003-producto-final-citas/pruebas-estres-resultados.md
- **Alcance:** valida FR-072 y FR-107 (incluida la regla de omisión del recordatorio de 2 h con la ventana cerrada) además de SC-005.

## T051 — Agenda: nueva cita, detalle con cancelar/reagendar, bloqueos, vistas reales y test de frescura de agenda (SC-014)
- **Agente:** frontend
- **Depende de:** T044, T049, T017, T007
- **Paralelo:** No
- **Historia:** US-011
- **Archivos:** front/src/routes/_authenticated/agenda.tsx, front/src/hooks/use-appointments.ts, front/src/lib/api/appointments.ts, front/src/routes/_authenticated.tsx, front/src/lib/polling.ts (nuevo), backend-lang/tests/test_panel_freshness.py (nuevo)
- **Alcance:** `polling.ts` exporta los intervalos de refresco (agenda y mensajes) que usan los hooks. `test_panel_freshness.py` (pytest, sin arnés de estrés ni dependencias nuevas) mide con dobles la latencia "tool `crear_cita` → `GET /appointments` la devuelve", lee `AGENDA_POLL_MS` de `polling.ts` y verifica que latencia + intervalo ≤ 30 s (SC-014, parte agenda). Excepción a la regla de tests (plan): US-011 no tiene tarea backend, así que el test lo crea esta tarea.

## T052 — Revisión US-011
- **Agente:** reviewer
- **Depende de:** T051
- **Paralelo:** No
- **Historia:** US-011
- **Archivos:** backend-lang/tests/test_panel_freshness.py (solo ejecución), front/src/routes/_authenticated/agenda.tsx (solo lectura), front/src/hooks/use-appointments.ts (solo lectura)

## T053 — needs_review persistido, escalación a humano, endpoints de alertas y tests
- **Agente:** backend
- **Depende de:** T042, T045, T039, T046
- **Paralelo:** No
- **Historia:** US-012
- **Archivos:** backend-lang/src/services/agent_service.py, backend-lang/src/services/appointment_agent.py, backend-lang/src/api/routes/conversations.py, backend-lang/src/schemas/conversation.py, backend-lang/tests/test_alerts.py (nuevo)
- **Alcance:** `GET /workspaces/{id}/alerts` y resolver alerta exigen `require_workspace_access("staff")` (FR-086). `test_alerts.py` incluye la matriz de rol de ambos: `workspace_owner`, `manager` y `staff` → 2xx; `viewer` → 403; workspace ajeno → 403.

## T054 — Mensajes con polling, marcas, errores, volver en móvil, campana de alertas y test de frescura de mensajes (SC-014)
- **Agente:** frontend
- **Depende de:** T053, T051
- **Paralelo:** No
- **Historia:** US-012
- **Archivos:** front/src/routes/_authenticated/messages.tsx, front/src/hooks/use-conversations.ts, front/src/lib/api/conversations.ts, front/src/routes/_authenticated.tsx, front/src/lib/polling.ts, backend-lang/tests/test_panel_freshness.py
- **Alcance:** amplía `test_panel_freshness.py` con "webhook firmado (doble) → `GET` de mensajes lo devuelve", lee `MESSAGES_POLL_MS` de `polling.ts` y verifica latencia + intervalo ≤ 15 s (SC-014, parte mensajes).

## T055 — Revisión US-012
- **Agente:** reviewer
- **Depende de:** T054
- **Paralelo:** No
- **Historia:** US-012
- **Archivos:** backend-lang/tests/test_alerts.py (solo ejecución), backend-lang/tests/test_panel_freshness.py (solo ejecución), front/src/routes/_authenticated/messages.tsx (solo lectura)

---

## Fase 6 — Comercial y pulido

## T056 — Marca de mes pagado (planes de pago bloqueados por pregunta abierta 4; consumo por pregunta abierta 10)
- **Agente:** dba
- **Depende de:** T009, T048
- **Paralelo:** No
- **Historia:** US-013
- **Archivos:** backend-lang/migrations/015_billing.sql (nuevo), backend-lang/migrations/001_initial_schema.sql (solo lectura)
- **Alcance:** solo la marca de mes pagado (qué mes quedó pagado y por quién). `pending_payment` y `suspended` ya están en el CHECK de `subscriptions.status` (`001_initial_schema.sql:270`) y `trial` lo añade T009: esta tarea no toca ese CHECK. Antes de crear columnas, comprobar si bastan las existentes `paid_this_month` y `payment_verified_by` (`001:272`, `:276`). La tabla o vista de consumo mensual no se crea hasta que se responda la pregunta abierta 10 (unidad de cobro).

## T057 — Suscripción vigente con trial, consumo, backoffice de pagos, fin de trial y suspensión automática
- **Agente:** backend
- **Depende de:** T056, T002, T034
- **Paralelo:** No
- **Historia:** US-013
- **Archivos:** backend-lang/src/api/routes/billing.py, backend-lang/src/workers/billing_worker.py (nuevo), backend-lang/src/api/main.py
- **Alcance:** (1) `billing.py`: la consulta de `GET /billing/workspaces/{id}/subscription` (hoy `status = 'active'`, `billing.py:68`) pasa a `status IN ('trial','active','pending_payment','suspended')` y responde 2xx también en `trial`; el conjunto `allowed` de `PATCH …/subscription/status` (`billing.py:89`) incluye `trial` (FR-092, H1). (2) `billing_worker.py`, verificación diaria: `trial` → `pending_payment` al vencer el periodo de prueba (FR-106; SUPUESTO 14 días, pendiente de la pregunta abierta 4) y `pending_payment` > 10 días → `suspended` (FR-092). (3) Plan, precio y marcar pagado no están bloqueados. Conteo de conversaciones facturables, consumo y excedente (FR-088, FR-089, FR-091) quedan bloqueados por la pregunta abierta 10.

## T058 — Backoffice solo super_admin, agente bloqueado si suspended y tests de billing
- **Agente:** security
- **Depende de:** T057, T042, T053
- **Paralelo:** No
- **Historia:** US-013
- **Archivos:** backend-lang/src/api/routes/billing.py, backend-lang/src/core/security.py, backend-lang/src/services/agent_service.py, backend-lang/tests/test_billing.py (nuevo), backend-lang/tests/test_roles_matrix.py
- **Alcance:** `test_billing.py` cubre: `GET …/subscription` → 2xx con el workspace en `trial`, `active`, `pending_payment` y `suspended`, y 404 sin fila vigente (FR-092, H1); `PATCH …/subscription/status` acepta `trial`; transición `trial` → `pending_payment` al vencer el periodo (FR-106, con reloj simulado) sin tocar workspaces en prueba vigente; `pending_payment` > 10 días → `suspended`; agente sin respuesta con `suspended` (FR-063). Quita la marca `xfail` del caso `trial` de `test_roles_matrix.py` creado en T006.

## T059 — Pantallas Suscripción y backoffice de cobro
- **Agente:** frontend
- **Depende de:** T058, T054
- **Paralelo:** No
- **Historia:** US-013
- **Archivos:** front/src/routes/_authenticated/subscription.tsx (nuevo), front/src/routes/_authenticated/admin-billing.tsx (nuevo), front/src/lib/api/billing.ts, front/src/routes/_authenticated.tsx
- **Alcance:** mientras la pregunta abierta 10 no tenga respuesta, consumo y excedente no se muestran (sin valores inventados).

## T060 — Revisión US-013
- **Agente:** reviewer
- **Depende de:** T059
- **Paralelo:** No
- **Historia:** US-013
- **Archivos:** backend-lang/tests/test_billing.py (solo ejecución), backend-lang/tests/test_roles_matrix.py (solo ejecución), front/src/routes/_authenticated/subscription.tsx (solo lectura)
- **Alcance:** cierra solo las partes verificables de US-013: escenarios 1a y 2a (plan, precio, estado y marcar mes pagado) y el 3. Las partes 1b y 2b (consumo y excedente) quedan abiertas, BLOQUEADAS por la pregunta abierta 10, y se registran como pendientes, no como fallo.

## T061 — Endpoints de resumen del dashboard e historial de cliente, con tests
- **Agente:** backend
- **Depende de:** T053, T044, T049, T058
- **Paralelo:** No
- **Historia:** US-014
- **Archivos:** backend-lang/src/api/routes/conversations.py, backend-lang/src/api/routes/appointments.py, backend-lang/src/schemas/conversation.py, backend-lang/tests/test_dashboard_summary.py (nuevo), backend-lang/tests/test_roles_matrix.py
- **Alcance:** `test_dashboard_summary.py` cubre KPIs en 0 para workspace nuevo, historial de cliente con sus citas reales y aislamiento por workspace (FR-094, FR-095). Rol mínimo: resumen del dashboard `require_workspace_access("viewer")` (FR-094) e historial de cliente `require_workspace_access("staff")` (FR-095). `test_roles_matrix.py` añade la matriz rol × endpoint de los endpoints nuevos sin rol previo: listar/elegir calendario de Google (owner, FR-034), `GET /workspaces/{id}/alerts` y resolver alerta (staff, FR-086), resumen del dashboard (viewer, FR-094), historial de cliente (staff, FR-095) y backoffice de cobro (solo super_admin, FR-091); rol inferior → 403 y workspace ajeno → 403. Con esto quedan cubiertas todas las filas "nuevo" (24, 25, 28–31 y 34) de la "Matriz objetivo rol × endpoint" de la spec.

## T062 — Dashboard, topbar, clientes y Ajustes con datos y estados reales
- **Agente:** frontend
- **Depende de:** T061, T027, T059
- **Paralelo:** No
- **Historia:** US-014
- **Archivos:** front/src/routes/_authenticated/dashboard.tsx, front/src/routes/_authenticated.tsx, front/src/routes/_authenticated/clients.tsx, front/src/routes/_authenticated/settings.tsx, front/src/routes/_authenticated/messages.tsx, front/src/hooks/use-customers.ts

## T063 — Navegación móvil, legales, rutas de error, placeholders y código muerto
- **Agente:** frontend
- **Depende de:** T062
- **Paralelo:** No
- **Historia:** US-014
- **Archivos:** front/src/routes/_authenticated.tsx, front/src/routes/index.tsx, front/src/routes/signup.tsx, front/src/routes/__root.tsx, front/src/routes/_authenticated/clients.tsx, front/src/routes/_authenticated/dashboard.tsx, front/src/routes/_authenticated/onboarding.tsx, front/src/hooks/use-mobile.tsx, front/src/components/app-sidebar.tsx, front/src/components/app-header.tsx, front/src/components/weekly-calendar.tsx, front/src/components/kpi-card.tsx

## T064 — Revisión US-014: re-auditoría de vistas, tests de dashboard y diseño HILO en reporte de QA nuevo
- **Agente:** reviewer
- **Depende de:** T063
- **Paralelo:** No
- **Historia:** US-014
- **Archivos:** backend-lang/tests/test_dashboard_summary.py (solo ejecución), backend-lang/tests/test_roles_matrix.py (solo ejecución), specs/003-producto-final-citas/qa-reporte-vistas.md (nuevo), specs/003-producto-final-citas/auditoria-vistas.md (solo lectura), front/src/routes/_authenticated/dashboard.tsx (solo lectura), front/src/components/hilo/ (solo lectura)
- **Alcance:** gate de fase 6, además de SC-015 y SC-016: medición de **SC-017 en el piloto** con el criterio de la spec (observador cronometra `/signup` → horario guardado sin intervenir; pasa si el 100 % de los dueños observados termina en ≤ 15 min sin ayuda). Registra en `qa-reporte-vistas.md`, por dueño, tiempo total, paso de atasco y si pidió ayuda. Si el piloto aún no se hizo, SC-017 queda "no medida (piloto pendiente)", no como fallo; el tamaño mínimo del piloto sigue pendiente de definición de métrica (spec, SC-017).

---

## Trazabilidad FR → T###

| FR | Tareas | FR | Tareas | FR | Tareas |
|---|---|---|---|---|---|
| FR-001 | T002, T006, T008 | FR-036 | T023, T025, T026 | FR-071 | T032, T049 |
| FR-002 | T001, T003 | FR-037 | T030 | FR-072 | T049, T050 |
| FR-003 | T003, T006 | FR-038 | T029, T030 | FR-073 | T049, T050 |
| FR-004 | T003, T006 | FR-039 | T029 | FR-074 | T049 |
| FR-005 | T004 | FR-040 | T029, T030 | FR-075 | T049 |
| FR-006 | T007 | FR-041 | T030 | FR-076 | T048 |
| FR-007 | T001, T003, T006 | FR-042 | T032, T033 | FR-077 | T049 |
| FR-008 | T001, T004, T006, T008 | FR-043 | T034, T036 | FR-078 | T051 |
| FR-009 | T004 | FR-044 | T033 | FR-079 | T051 |
| FR-010 | T006, T007 | FR-045 | T001, T034 | FR-080 | T051 |
| FR-011 | T001, T009, T010 | FR-046 | T035 | FR-081 | T051 |
| FR-012 | T010, T012 | FR-047 | T035, T036 | FR-082 | T051 |
| FR-013 | T009, T011, T013 | FR-048 | T035 | FR-083 | T053, T054 |
| FR-014 | T012, T020 | FR-049 | T033, T034, T036 | FR-084 | T054 |
| FR-015 | T009, T011, T012, T013 | FR-050 | T019, T035 | FR-085 | T039, T053 |
| FR-016 | T013 | FR-051 | T036 (montaje bloqueado, pregunta abierta 9) | FR-086 | T039, T053, T054, T061 |
| FR-017 | T013 | FR-052 | T036, T037 | FR-087 | T054 |
| FR-018 | T009, T010 | FR-053 | T041 | FR-088 | T057, T059 (bloqueado, pregunta abierta 10) |
| FR-019 | T016, T017 | FR-054 | T040 | FR-089 | T056, T057 (bloqueado, pregunta abierta 10) |
| FR-020 | T016 | FR-055 | T040 | FR-090 | T056 (bloqueado, pregunta abierta 4) |
| FR-021 | T015, T017 | FR-056 | T038, T041, T042 | FR-091 | T057, T058, T059 (consumo bloqueado, pregunta abierta 10) |
| FR-022 | T015, T016 | FR-057 | T041 | FR-092 | T006, T057, T058 |
| FR-023 | T015, T016, T017 | FR-058 | T032, T042 | FR-093 | T062 |
| FR-024 | T015, T016, T017 | FR-059 | T039, T042 | FR-094 | T061, T062 |
| FR-025 | T021 | FR-060 | T042 | FR-095 | T061, T062 |
| FR-026 | T021 | FR-061 | T042 | FR-096 | T063 |
| FR-027 | T019 | FR-062 | T039, T041, T042 | FR-097 | T063 |
| FR-028 | T021 | FR-063 | T042, T058 | FR-098 | T063 |
| FR-029 | T019, T020 | FR-064 | T026, T042 | FR-099 | T063 |
| FR-030 | T021 | FR-065 | T040 | FR-100 | T062 |
| FR-031 | T024, T026 | FR-066 | T044 | FR-101 | T063 |
| FR-032 | T023, T024, T026 | FR-067 | T038, T044 | FR-102 | T063 |
| FR-033 | T023, T024 | FR-068 | T044 | FR-103 | T006 |
| FR-034 | T026, T027, T061 | FR-069 | T045, T046 | FR-104 | T012 |
| FR-035 | T027 | FR-070 | T038, T045 | FR-105 | T005 (cumplida en `94f8e44`, D-U4), T008 |
| | | | | FR-106 | T057, T058 (duración del trial pendiente, pregunta abierta 4) |
| | | | | FR-107 | T049, T050 |
| | | | | FR-108 | T003, T006, T013, T014 |
| | | | | FR-109 | T019, T020, T021, T022 |

**Cobertura**: 109/109 FR con al menos una tarea (FR-107, recordatorio de 2 h, en T049 y T050; FR-108, sesión conservada ante 5xx de BD, en T003, T006, T013 y T014; FR-109, Kapso 5xx → 502 con reintento, en T019, T020, T021 y T022). Casos borde sin FR propio con test nombrado: US-001(b) 404 de workspace inexistente (FR-004, `test_roles_matrix.py`, T006); US-007 escenarios 2 y 4 (`test_webhook_reliability.py`, T036); US-010(a) y (b) (`test_reminder_worker.py`, T049). SC-017 se mide en el piloto (T064). 64 tareas (T001–T064), sin huecos. Todas las dependencias apuntan a tareas de número menor (sin ciclos). Dependencias añadidas para que no corran a la vez tareas que editan el mismo archivo: T026→T020 (`schemas/channel.py`), T049→T045 (`conversation_service.py`), T053→T046 (`appointment_agent.py`), T058→T053 (`agent_service.py`), T061→T049 (`appointments.py`), T057→T034 (`api/main.py`), T061→T058 (`test_roles_matrix.py`), T010→T004 (`auth.py`), T011→T006 (`email_service.py`), T016→T006 (`workspaces.py`, `schemas/workspace.py`), T020→T006 (`test_channels_roles.py`) y T027→T013 (`front/src/lib/api/auth.ts`; ordena también T063 tras T013 vía T062→T027 por `signup.tsx`). SC-001 se mide contra la "Matriz objetivo rol × endpoint" de la spec (`test_roles_matrix.py`: T006, T058, T061; aprobada en T008 y T064). SC-013 lo mide `test_kapso_onboarding.py` (T020, ejecutado en T022). Las migraciones 006…015 siguen el orden de las tareas dba (T001 [006 convergencia + 007 roles/rate_limits] → T009 → T015 → T023 → T032 → T038 → T039 → T048 → T056). Revisores por historia (última tarea de cada una, sin crear código ni tests): T008, T014, T018, T022, T028, T031, T037, T043, T047, T050, T052, T055, T060, T064. SC-014 lo mide `test_panel_freshness.py` (T051, T054; ejecutado en T052 y T055).
