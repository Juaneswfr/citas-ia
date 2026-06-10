# Tasks: Frontend API Services Integration

**Feature**: `002-frontend-api-services` | **Branch**: master | **Fecha**: 2026-06-01  
**Input**: `specs/002-frontend-api-services/` — plan.md, spec.md, data-model.md, contracts/api-services.md, research.md, quickstart.md

**Leyenda**: `- [x]` = completado · `- [ ]` = pendiente · `[P]` = paralelizable · `[USn]` = user story

---

## Phase 1: Setup (Estructura base)

**Purpose**: Crear los directorios que recibirán los nuevos módulos. Sin cambios en ningún archivo existente.

- [x] T001 Crear directorio `front-app/src/lib/types/` para tipos TypeScript del backend
- [x] T002 Crear directorio `front-app/src/lib/api/` para funciones de API
- [x] T003 Crear directorio `front-app/src/hooks/` para React Query hooks

---

## Phase 2: Foundational (Bloqueantes — deben completarse antes de cualquier User Story)

**Purpose**: Infraestructura de autenticación y cliente HTTP compartida por todos los módulos.

**⚠️ CRÍTICO**: Ninguna user story puede avanzar hasta completar esta fase.

- [x] T00X [P] Crear tipos TypeScript espejo de los schemas del backend en `front-app/src/lib/types/api.ts` — incluir: `TokenResponse`, `MeResponse`, `WorkspaceOut`, `ServiceOut`, `ServiceCreate`, `ServiceUpdate`, `AppointmentOut`, `AppointmentStatus`, `AppointmentUpdate`, `CustomerOut`, `CustomerUpdate`, `ConversationOut`, `MessageOut`, `BillingPlanOut`, `SubscriptionOut`
- [x] T00X [P] Crear cliente HTTP base en `front-app/src/lib/api/client.ts` — implementar `apiFetch<T>(path, options)` que lee `import.meta.env.VITE_API_URL`, adjunta `Authorization: Bearer <backendJwt>` desde el contexto de auth, y lanza `ApiError` tipada con `status` y `detail` para errores HTTP; mapear 401→redirect login, 5xx→mensaje genérico
- [x] T00X Crear módulo de autenticación del backend en `front-app/src/lib/api/auth.ts` — implementar `loginToBackend(email, password): Promise<TokenResponse>` (POST /auth/login) y `getMe(): Promise<MeResponse>` (GET /auth/me) usando `apiFetch` (depende de T005)
- [x] T00X Actualizar `front-app/src/lib/auth-context.tsx` — reemplazar mock login/signup por: (1) `supabase.auth.signInWithPassword()` para sesión Supabase, (2) llamar `loginToBackend()` para obtener JWT del backend, (3) llamar `getMe()` para obtener `workspace_id` y `role`, (4) almacenar `backendJwt` y `me` en React Context (memoria, no localStorage); exponer `workspaceId`, `role`, `backendJwt` desde el contexto (depende de T006)

**Checkpoint**: Auth context funcional con JWT real — los hooks de React Query pueden leer `workspaceId` del contexto.

---

## Phase 3: User Story 1 — Autenticación real con el backend (Priority: P1) 🎯 MVP

**Goal**: El dueño puede iniciar sesión con credenciales reales de Supabase, acceder al panel con datos de su workspace, y cerrar sesión correctamente.

**Independent Test**: Hacer login con credenciales válidas → dashboard carga sin datos de demo. Credenciales inválidas → mensaje de error. Logout → redirect a /login y no se puede volver al panel sin autenticar.

### Implementación US1

- [x] T00X [US1] Actualizar `front-app/src/routes/login.tsx` — reemplazar `window.localStorage.setItem('hilo.auth', ...)` por llamadas reales a `useAuth().login(email, password)` del auth context actualizado; mostrar error del backend cuando falla (401); conservar todo el diseño visual actual sin modificar ningún estilo ni clase CSS
- [x] T00X [US1] Actualizar `front-app/src/routes/_authenticated.tsx` — reemplazar el guard `window.localStorage.getItem('hilo.auth')` por verificación del `backendJwt` del auth context; mostrar el nombre real del workspace (`me.workspace_id` → lookup a `WorkspaceOut.name`) en el sidebar si disponible; conservar toda la estructura visual y navegación actual

**Checkpoint**: Login con credenciales reales funciona. Panel protegido con JWT real. Logout limpia la sesión.

---

## Phase 4: User Story 2 — Gestión de servicios con persistencia real (Priority: P2)

**Goal**: La página de Servicios muestra servicios reales del workspace, permite editarlos y los cambios persisten en la base de datos.

**Independent Test**: Crear un servicio → refrescar página → servicio persiste. Editar precio → recargar → precio actualizado. Desactivar → ya no aparece en lista activa.

### Implementación US2

- [x] T0XX [P] [US2] Crear módulo de API de servicios en `front-app/src/lib/api/services.ts` — implementar: `listServices(workspaceId, activeOnly?)`, `getService(workspaceId, serviceId)`, `createService(workspaceId, body)`, `updateService(workspaceId, serviceId, body)`, `deactivateService(workspaceId, serviceId)` usando `apiFetch` con los endpoints de `specs/001-db-and-endpoints/contracts/services.md`
- [x] T0XX [P] [US2] Crear módulo de adaptadores en `front-app/src/lib/api/adapters.ts` — implementar `toHiloService(svc: ServiceOut, index: number): HiloService` con el mapping: `duration_minutes→dur`, `buffer_minutes→buffer`, `price_cop→price`, `home_service_enabled→home`, `home_service_extra_price_cop→extra`, `is_active→active`; asignar `hue` cíclico por índice (clay/wine/mustard/steel/sage/plum), `pros: []`, `book: 0`
- [x] T0XX [US2] Crear hooks de React Query en `front-app/src/hooks/use-services.ts` — implementar: `useServices(activeOnly?)` con query key `['services', workspaceId]` y `staleTime: 5 * 60 * 1000`; `useCreateService()` mutation que invalida `['services', workspaceId]`; `useUpdateService(serviceId)` mutation que invalida la query; `useDeactivateService()` mutation que invalida la query; todos usan `toHiloService` del adaptador
- [x] T0XX [US2] Actualizar `front-app/src/routes/_authenticated/services.tsx` — reemplazar `HILO.services` por `const { data: services = [], isLoading } = useServices()`; en `isLoading` mostrar placeholder (misma estructura de grid con cards vacías o spinner discreto); `EditSheet.onClose` al guardar llama `useUpdateService(svc.id).mutate(formData)` con toast de confirmación/error via Sonner; botón "Nuevo servicio" llama `useCreateService().mutate(formData)`; conservar todo el layout, estilos y componentes visuales

**Checkpoint**: Servicios reales visibles y editables. Cambios persisten al refrescar.

---

## Phase 5: User Story 3 — Visualización de citas reales en la agenda (Priority: P3)

**Goal**: La agenda semanal y el dashboard muestran citas reales del workspace con estados correctos. Los KPIs del dashboard reflejan datos reales.

**Independent Test**: Con citas agendadas vía WhatsApp → aparecen en la agenda del panel. Dashboard muestra el count real de citas del día. Cancelar cita → requiere confirmación → estado cambia a cancelada.

### Implementación US3

- [x] T0XX [P] [US3] Crear módulo de API de citas en `front-app/src/lib/api/appointments.ts` — implementar: `listAppointments(workspaceId, params?)` con query params `status`, `from_date`, `to_date`; `getAppointment(workspaceId, appointmentId)`; `updateAppointment(workspaceId, appointmentId, body, confirmed?)` que añade `?confirmed=true` cuando `confirmed=true` (requerido por Principio IX del backend)
- [x] T0XX [P] [US3] Agregar `toHiloAppointment(apt, customers, services)` a `front-app/src/lib/api/adapters.ts` — mapping: `start_at→time` (format HH:mm), `end_at→end`, `customer_id→client` (lookup en customers Map), `service_id→svc` (lookup en services Map), `status`: `confirmed→upcoming/now/next/done` según hora relativa a now, `pending→upcoming`, `cancelled→done`; `via: 'wa'`, `home: is_home_service`
- [x] T0XX [US3] Crear hooks de React Query en `front-app/src/hooks/use-appointments.ts` — implementar `useAppointments(options?)` que llama en paralelo `listAppointments`, `listCustomers`, `listServices` y usa `toHiloAppointment` para enriquecer cada cita; query key `['appointments', workspaceId, options]`, `staleTime: 60 * 1000`; `useUpdateAppointment(appointmentId)` mutation con invalidación de appointments query
- [x] T0XX [US3] Actualizar `front-app/src/routes/_authenticated/agenda.tsx` — reemplazar datos de `HILO.today` o mock por `const { data: appointments = [], isLoading } = useAppointments({ from_date: weekStart, to_date: weekEnd })`; mantener el componente de calendario semanal existente (`WeeklyCalendar`) con los mismos props, solo cambiar la fuente de datos; isLoading → spinner discreto sobre el calendario
- [x] T0XX [US3] Actualizar `front-app/src/routes/_authenticated/dashboard.tsx` — reemplazar `HILO.today` por `useAppointments({ from_date: todayIso, to_date: todayIso })`; reemplazar `HILO.metrics` por métricas calculadas: `todayCount = appointments.length`, `doneCount = appointments.filter(a => a.status === 'done').length`, `upcomingCount = appointments.filter(a => a.status === 'upcoming').length`; reemplazar el `AgentPanel` de hardcode por la última conversación de `useConversations()` si disponible; conservar toda la estructura visual idéntica

**Checkpoint**: Agenda y dashboard muestran datos reales. Cancelación de cita fluye con confirmación (Principio IX).

---

## Phase 6: User Story 4 — Listado de clientes con datos reales (Priority: P4)

**Goal**: La página de Clientes muestra clientes reales del workspace. Las notas se pueden editar y persisten.

**Independent Test**: Con clientes registrados vía WhatsApp → aparecen en la lista de clientes. Editar nota de cliente → refrescar → nota persiste.

### Implementación US4

- [x] T0XX [P] [US4] Crear módulo de API de clientes y conversaciones en `front-app/src/lib/api/conversations.ts` — implementar: `listCustomers(workspaceId)`, `getCustomer(workspaceId, customerId)`, `updateCustomer(workspaceId, customerId, body)`, `listConversations(workspaceId, status?)`, `getConversation(workspaceId, conversationId)`, `listMessages(workspaceId, conversationId)` usando `apiFetch`
- [x] T0XX [P] [US4] Agregar `toHiloClient(customer, appointments)` a `front-app/src/lib/api/adapters.ts` — mapping: `name ?? phone → name`, `last_seen_at → last` (formatDistanceToNow), derivar `next` del appointment futuro más próximo, `visits` = count de appointments, `fav` = servicio más frecuente, `spend` = suma de `price_cop` de citas completadas, `status`: visits ≥ 10 → 'VIP', ≥ 5 → 'frecuente', ≥ 1 → 'activo', 0 → 'nuevo'
- [x] T0XX [US4] Crear hooks de React Query en `front-app/src/hooks/use-customers.ts` — implementar `useCustomers()` que llama `listCustomers` y `listAppointments` en paralelo para construir `HiloClient[]` con `toHiloClient`; query key `['customers', workspaceId]`, `staleTime: 5 * 60 * 1000`; `useCustomer(customerId)` para detalle; `useUpdateCustomer(customerId)` mutation que invalida `['customers', workspaceId]`
- [x] T0XX [US4] Actualizar `front-app/src/routes/_authenticated/clients.tsx` — reemplazar `HILO.clients` por `const { data: clients = [], isLoading } = useCustomers()`; acción de editar notas llama `useUpdateCustomer(id).mutate({ notes })` con toast de confirmación; isLoading → skeleton de lista; conservar toda la presentación visual existente de tarjetas de clientes

**Checkpoint**: Lista de clientes reales visible. Notas persistidas en BD.

---

## Phase 7: User Story 5 — Conversaciones y mensajes de WhatsApp (Priority: P5)

**Goal**: La sección de Conversaciones/Mensajes muestra las conversaciones reales que ha gestionado el agente.

**Independent Test**: Con conversaciones gestionadas por el agente → aparecen en la lista de mensajes. Al abrir una conversación → se ven los mensajes en orden cronológico.

### Implementación US5

- [x] T0XX [US5] Crear hooks de React Query en `front-app/src/hooks/use-conversations.ts` — implementar `useConversations(status?)` con query key `['conversations', workspaceId, status]`, `staleTime: 30 * 1000`; `useMessages(conversationId)` con query key `['messages', workspaceId, conversationId]`, `staleTime: 30 * 1000`
- [x] T0XX [US5] Actualizar `front-app/src/routes/_authenticated/messages.tsx` — reemplazar `mockMessages` por `const { data: conversations = [], isLoading } = useConversations()`; al seleccionar una conversación cargar `useMessages(conversationId)`; mapear `ConversationOut` al formato visual existente: `client: customer.name ?? customer.phone`, `preview: last message content`, `time: last_message_at` relativo, `unread: needs_review`; conservar todo el layout visual actual

**Checkpoint**: Conversaciones reales visibles. Mensajes ordenados cronológicamente.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Módulos de soporte, variables de entorno y verificación final.

- [x] T0XX [P] Crear módulo de billing en `front-app/src/lib/api/billing.ts` — implementar `listPlans()` (GET /billing/plans, sin auth) y `getSubscription(workspaceId)` (GET /billing/workspaces/{id}/subscription) para uso futuro en la sección de Suscripción del sidebar
- [x] T0XX [P] Crear `front-app/.env.example` con `VITE_API_URL=http://localhost:8000`, `VITE_SUPABASE_URL=` y `VITE_SUPABASE_ANON_KEY=` documentados para onboarding de nuevos desarrolladores
- [x] T0XX Verificar que `front-app/.env.local` tiene `VITE_API_URL` configurado apuntando al backend real (local o producción)
- [x] T0XX Revisión de estados de carga: verificar que cada página actualizada (services, dashboard, agenda, clients, messages) tiene estado `isLoading` manejado con placeholder discreto y `isError` con mensaje amigable via Sonner — sin romper la estructura visual
- [x] T0XX Verificar el flujo completo de sesión: login → dashboard con datos reales → navegación entre páginas sin re-login → logout → redirect a /login

---

## Dependencies & Execution Order

### Dependencias entre fases

- **Setup (Phase 1)**: Sin dependencias — iniciar inmediatamente
- **Foundational (Phase 2)**: Depende de Phase 1 — **bloquea todas las user stories**
- **US1 — Auth (Phase 3)**: Depende de Foundational (Phase 2)
- **US2 — Services (Phase 4)**: Depende de Foundational (Phase 2); US1 recomendado pero no estrictamente bloqueante
- **US3 — Appointments (Phase 5)**: Depende de Foundational + parcialmente de US2 (adapters.ts base)
- **US4 — Clients (Phase 6)**: Depende de Foundational + US3 (appointments para calcular stats)
- **US5 — Conversations (Phase 7)**: Depende de Foundational + conversations.ts de US4 (T019)
- **Polish (Phase 8)**: Depende de todas las user stories deseadas

### Dependencias internas por fase

**Phase 2**:
- T004 y T005 → paralelos entre sí
- T006 → depende de T004 (tipos) y T005 (client)
- T007 → depende de T006

**Phase 4 (US2)**:
- T010 y T011 → paralelos entre sí
- T012 → depende de T010 (api/services.ts) y T011 (adapters.ts base)
- T013 → depende de T012

**Phase 5 (US3)**:
- T014 y T015 → paralelos entre sí
- T016 → depende de T014 (appointments.ts) y T015 (adapter)
- T017 y T018 → dependen de T016

**Phase 6 (US4)**:
- T019 y T020 → paralelos entre sí
- T021 → depende de T019 y T020
- T022 → depende de T021

---

## Parallel Opportunities

### Máxima paralelización en Phase 2 (Foundational)
```
Paralelo:
  T004 — lib/types/api.ts
  T005 — lib/api/client.ts

Luego:
  T006 — lib/api/auth.ts (necesita T004 + T005)
  T007 — lib/auth-context.tsx (necesita T006)
```

### Paralelización en Phase 4 (US2 — Services)
```
Paralelo:
  T010 — lib/api/services.ts
  T011 — lib/api/adapters.ts (toHiloService)

Luego:
  T012 — hooks/use-services.ts
  T013 — routes/_authenticated/services.tsx
```

### Paralelización en Phase 5 (US3 — Appointments)
```
Paralelo:
  T014 — lib/api/appointments.ts
  T015 — lib/api/adapters.ts (toHiloAppointment)

Luego:
  T016 — hooks/use-appointments.ts

Luego paralelo:
  T017 — routes/_authenticated/agenda.tsx
  T018 — routes/_authenticated/dashboard.tsx
```

---

## Implementation Strategy

### MVP First (User Story 1 — Autenticación)

1. Completar Phase 1 (Setup)
2. Completar Phase 2 (Foundational)
3. Completar Phase 3 (US1 — Auth)
4. **PARAR y VALIDAR**: Login real funciona, panel protegido, logout limpia sesión
5. Mergear o demostrar MVP

### Entrega incremental

1. Foundational → Auth (US1) → Login real ✅
2. + Services (US2) → Catálogo real de servicios ✅
3. + Appointments (US3) → Agenda y dashboard con datos reales ✅
4. + Clients (US4) → CRM básico real ✅
5. + Conversations (US5) → Trazabilidad de conversaciones ✅

Cada historia añade valor sin romper las anteriores.

---

## Notes

- `[P]` = archivos diferentes sin dependencias entre sí — se pueden implementar en el mismo mensaje/turno
- Los componentes visuales (`ServiceCard`, `ThreadItem`, `AgentPanel`, etc.) **no se modifican** — solo cambia la fuente de datos que se les pasa
- `hilo-data.ts` y `mock-data.ts` se conservan intactos como referencia de tipos
- El adaptador `toHiloAppointment` requiere los mapas de customers y services — el hook `useAppointments` debe obtenerlos en paralelo con React Query
- La cancelación de cita SIEMPRE requiere `confirmed: true` (Principio IX de la constitución) — implementar dialog de confirmación antes de la llamada al API
- `staleTime` corto para conversaciones (30s) porque cambian frecuentemente; largo para servicios (5min) porque cambian raramente
- Total: **29 tareas** — 3 setup, 4 foundational, 2 US1, 4 US2, 5 US3, 4 US4, 2 US5, 5 polish
