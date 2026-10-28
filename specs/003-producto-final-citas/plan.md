# Implementation Plan: Producto final de citas por WhatsApp

**Feature**: `003-producto-final-citas` | **Branch**: master | **Fecha**: 2026-10-28 | **Spec**: [spec.md](./spec.md)
**Base**: `master` @ `f0e97b0`
**Input (exclusivo)**: [auditoria-vistas.md](./auditoria-vistas.md), [flujos.md](./flujos.md), [arbol-rutas.md](./arbol-rutas.md), [auditoria-git.md](./auditoria-git.md), [pruebas-estres.md](./pruebas-estres.md)

## Summary

Llevar el MVP actual (panel HILO + backend FastAPI + agente de citas con Kapso/Meta) a un producto pilotable con un barbero: cerrar los huecos de seguridad (OAuth de Calendar, roles, tenant), garantizar disponibilidad correcta sin doble reserva, completar el ciclo de vida de la cita (confirmación explícita, cancelar, reagendar, recordatorios), conectar Kapso en la UI y eliminar los datos falsos del panel. El camino crítico sigue `flujos.md` §D.

## Technical Context

| Aspecto | Valor (fuente) |
|---|---|
| Backend | Python 3.12, FastAPI, asyncpg (pool `min=2,max=10`), `langchain` tool-calling en `BE/services/appointment_agent.py` (no LangGraph, H18) |
| Frontend | TanStack Start/Router, React Query, JWT propio en `localStorage` (`FE/lib/auth-context.tsx`), componentes HILO en `FE/components/hilo/*` |
| BD | PostgreSQL. **Esquema canónico: `backend-lang/migrations/001..005`** + nuevas `006…014` (decisión D14). `front/drizzle/` y `front/src/db/schema.ts` no se usan en ejecución |
| WhatsApp | Kapso (`KAPSO_ENABLED`, `BE/services/kapso_onboarding.py`, `whatsapp_provider.py`) y Meta legado (`whatsapp_service.py`, URL fija H17) |
| Calendar | `googleapiclient` síncrono (H6) vía `BE/integrations/google_calendar.py` y `BE/services/calendar_service.py` |
| Despliegue | `backend-lang/Dockerfile` con `--workers 2` (H4, H9); `docker-compose.yml` monta `front-app/dist` (auditoria-git); cambiarlo a `./front/dist` está pendiente de la pregunta abierta 9 de la spec |
| Tests | `backend-lang/tests/` (7 archivos, funcionales); sin pruebas de carga (pruebas-estres §5) |

## Arquitectura y decisiones técnicas

| # | Decisión | Motivo / insumo |
|---|---|---|
| D1 | **Rol por workspace**: el JWT lleva `member_role`; `super_admin` desde `users.role`; los 4 guards `"owner"` pasan a `workspace_owner`. `require_workspace_access` y `refresh` consultan `workspace_members`. | arbol-rutas §0, §1, §4 (3, 4, 6); S10 |
| D2 | **OAuth de Calendar firmado**: `state` = HMAC(`JWT_SECRET`) de `{workspace_id, user_id, nonce, exp=10 min}`; nonce de un solo uso en tabla `oauth_states`; `/url` exige JWT + owner. | auditoria-vistas CRITICAL-1; arbol-rutas §4.1 |
| D3 | **Disponibilidad única**: una función de backend combina `working_hours` (jsonb en `workspaces.settings`, S3), `availability_blocks`, `buffer_minutes`, anticipación mínima (S4) y free/busy; la usan `consultar_disponibilidad` y `create_appointment`. | flujos B6.1, B6.3, C4.1 |
| D4 | **Anti doble reserva en BD**: `EXCLUDE USING gist (calendar_id WITH =, tstzrange(start_at,end_at) WITH &&) WHERE status IN ('pending','confirmed')` con `btree_gist`; fallback `pg_advisory_xact_lock(hashtext(calendar_id::text))` (igual que FR-056) si la extensión no está disponible (pendiente de verificación en la BD real). Violación → 409 y borrado compensatorio del evento de Google. | H5, E3; flujos C6.1 |
| D5 | **Confirmación explícita**: `conversations.pending_booking` (jsonb); `crear_cita` solo tras "sí". | S5; flujos C5.1 |
| D6 | **Idempotencia y orden**: índice único sobre el id de mensaje del proveedor en `messages`; `pg_advisory_xact_lock(hashtext(conversation_id))` para serializar corridas entre workers; tareas con `_spawn` y drenado en `lifespan`. | H1, H3, H14; flujos C9.6 |
| D7 | **Ventana de 24 h**: `conversations.last_inbound_at` + `can_send_freeform()`; fuera de ventana, plantilla `recordatorio_cita` (es_CO) vía `send_template`. | S6; flujos C1.2 |
| D8 | **Recordatorios exactamente una vez**: reclamo atómico `UPDATE … SET reminder_24h_sent=true … WHERE … RETURNING` (o `FOR UPDATE SKIP LOCKED`) antes del envío, con reversión si el proveedor falla; ciclo ≤ 10 min y tolerancia ± 15 min; proveedor y token del canal. | H9–H12; E7 |
| D9 | **Google no bloqueante**: `asyncio.to_thread` en cada `.execute()` + reintentos ≤ 3 con backoff en 429/5xx. | H6, H8; E5 |
| D10 | **Pool con timeout**: `acquire(timeout=5)` → 503. | H7; E8 |
| D11 | **Kapso como camino de WhatsApp** en UI; Meta Embedded Signup oculto pero reparado (`apiFetch` con Bearer). | S1; auditoria-vistas HIGH-2 |
| D12 | **Rescate selectivo del stash** (parches por archivo, nunca `stash apply`): redacción de tokens en `ChannelOut`, `decrypt_token` + token por canal, `connectWhatsAppEmbeddedSignup`, `front/dist` en compose (montaje condicionado a la pregunta 9), `bcrypt<5`. Descartar `167cc22`. | auditoria-git "Recomendación final" |
| D13 | **Panel honesto**: ningún dato de `HILO.*` de negocio en rutas autenticadas; lo que no tenga backend se oculta. UI de rol con un helper único sobre `useAuth().role`. | auditoria-vistas HIGH-3, MEDIUM-10 |
| D14 | **Esquema canónico = `backend-lang/migrations/`** (decidido; sustituye el SUPUESTO "drizzle" de flujos.md). Migraciones nuevas solo en `backend-lang/migrations/006…014_*.sql`; `front/drizzle/` y `front/src/db/schema.ts` no se editan. **Justificación**: (1) el backend, único proceso que toca la BD, ejecuta SQL crudo con asyncpg contra `agent_runs`, `tool_calls`, `agent_alerts` (`agent_service.py:113`), `kapso_webhook_events` y `kapso_customers` (`webhooks.py`, `kapso_onboarding.py`), tablas que solo existen en `migrations/001`, `003` y `004` y no en drizzle; (2) `docker-compose.yml` levanta solo frontend, backend y nginx, y el backend toma `DATABASE_URL` de `backend-lang/.env`: drizzle no participa en el despliegue; (3) el front no usa drizzle en ejecución: nada fuera de `front/src/db/` importa `db/client.ts` ni `db/schema.ts` (la persistencia va por la API, `CLAUDE.md`); (4) drizzle no tiene CHECK, así que no describe las restricciones que hoy rompen el registro (`member_role`, `subscriptions.status`). | Código en `f0e97b0`; analyze H3 |
| D15 | **Rate limit compartido en PostgreSQL**: tabla `rate_limits(key, window_start, hits)` con `INSERT … ON CONFLICT (key, window_start) DO UPDATE SET hits = rate_limits.hits + 1 RETURNING hits`; ventana fija; limpieza de ventanas viejas en el mismo ciclo del reminder worker. Un solo helper en `core/security.py` lo usan login (FR-008), registro (FR-104) y webhooks (FR-045). No se añade Redis. | FR-045, FR-008; H4 (2 workers) |
| D16 | **Registro con email repetido: se acepta la enumeración**, mitigada por el rate limit de FR-104. Se conserva el 400 genérico actual (`auth.py:37-40`) y no se pasa a "202 siempre + aviso por correo". **Justificación**: el registro devuelve un JWT para entrar directo al onboarding (US-002, escenario 1); responder siempre igual obligaría a quitar ese JWT y rehacer el flujo, y con 5 registros/hora por IP la enumeración masiva no es práctica. | analyze E5 M5; FR-012, FR-104 |
| D17 | **Firma de Meta inválida → 403** (lo que ya devuelve `webhooks.py:122` y espera `pruebas-estres.md` §E2); Kapso sigue con 401. Única excepción a la regla 401/403 de la spec. | analyze E5 M2; FR-049 |

## Orden de implementación por capas

Dentro de cada historia: **dba → security → backend → frontend → reviewer**, salvo que la tarea de security valide código que crea el backend de la misma historia (entonces va después: T012, T020, T034, T046, T058). Los tests los crea la última tarea backend o security de cada historia; el `reviewer` solo los ejecuta y valida (no crea código ni tests). Excepción: US-011 no tiene tarea backend, así que el test de SC-014 (`test_panel_freshness.py`) lo crea su tarea frontend T051 y lo amplía T054. Entre historias, el orden sigue el camino crítico de `flujos.md` §D:

| Fase | Historias | Capas implicadas | Gate de salida |
|---|---|---|---|
| 1. Seguridad y esquema | US-001, US-002 | dba, security, backend, frontend | SC-001, SC-003, SC-011 (test funcional de T006, ejecutado en T008) y FR-105 (T005 sin credencial por defecto, revisado en T008) |
| 2. Configuración del negocio | US-003, US-004, US-005, US-006 | dba, security, backend, frontend | SC-002, SC-013, SC-018 |
| 3. Mensajería confiable | US-007 | dba, security, backend, reviewer | Con arnés autorizado: SC-006, SC-007, SC-008, SC-010, SC-012. Sin autorización: gate alternativo de la spec (SC-006, SC-010, SC-012 funcionales; SC-007/SC-008 no medidos) |
| 4. Reserva correcta | US-008, US-009 | dba, security, backend | Con arnés: SC-004, SC-009. Sin autorización: gate alternativo (SC-004, SC-009 funcionales) |
| 5. Ciclo de vida y avisos | US-010, US-011, US-012 | dba, backend, frontend | SC-014 (`test_panel_freshness.py`, creado en T051/T054 y ejecutado en T052/T055; no requiere arnés) y, con arnés, SC-005; sin autorización, SC-005 funcional (gate alternativo) |
| 6. Comercial y pulido | US-013, US-014 | dba, backend, security, frontend | SC-015, SC-016, SC-017 (se mide en el piloto con el criterio de la spec; T064 lo registra o lo deja "no medido (piloto pendiente)"); FR-088, FR-089 y el consumo de FR-091 solo si la pregunta abierta 10 tiene respuesta |

Regla de capas: `security` va antes de cualquier `frontend` que dependa de auth (T002/T003 → T004 → T006 → T007; T005 no es de auth y solo bloquea al reviewer T008; T012 → T013; T024 → T027). Las tareas que usan el helper de rate limit de `core/security.py` dependen de T004 (T012, T024, T034). Las tareas `dba` llevan número menor que las de `backend` que las consumen.

## Mapa FR / US → capa responsable

| Historia | FR | dba | backend | security | frontend | reviewer |
|---|---|---|---|---|---|---|
| US-001 Acceso por rol | FR-001…FR-010, FR-103, FR-105, FR-108 | FR-002, FR-007, FR-008, FR-045 (`rate_limits`) | FR-004 (test 404), FR-007 (tests), FR-010, FR-103, FR-108 (test 503) | FR-001, FR-003, FR-004, FR-005, FR-007, FR-008, FR-009, FR-105, FR-108 (503, no 401) | FR-006, FR-010, FR-108 (en T013, US-002) | todos |
| US-002 Registro y cuenta | FR-011…FR-018, FR-104 | FR-011, FR-013, FR-015, FR-018 | FR-011, FR-012, FR-013, FR-015, FR-018 | FR-012 (tests), FR-014, FR-015, FR-104 | FR-013, FR-015, FR-016, FR-017 | todos |
| US-003 Onboarding y horario | FR-019…FR-024 | FR-021…FR-024 | FR-019, FR-020, FR-022, FR-023, FR-024 | — | FR-019, FR-021, FR-023, FR-024 | todos |
| US-004 WhatsApp Kapso | FR-025…FR-030, FR-109 | — | FR-027, FR-029, FR-109 | FR-014, FR-029, FR-109 (test) | FR-025, FR-026, FR-028, FR-030, FR-109 | todos |
| US-005 Google Calendar | FR-031…FR-036, FR-064 | FR-032, FR-033, FR-036 | FR-034, FR-064 | FR-031, FR-032, FR-033, FR-036 | FR-034, FR-035 | todos |
| US-006 Servicios | FR-037…FR-041 | — | FR-038 (regla de roles), FR-039, FR-040 | — | FR-037, FR-038, FR-040, FR-041 | todos |
| US-007 Mensajería confiable | FR-042…FR-052 | FR-042 | FR-042, FR-044, FR-046…FR-051 (montaje de FR-051 bloqueado, pregunta 9) | FR-043, FR-045, FR-049 (firma) | — | FR-052 |
| US-008 Reserva por WhatsApp | FR-053…FR-063, FR-065 (FR-064 está en US-005; su test de latencia lo crea T042) | FR-056, FR-059, FR-062 (`agent_alerts`, T039) | FR-053, FR-056…FR-063 | FR-054, FR-055, FR-065 | — | todos |
| US-009 Cancelar/reagendar | FR-066…FR-070 | FR-067, FR-070 | FR-066…FR-070 | FR-069 | — | todos |
| US-010 Recordatorios | FR-071…FR-077, FR-107 | FR-071, FR-076 | FR-071…FR-075, FR-077, FR-107 | — | — | todos |
| US-011 Agenda del panel | FR-078…FR-082 | — | (usa FR-066…FR-068) | — | FR-078…FR-082 + test de SC-014 | todos |
| US-012 Conversaciones y alertas | FR-083…FR-087 | FR-085, FR-086 (usa T039) | FR-083, FR-085, FR-086 | — | FR-083, FR-084, FR-086, FR-087 | todos |
| US-013 Suscripción | FR-088…FR-092, FR-106 (FR-088, FR-089, consumo de FR-091 bloqueados por pregunta 10; FR-090 por pregunta 4; duración del trial de FR-106 pendiente de la pregunta 4) | FR-089, FR-090 | FR-088, FR-089, FR-091, FR-092, FR-106 | FR-063, FR-091, FR-092, FR-106 | FR-088, FR-091 | todos |
| US-014 Panel honesto | FR-093…FR-102 | — | FR-094, FR-095 | — | FR-093…FR-102 | todos |

## Dependencias externas y modo sandbox

| Dependencia | Uso | Modo sandbox / pruebas | Riesgo |
|---|---|---|---|
| **Kapso** | Onboarding `partner_managed`, envío, webhooks por número | `KAPSO_ENABLED=false` apaga rutas (`kapso.py:14-19`); en pruebas `KAPSO_BASE_URL=http://127.0.0.1:<stub>` (pruebas-estres §4.2); `httpx.MockTransport` en tests | Webhook por número provisionado hoy con la URL del front (verificado en `webhooks.py:334`; lo corrige FR-027) |
| **WhatsApp Cloud API (Meta)** | Envío legado, plantillas, webhooks firmados | URL fija en código (H17): parchear `WhatsAppService.send_message/send_template` + proxy muerto `HTTPS_PROXY=http://127.0.0.1:9` + preflight de egress (pruebas-estres §4.3) | Plantilla `recordatorio_cita` requiere aprobación de Meta (plazo externo) |
| **Google Calendar** | OAuth, free/busy, eventos, push | Doble de `build_calendar_client` con estado y latencia (pruebas-estres §3); `GOOGLE_CLIENT_ID/SECRET` vacíos en pruebas | Cliente síncrono (H6) hasta FR-064 |
| **Billing** | Planes y suscripciones; cobro manual (S8) | Sin pasarela: solo BD. Semilla de planes pendiente de la pregunta abierta 4 | Precios no confirmados |
| **Anthropic (LLM del agente)** | `init_chat_model("anthropic:…")` | `FakeLLM` (`tests/test_appointment_agent.py:25`), `ANTHROPIC_API_KEY` vacía en pruebas | Timeout de 45 s no interrumpe Google síncrono (H8) |
| **Email (Resend)** | Verificación y reset (FR-013, FR-015) | `RESEND_API_KEY` vacía y `EmailService` parcheado en pruebas | Plantillas nuevas |

Ningún valor de secreto se escribe en specs, logs ni salidas (pruebas-estres §7.7).

## Riesgos y mitigaciones

| # | Riesgo | Impacto | Mitigación |
|---|---|---|---|
| R1 | La BD de producción no coincide con `backend-lang/migrations/001..005` (esquema canónico, D14) | Migraciones 006+ fallan o alteran un CHECK distinto | T001 compara `information_schema` y `pg_constraint` de la BD destino con 001..005 antes de aplicar 006 y documenta diferencias; las migraciones usan `IF EXISTS`/`IF NOT EXISTS` y `DROP CONSTRAINT IF EXISTS` |
| R2 | Datos existentes con citas solapadas impiden crear el `EXCLUDE` | Migración falla | T038 incluye consulta previa de solapes y limpieza manual aprobada |
| R3 | `btree_gist` no disponible en el Postgres de producción | D4 inviable | Fallback con advisory lock por calendario (D4) |
| R4 | Credencial de `.mcp.json` en el historial (commit `4d462a7`); además `front/drizzle.config.ts`, **versionado** en `f0e97b0`, trae una URL de PostgreSQL con usuario y contraseña `***` como valor por defecto | Exposición | T005 la quita del código (FR-105: solo `DATABASE_URL`, falla si falta). La rotación de ambas, que siguen en el historial, la hace el usuario (pregunta abierta 8 de la spec) |
| R5 | Cambiar el rol del JWT invalida sesiones actuales | Usuarios expulsados | Aceptado: el siguiente login emite el token correcto; comunicar al piloto |
| R6 | Plantilla de Meta no aprobada a tiempo | Recordatorios fuera de ventana no salen | Recordatorio de 24 h solo con plantilla aprobada; mientras tanto se registra alerta, no texto libre |
| R7 | Arnés de estrés requiere autorización y Docker | Sin evidencia medida de SC-007 y SC-008 | Gate alternativo funcional de la spec para las fases 3 a 5; SC-007/SC-008 quedan como riesgo aceptado del piloto si no hay autorización |
| R8 | 2 workers duplican worker de recordatorios y rate limit | Duplicados y límites ×2 | D8 (reclamo atómico) y D15 (rate limit en PostgreSQL) |
| R11 | La migración 012 (T039) rechaza `severity='error'` que hoy insertan `agent_service.py:113` y `:138` | Alertas del agente fallan entre migración y despliegue | Desplegar 012 junto con T042 (que cambia ambos INSERT a `high`); no aplicar 012 sola |
| R9 | Parches del stash en conflicto con Kapso | Regresión de Kapso | Integración a mano de `whatsapp_service.py` y `agent_service.py` (auditoria-git, plan de integración paso 3) |
| R10 | Usuarios migrados sin `password_hash` | No pueden entrar | FR-015 (reset) en la fase 1 |

## Project Structure

```
specs/003-producto-final-citas/
├── auditoria-vistas.md · flujos.md · arbol-rutas.md · auditoria-git.md · pruebas-estres.md   (insumos)
├── spec.md · plan.md · tasks.md                                                              (este paquete)
├── pruebas-estres-resultados.md                                                              (lo crea T037; lo amplían T043 y T050)
└── qa-reporte-vistas.md                                                                      (lo crea T064)

backend-lang/
├── migrations/006…014_*.sql          (nuevas, dba; esquema canónico D14)
├── src/core/{security,database}.py
├── src/api/main.py
├── src/api/routes/{auth,workspaces,services,appointments,channels,conversations,billing,kapso,webhooks}.py
├── src/schemas/{auth,workspace,service,appointment,channel,conversation}.py
├── src/services/{appointment_agent,agent_service,calendar_service,conversation_service,whatsapp_service,
│                 whatsapp_provider,kapso_onboarding,embedded_signup_service,audit_service,email_service}.py
├── src/integrations/google_calendar.py
├── src/workers/reminder_worker.py (+ billing_worker.py nuevo)
└── tests/ (+ stress/ con autorización)

front/src/
├── lib/{auth-context.tsx, polling.ts (nuevo), api/*.ts}
├── hooks/{use-appointments,use-conversations,use-customers,use-services,use-mobile}.ts(x)
├── components/{service-form-dialog.tsx, hilo/*}
└── routes/{__root,index,login,signup,verify-email,_authenticated}.tsx + reset-password.tsx (nueva)
    └── _authenticated/{dashboard,agenda,clients,messages,services,settings,onboarding}.tsx
        + team.tsx, subscription.tsx, admin-billing.tsx (nuevas)
```

## Notes

- Esta etapa es solo documentación: no se ejecutaron tests, typecheck ni build.
- Correcciones de ETAPA 1 aplicadas en esta corrida: recuento de `auditoria-vistas.md` §1/§2.10 (81 → 83 acciones, F 44 → 46) y tabla §C de `flujos.md` (Barbero PARCIAL 18 → 17, FALTA 4 → 5).
- Corrección tras `E3-analyze` (NO APTO, H1–H3): D14 decide el esquema canónico, D15 fija el rate limit, nueva tarea dba T038 (`agent_alerts`), tareas renumeradas T038→T063, gate alternativo sin arnés y tests movidos de `reviewer` a la última tarea backend/security de cada historia.
- Corrección tras `E5-analyze` (NO APTO, H1 + M1–M7): nueva tarea security T005 (credencial por defecto de `front/drizzle.config.ts`, FR-105) y renumeración T005→T006 … T063→T064; T004 añadida a las dependencias de T012, T024 y T034 (M1); D17 fija 403 para la firma de Meta (M2); test de SC-014 en T051/T054 y de dashboard en T061 (M3); D16 acepta la enumeración en el registro (M5); FR-007 cubre `users.role` nulo sin membresías (M7). M4 (montaje del front) y M6 (unidad de cobro) quedan como preguntas abiertas 9 y 10 de la spec.
- Corrección tras `E9-analyze` (NO APTO, H1 + M1–M7 + L1–L3, L5): "Matriz objetivo rol × endpoint" en la spec como criterio de SC-001 (H1); dependencias T010→T004, T011→T006, T016→T006, T020→T006 (M1); staff ve todas las citas en solo lectura (M2); manager desactiva con `PATCH is_active`, solo owner `DELETE` (M3); US-013 partida en partes verificables y bloqueadas (M4); FR-107 para el recordatorio de 2 h, total 107 FR (M5); test de latencia de Google en T042 (M6); FR-018 cerrado con evidencia y carrera de email en T010 (M7); FR-064 movido al bloque de US-005 (L3). Sin tareas nuevas: siguen 64.
- `CLAUDE.md` pide registrar cambios en `logs.md`; en esta etapa no se toca (restricción: no modificar nada fuera de `specs/003-producto-final-citas/`). Lo hará quien haga el commit.
