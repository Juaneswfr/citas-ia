# 003 — Árbol de rutas y permisos por rol

**Base**: `master` @ `f0e97b0`, 2026-10-28. Prefijos: `BE/` = `backend-lang/src/`, `FE/` = `front/src/`. Complementa [flujos.md](./flujos.md).

## 0. Cómo se decide el acceso hoy

| Capa | Mecanismo real | Archivo:línea | Problema |
|---|---|---|---|
| Front (guard) | `beforeLoad` de `_authenticated`: en SSR no comprueba nada; en el cliente lee `localStorage.hilo_jwt`, decodifica con `atob` y solo mira `exp` (**no verifica firma**) | `FE/routes/_authenticated.tsx:14-28` | Sin rol, sin comprobar onboarding ni email verificado. Solo es cosmético: la seguridad real está en el backend. |
| Front (rol) | `role` se expone en el contexto y solo se usa para mostrar una etiqueta | `FE/lib/auth-context.tsx:175`, `FE/routes/_authenticated/settings.tsx:321-323` | Ninguna ruta ni botón se oculta por rol. |
| Front (server fns) | `requireAuth` (jose HS256) y `auth-attacher` existen pero **nadie los usa**; `src/db/*` (drizzle) no se importa en ningún sitio | `FE/integrations/supabase/auth-middleware.ts:14-26`, `FE/integrations/supabase/auth-attacher.ts:6-13` | Si se activan server functions con drizzle, habrá que filtrar por `workspaceId` a mano en cada query. |
| Back (JWT) | HS256; claims `sub, email, role, workspace_id, exp` | `BE/core/security.py:29-58` | Sin `iat`, `jti` ni revocación. |
| Back (rol) | `require_role(min)` compara con `ROLE_HIERARCHY` (super_admin 5 › workspace_owner 4 › manager 3 › staff 2 › viewer 1 › system_agent 0) | `BE/core/security.py:19-26`, `:68-86` | Un rol desconocido como mínimo da 999, es decir, **siempre 403**. |
| Back (tenant) | `require_workspace_access(min)`: compara el claim `workspace_id` del token con el path. super_admin pasa siempre | `BE/core/security.py:89-112` | **No consulta `workspace_members` en BD**. |
| Back (origen del rol) | El login toma `users.role` global, no `member_role`, y elige el workspace con `LEFT JOIN … LIMIT 1` | `BE/api/routes/auth.py:96-127` | El rol de membresía se ignora. Un usuario con 2 workspaces entra en uno al azar. |
| Back (refresh) | Reemite el token con los mismos claims **sin consultar BD** | `BE/api/routes/auth.py:138-156` | Un miembro removido o un usuario `is_active=false` conserva el acceso indefinidamente. |

## 1. Roles: documentados frente a reales

| Rol | PRD | En código | Cómo se obtiene hoy |
|---|---|---|---|
| Admin global (`super_admin`) | `PRD BD §4` | Sí (`security.py:20`) | Solo por SQL manual (no hay endpoint). No hay ninguna UI de backoffice. |
| Dueño / barbero (`workspace_owner`) | Sí | Sí (`security.py:21`) | `POST /auth/register` (`auth.py:49`). |
| `manager` | Sí | Sí | **Inalcanzable**: invitar exige el rol `"owner"`, que no existe (`BE/api/routes/workspaces.py:125`). Además, el rol del token sale de `users.role` y la invitación solo escribe `member_role` (`workspaces.py:138-142`). |
| `staff` | Sí ("su agenda") | Sí | Inalcanzable por la misma razón. Tampoco hay columna de profesional asignado en `appointments`, así que "su agenda" no se puede filtrar. |
| `viewer` | Membresía y UI | Sí (`security.py:24`) | Es el valor por defecto en el login si `users.role` es nulo (`auth.py:125`). El CHECK de `users.role` en 001 no admite `viewer` (no verificado contra drizzle). |
| `system_agent` | `PRD BD §4` | Sí (nivel 0) | No se emite. El agente llama `create_appointment` con `{"sub": None}` saltándose el guard (`BE/services/appointment_agent.py:125-130`). |
| **`owner`** (string usado en guards) | Solo como `member_role` en data-model | **No existe** en `ROLE_HIERARCHY` | Usado en `workspaces.py:125`, `workspaces.py:155`, `BE/api/routes/services.py:154` y `BE/api/routes/billing.py:61`: 4 endpoints siempre en 403. |
| Cliente final | Solo WhatsApp | Entidad `customers`, sin login | Se identifica por `(workspace_id, phone)` (`BE/services/conversation_service.py:80-103`). |
| Visitante | Landing | — | Rutas públicas. |

**Recomendación (SUPUESTO S10 de flujos.md)**: el JWT lleva `role = workspace_members.member_role` del workspace activo, con valores `workspace_owner|manager|staff|viewer`. `super_admin` sale de `users.role`. Reemplazar `"owner"` por `"workspace_owner"` en los 4 guards. Hacer refresh contra BD.

---

## 2. Árbol de rutas del front

Leyenda: ✅ puede · 👁 solo ver · ❌ no debería · ⚠️ hoy puede pero no debería · — no aplica. "Guard" es el código que lo hace cumplir hoy.

```
/                              público
├── /login                     público
├── /signup                    público
├── /verify-email              público (placeholder)
├── /auth/callback             público (redirige a /login)
├── /politicas-de-privacidad   público
├── /condiciones-del-servicio  público
└── _authenticated (layout)    guard: JWT no expirado en localStorage (FE/routes/_authenticated.tsx:14-28)
    ├── /dashboard
    ├── /agenda
    ├── /services
    ├── /clients
    ├── /messages
    ├── /onboarding
    ├── /settings
    └── (# "pronto": Canales, Calendarios, Equipo, Suscripción — FE/routes/_authenticated.tsx:41-46)
```

| Ruta | Visitante | Super admin | Owner | Manager | Staff | Viewer | Guard real | Hueco |
|---|---|---|---|---|---|---|---|---|
| `/`, políticas, condiciones | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ninguno | Enlaces del footer `href="#"` (`FE/routes/index.tsx:347-348`). |
| `/login` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ninguno | Siempre navega a `/dashboard`, aunque el onboarding esté incompleto (`FE/routes/login.tsx:26-27`). "Olvidé contraseña" sin handler (`:122-124`). |
| `/signup` | ✅ | — | — | — | — | — | ninguno | Un usuario ya logueado puede registrarse otra vez. |
| `/verify-email` | ✅ | — | ✅ | ✅ | ✅ | ✅ | ninguno | Placeholder (`FE/routes/verify-email.tsx:18-21`). |
| `/dashboard` | ❌ (redirige) | 👁 | ✅ | ✅ | 👁 (solo sus citas) | 👁 | `_authenticated.tsx:14-28` | Métricas y alertas de demo (`HILO`), igual para todos los roles. |
| `/agenda` | ❌ | 👁 | ✅ ver, cancelar, reagendar, bloquear | ✅ | 👁 sus citas | 👁 | ídem | Hoy nadie puede cancelar ni bloquear: no hay UI (`FE/routes/_authenticated/agenda.tsx:87-97`, `:251-252`). Staff vería todas las citas porque no hay filtro por profesional. |
| `/services` | ❌ | 👁 | ✅ CRUD | ✅ crear y editar | 👁 | 👁 | ídem | ⚠️ Staff y viewer ven los botones de editar; el backend les responde 403 (manager mínimo, `BE/api/routes/services.py:41`, `:99`), pero la UI no lo anticipa. |
| `/clients` | ❌ | 👁 | ✅ | ✅ | 👁 + notas | 👁 | ídem | ⚠️ Viewer ve la lista de clientes en la UI, pero el backend le responde 403 (staff mínimo, `BE/api/routes/conversations.py:23`). El PATCH de notas exige staff, aunque el contrato decía manager (`conversations.py:57`, contrato `conversations.md`). |
| `/messages` | ❌ | 👁 | ✅ | ✅ | ✅ | ❌ | ídem | Solo lectura para todos. No hay toma de control humana. |
| `/onboarding` | ❌ | — | ✅ | ❌ | ❌ | ❌ | ídem | ⚠️ Cualquier rol puede entrar y lanzar WhatsApp o Calendar. El backend protege los canales (`workspace_owner`, `BE/api/routes/channels.py:118`), pero **no el OAuth de Calendar** (`BE/api/routes/auth.py:169-254`). |
| `/settings` | ❌ | 👁 | ✅ | ✅ negocio | 👁 cuenta | 👁 cuenta | ídem | Reconectar WhatsApp sale sin Bearer (`FE/routes/_authenticated/settings.tsx:101-105`). No hay secciones de horarios, plan ni equipo. |
| Equipo (FALTA) | ❌ | ✅ | ✅ | 👁 | ❌ | ❌ | — | Backend roto por el rol `"owner"` (`BE/api/routes/workspaces.py:125`, `:155`). |
| Suscripción (FALTA) | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | — | Backend roto por el rol `"owner"` (`BE/api/routes/billing.py:61`). |
| Backoffice super admin (FALTA) | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | — | No existe. Cambiar el estado de la suscripción solo es posible por API (`billing.py:76`). |

---

## 3. Endpoints del backend por rol

Abreviaturas: SA super_admin · OW workspace_owner · MG manager · ST staff · VW viewer · Cli cliente WhatsApp · Vis visitante o tercero. "WA(x)" significa `require_workspace_access(x)` (`BE/core/security.py:89`). Routers incluidos en `BE/api/main.py:77-85`.

### Auth y OAuth

| Endpoint | Guard real (archivo:línea) | SA | OW | MG | ST | VW | Vis | Hueco |
|---|---|---|---|---|---|---|---|---|
| `POST /auth/register` | ninguno (`BE/api/routes/auth.py:30`) | — | — | — | — | — | ✅ | Sin rate limit ni captcha. `member_role='workspace_owner'` puede violar el CHECK (no verificado). |
| `POST /auth/login` | ninguno (`auth.py:95`) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Sin rate limit (el `Limiter` no tiene límites: `BE/api/main.py:32`). Usa el rol global (`auth.py:125`). |
| `POST /auth/refresh` | JWT en el body (`auth.py:138-156`) | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | **No consulta BD**: un usuario revocado sigue dentro. |
| `GET /auth/me` | `get_current_user` (`auth.py:160`) | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | — |
| `GET /auth/google/calendar/url` | **ninguno** (`auth.py:173`) | | | | | | ⚠️ ✅ | Acepta cualquier `workspace_id`. |
| `GET /auth/google/callback` | **ninguno**; `state` sin firmar (`auth.py:202-246`) | | | | | | ⚠️ ✅ | **Crítico**: un tercero vincula su Google Calendar al workspace de otro y recibe eventos con nombres y teléfonos de los clientes. |

### Workspaces, miembros y servicios

| Endpoint | Guard real | SA | OW | MG | ST | VW | Hueco |
|---|---|---|---|---|---|---|---|
| `POST /workspaces/` | `require_role("workspace_owner")` (`BE/api/routes/workspaces.py:26-30`) | ✅ | ✅ | ❌ | ❌ | ❌ | No crea membresía (`:35-52`): el workspace queda huérfano. |
| `GET /workspaces/{id}` | WA(viewer) (`workspaces.py:55`) | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| `PATCH /workspaces/{id}` | WA(manager) (`workspaces.py:73`) | ✅ | ✅ | ⚠️ ✅ | ❌ | ❌ | Un manager puede poner `is_active=false` al workspace (`BE/schemas/workspace.py:29`). Debería ser solo OW. |
| `GET /workspaces/{id}/members` | WA(manager) (`workspaces.py:104`) | ✅ | ✅ | ✅ | ❌ | ❌ | — |
| `POST /workspaces/{id}/members` | WA(**"owner"**) (`workspaces.py:125`) | ❌ | ❌ | ❌ | ❌ | ❌ | **Inaccesible para todos.** |
| `DELETE /workspaces/{id}/members/{uid}` | WA(**"owner"**) (`workspaces.py:155`) | ❌ | ❌ | ❌ | ❌ | ❌ | Inaccesible. Aunque funcionara, el token del removido seguiría siendo válido. |
| `GET .../services`, `.../services/{sid}` | WA(viewer) (`BE/api/routes/services.py:19`, `:79`) | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| `POST .../services` | WA(manager) (`services.py:41`) | ✅ | ✅ | ✅ | ❌ | ❌ | — |
| `PATCH .../services/{sid}` | WA(manager) (`services.py:99`) | ✅ | ✅ | ✅ | ❌ | ❌ | Permite `is_active=false`, saltándose la regla del DELETE. Auditoría rota (`BE/services/audit_service.py:45-51`). |
| `DELETE .../services/{sid}` | WA(**"owner"**) (`services.py:154`) | ❌ | ❌ | ❌ | ❌ | ❌ | Inaccesible. |

### Citas y bloqueos

| Endpoint | Guard real | SA | OW | MG | ST | VW | Hueco |
|---|---|---|---|---|---|---|---|
| `GET .../appointments`, `/{aid}` | WA(staff) (`BE/api/routes/appointments.py:26`, `:159`) | ✅ | ✅ | ✅ | ✅ todas | ❌ | Staff ve todas las citas, no solo las suyas (no hay columna de profesional). |
| `POST .../appointments` | WA(staff) (`appointments.py:65`) | ✅ | ✅ | ✅ | ✅ | ❌ | **Servicio y cliente sin filtro por workspace** (`:73`, `:87`): con un UUID ajeno se lee el nombre de un cliente de otro tenant y se escribe en el evento. `price_cop` lo controla el llamante (`:135`). Sin lock (`:102-141`). |
| `PATCH .../appointments/{aid}` | WA(manager) + `confirmed` al cancelar (`appointments.py:179-197`) | ✅ | ✅ | ✅ | ❌ | ❌ | El `status` no se valida (el CHECK de BD da 500). Reagendar no actualiza `end_at` ni Calendar (`:212-222`). |
| `GET .../blocks` | WA(staff) (`appointments.py:252`) | ✅ | ✅ | ✅ | ✅ | ❌ | — |
| `POST/DELETE .../blocks` | WA(manager) + `confirmed` (`appointments.py:268`, `:310`) | ✅ | ✅ | ✅ | ❌ | ❌ | Los bloqueos no afectan a la disponibilidad. |

### Canales, calendarios y Kapso

| Endpoint | Guard real | SA | OW | MG | ST | VW | Hueco |
|---|---|---|---|---|---|---|---|
| `GET .../channels`, `GET .../calendars` | WA(viewer) (`BE/api/routes/channels.py:23`, `:202`) | ✅ | ✅ | ✅ | ✅ | ✅ | `GET /calendars` probablemente da 500 si la fila viene del callback OAuth (`connected_by_user_id` nulo; `BE/schemas/channel.py:56`, no verificado). |
| `POST .../channels`, `PATCH .../channels/{cid}/status`, `POST .../channels/embedded-signup` | WA(workspace_owner) (`channels.py:37`, `:76`, `:118`) | ✅ | ✅ | ❌ | ❌ | ❌ | Coincide con QA R-05 y contradice `channels.md` (manager). Se recomienda mantener solo OW. |
| `POST/DELETE .../calendars` | WA(workspace_owner) (`channels.py:225`, `:266`) | ✅ | ✅ | ❌ | ❌ | ❌ | Correcto, pero el OAuth público (arriba) lo esquiva. |
| `POST /workspaces/{id}/kapso/onboarding-link` | WA(workspace_owner) (`BE/api/routes/kapso.py:27`) | ✅ | ✅ | ❌ | ❌ | ❌ | Apagado con `KAPSO_ENABLED=false` (`kapso.py:14-19`). |

### Clientes y conversaciones

| Endpoint | Guard real | SA | OW | MG | ST | VW | Hueco |
|---|---|---|---|---|---|---|---|
| `GET/PATCH .../customers[/{id}]` | WA(staff) (`BE/api/routes/conversations.py:23`, `:37`, `:57`) | ✅ | ✅ | ✅ | ✅ | ❌ | El contrato pedía manager para el PATCH. Se recomienda dejar staff (notas operativas) y marcarlo como SUPUESTO. |
| `GET .../conversations[/{id}[/messages]]` | WA(staff) (`conversations.py:94`, `:118`, `:138`) | ✅ | ✅ | ✅ | ✅ | ❌ | No hay endpoint para enviar un mensaje humano. |

### Facturación

| Endpoint | Guard real | SA | OW | MG | ST | VW | Vis | Hueco |
|---|---|---|---|---|---|---|---|---|
| `GET /billing/plans` | ninguno (`BE/api/routes/billing.py:47`) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Correcto (pricing público). |
| `GET /billing/workspaces/{id}/subscription` | WA(**"owner"**) (`billing.py:61`) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Inaccesible. |
| `PATCH /billing/workspaces/{id}/subscription/status` | `require_role("super_admin")` (`billing.py:80-86`) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | Correcto. |

### Webhooks (actor: plataforma externa en nombre del cliente final)

| Endpoint | Guard real | Hueco |
|---|---|---|
| `GET /webhooks/whatsapp` | verify token (`BE/api/routes/webhooks.py:76-93`) | `int(challenge)` da 500 si falta el parámetro (`:93`). |
| `POST /webhooks/whatsapp` | HMAC de Meta, cierra si falta el secreto (`webhooks.py:58-73`, `:114-122`) | Sin dedup por wamid. La clave del rate limit es el header `X-Workspace-ID`, que controla el emisor (`:26`, `:102`). |
| `POST /webhooks/kapso/n/{token}` | HMAC con el secreto por canal (`webhooks.py:232-254`) | Dedup por entrega, no por mensaje (`:185-219`). |
| `POST /webhooks/kapso` | HMAC del proyecto (`webhooks.py:279-299`) | — |
| `POST /webhooks/google-calendar` | **ninguno** (`webhooks.py:379`) | No valida `X-Goog-Channel-Token`: un tercero puede provocar una sincronización que marque citas como canceladas (`BE/services/calendar_service.py:123-186`). |

### Cliente final por WhatsApp (qué puede hacer vía agente)

| Acción | Tool | Alcance real | Hueco |
|---|---|---|---|
| Ver servicios | `listar_servicios` (`BE/services/appointment_agent.py:83`) | Solo del workspace del canal (el contexto, no el modelo, decide el workspace) | — |
| Ver disponibilidad | `consultar_disponibilidad` (`:91`) | Primer calendario activo | Ignora horario y bloqueos. |
| Reservar | `crear_cita` (`:112`) | Su propio `customer_id` lo toma del contexto | Sin confirmación explícita. Invoca el endpoint con `sub=None`, saltándose el guard. |
| Cancelar o reagendar | — | FALTA | Debe limitarse a citas del mismo `customer_id` y workspace (S4). |
| Pedir humano | — | Solo alerta en caso de error | `needs_review` no se guarda (`BE/services/agent_service.py:67`). |

---

## 4. Huecos de permisos ordenados por gravedad

1. **OAuth de Google sin auth y `state` sin firmar** (`BE/api/routes/auth.py:169-254`): toma de control del calendario de cualquier workspace y fuga de datos de clientes. Hay que firmar el `state` (HMAC con `JWT_SECRET`, `workspace_id`, `user_id` y nonce con TTL de 10 min) y exigir JWT en `/url`.
2. **`create_appointment` sin filtro de tenant** en servicio y cliente (`BE/api/routes/appointments.py:73`, `:87`): fuga entre workspaces.
3. **Membresía solo por claim y refresh sin BD** (`BE/core/security.py:100-110`, `BE/api/routes/auth.py:138-156`): no se puede revocar a nadie.
4. **Rol `"owner"` inexistente** en 4 guards (`workspaces.py:125`, `:155`, `services.py:154`, `billing.py:61`): el equipo, el borrado de servicios y la suscripción no funcionan.
5. **Webhook de Google Calendar sin autenticación** (`BE/api/routes/webhooks.py:379`): cancelaciones forzadas (si el sync llega a funcionar).
6. **Rol del token sale de `users.role` y no de `member_role`** (`auth.py:125`): manager y staff no son representables.
7. **Manager puede desactivar el workspace** (`BE/schemas/workspace.py:29` con WA(manager) en `workspaces.py:73`).
8. **El front no adapta la UI al rol** (`FE/lib/auth-context.tsx:175` sin uso): botones que terminan en 403. Además, CORS `*` con credenciales (`BE/api/main.py:65-71`).
