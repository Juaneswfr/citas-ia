# 003 — Auditoría de vistas del frontend (solo lectura)

**Base**: `master` @ `f0e97b0`, 2026-10-28. Prefijos: `FE/` = `front/src/`, `BE/` = `backend-lang/src/`. Las rutas del backend llevan los prefijos de `BE/api/main.py:77-85` (auth y workspaces tienen `prefix`; billing tiene `/billing`).
**Método**: lectura estática. No se ejecutó nada (ni tests, build ni servidores). El diseño HILO se comparó solo por clases y estructura en código.

**Alcance de la lectura obligatoria** (para no sobrestimar la cobertura):
- Leídos: `CLAUDE.md`, `PRD de Frontend` (§1-12), `PRD General` (§1-14), `specs/002/spec.md` (FR-001..013), y las reglas de rol de `specs/001/.../contracts` por grep.
- **No leídos completos / no verificados**: los contratos 001 campo por campo (solo se contrastaron `ChannelOut`, `CustomerUpdate`, `MeResponse` y los nombres de query params); `PRD Final — Integraciones` y `Plan Kapso` (solo se citan por nombre).
- El contenido de la landing (`index.tsx`, precios y textos) y de las páginas legales no se revisó más allá de enlaces y acciones.

---

## 1. Resumen ejecutivo

- 83 acciones auditadas en 7 rutas públicas y 7 autenticadas, más los layouts. **FUNCIONAL 46 · MOCK 13 · PLACEHOLDER 17 · ROTO 1 · NO CONECTADA 6.** (Recuento corregido en ETAPA 2: antes decía 81 / F 44.)
- **ROTO**: conectar WhatsApp desde Ajustes. El `fetch` crudo omite `Authorization` (`FE/routes/_authenticated/settings.tsx:101-105`), y el endpoint exige Bearer (`BE/core/security.py:17,62`). Solo el onboarding envía el token (`onboarding.tsx:245`).
- **Seguridad**: el flujo OAuth de Google Calendar no está autenticado y el `state` no está firmado. Cualquiera puede sobrescribir el calendario de otro workspace (`BE/api/routes/auth.py:169-172, 198-228`).
- **Permisos**: `require_workspace_access("owner")` usa un rol que no existe en `ROLE_HIERARCHY`, así que da 403 a todos, incluido super_admin (`BE/core/security.py:19-26,76`; usos en `billing.py:61`, `services.py:155`, `workspaces.py:125,155`).
- **Panel**: Dashboard, Agenda y topbar muestran estado de WhatsApp y Google Calendar hardcodeado (`HILO.channel`, pill fija). Solo Ajustes y Onboarding leen el estado real.

---

## 2. Tabla por ruta

Leyenda de estados: F = FUNCIONAL · M = MOCK · P = PLACEHOLDER · R = ROTO · NC = NO CONECTADA. Roles según `BE/core/security.py:19-26` (super_admin 5 › workspace_owner 4 › manager 3 › staff 2 › viewer 1).

### 2.1 Públicas

Ninguna ruta pública tiene `beforeLoad`. Un usuario ya autenticado puede entrar a `/login` y `/signup` (LOW). No hay `notFoundComponent` ni `errorComponent` en ninguna ruta (grep sin resultados en `FE/`).

#### `/` — `FE/routes/index.tsx` (guard: ninguno, público; vacío/error: n/a, contenido estático)

| Acción | Handler | API | Endpoint BE | Estado |
|---|---|---|---|---|
| Anclas Producto / Soluciones / Precios / Recursos (`:46-49,63-66`) | `href="#..."`, ids en `:74,159,291,322` | — | — | F |
| "Iniciar sesión" (`:52,67,328`) | `Link /login` | — | — | F |
| "Empieza gratis" / "Pruébalo hoy" (`:53,68,88,285,327`) | `Link /signup` | — | — | F |
| Burger (`:54`) | `setMenuOpen` (estado local) | — | — | F |
| "Ver el panel", "Conoce la agenda / servicios / clientes", "Cómo se conecta" (`:89,194,222,242,264`) | `Link` a `/dashboard`, `/services`, `/clients`, `/onboarding` | — | — | F (un visitante anónimo termina en `/login` por el guard) |
| Footer Contacto, Soporte, Privacidad, Términos (`:347-348`) | `<a href="#">` | — | — | **P**. Las páginas legales existen pero la landing no enlaza a ellas. |

#### `/login` — `FE/routes/login.tsx` (guard: ninguno; vacío: n/a; cargando: texto "Iniciando sesión…" `:140`; error: banner `:127-137`)

| Acción | Handler | API | Endpoint BE | Estado |
|---|---|---|---|---|
| "Iniciar sesión" (`:100-142`) | `handleSubmit` `:21` → `auth-context.login` `:132` → `getMe` | `POST /auth/login`, `GET /auth/me` | `BE/api/routes/auth.py:90`, `:159` | F |
| "Continuar con Google" (`:75`) | `signInWithGoogle` lanza `Error` siempre (`FE/lib/auth-context.tsx:161-163`) | — | no existe | **P**. Siempre muestra un error. |
| "¿Olvidaste tu contraseña?" (`:122`) | `<a>` sin `href` ni handler | — | no existe | **P** |
| "Crea una gratis", logo, "Volver al inicio" (`:53,63,146`) | `Link` | — | — | F |

#### `/signup` — `FE/routes/signup.tsx` (guard: ninguno; error: banner; sin casilla ni enlaces a Términos/Privacidad)

| Acción | Handler | API | Endpoint BE | Estado |
|---|---|---|---|---|
| "Crear cuenta" (`:20-32`, botón `:197`) | `register()` → `registerToBackend` (`auth-context.tsx:147-158`); el slug se deriva del nombre en cliente → `navigate /onboarding` | `POST /auth/register` | `auth.py:24` (crea user `workspace_owner` + workspace + membership, `:48,72`) | F |
| "Continuar con Google" (`:103`) | `signInWithGoogle` lanza error | — | no existe | **P** |
| "Continuar con Facebook" (`:127`) | `signInWithFacebook` lanza error (`auth-context.tsx:165-167`) | — | no existe | **P** |
| "Inicia sesión", logo, "Volver" (`:81,91,204`) | `Link` | — | — | F |

Colisión de slug (dos negocios con el mismo nombre): no verificado en el backend.

#### `/verify-email` — `FE/routes/verify-email.tsx` (guard: ninguno)

| Acción | Handler | API | Endpoint BE | Estado |
|---|---|---|---|---|
| "¿No llegó? Reenviar correo" (`:92`) | `resend` solo hace `setResent(true)` (`:18-21`) y muestra "¡Correo reenviado!" (`:79`) | ninguna | no existe | **P**. Miente al usuario. |
| "← Volver al inicio de sesión" (`:109`) | `Link` | — | — | F |
| Ruta completa | Nadie navega aquí. `signup()` (`auth-context.tsx:140-144`) devuelve `'verify-email'` pero ningún componente lo llama, y el registro hace auto-login. | — | — | **NC** (huérfana) |

#### `/auth/callback` — `FE/routes/auth/callback.tsx:4-9`

| Acción | Handler | Estado |
|---|---|---|
| Redirección a `/login` | `beforeLoad` hace `redirect` (`:5-7`). Comentario: "OAuth eliminado". | **NC** (vestigio; nadie enlaza a ella) |

#### `/condiciones-del-servicio` y `/politicas-de-privacidad` — `FE/routes/condiciones-del-servicio.tsx`, `FE/routes/politicas-de-privacidad.tsx`

| Acción | Handler | Estado |
|---|---|---|
| Nav, burger, footer, enlaces cruzados, `mailto` (`condiciones:62-121,441-442`; `politicas:62-109`) | `Link` y `<a>`; burger con estado local | F (cada una) |

Solo se llega a ellas desde la otra página o por URL directa (la landing usa `href="#"`, `index.tsx:348`). Ver HIGH-5.

### 2.2 Layout y guard — `FE/routes/_authenticated.tsx`

| Acción | Handler | API | Endpoint BE | Estado | Guard / notas |
|---|---|---|---|---|---|
| Guard de sesión (`:13-28`) | `beforeLoad` lee `localStorage.hilo_jwt` y decodifica `exp` con `atob`; no comprueba nada en SSR (`:15`) | — | — | F (cosmético) | Sin rol, sin firma, sin onboarding. `role` solo se muestra (`:249`). |
| Sidebar: Inicio, Agenda, Servicios, Clientes, Conversaciones, Configuración (`:34-47,105`) | `nav(path)` → `navigate` (`:251-254`) | — | — | F | Visible para todos los roles. |
| Sidebar: Canales, Calendarios, Equipo, Suscripción (`:41,42,45,46`) | `path:'#'`, `nav` retorna sin hacer nada (`:252`); etiqueta "pronto" (`:120`) | — | — | **P** | Las cuatro pantallas del PRD FE §4 no tienen ruta. |
| Tarjeta "Termina de configurar" (`:128-145`) | `onNav('/onboarding')`; porcentaje `onboardPct={75}` (`:272`) y texto "faltan 2 pasos" (`:144`) fijos | — | — | **M** (navega bien, el progreso es falso) | |
| Cerrar sesión (`:153`) | Icono `dotsV` con `onClick={onLogout}` → `logout` (`auth-context.tsx:77-82`) | — | — | F | Sin confirmación ni etiqueta visible; solo existe en el Sidebar de escritorio. |
| Nombre del negocio, usuario y rol (`:236-249`) | `GET /workspaces/{id}` vía `apiFetch`; si falla cae a `HILO.business.name` | `GET /workspaces/{id}` | `workspaces.py:55` (viewer) | F | Fallback silencioso a datos demo. |
| Buscador "Buscar cliente, cita… ⌘K" (`:171-179`) | `<button>` sin `onClick`; no hay atajo ⌘K en el archivo | — | no existe | **P** | |
| Pill "WhatsApp activo" (`:183-186`) | Texto y punto verde fijos; no lee canales | — | — | **M** | Aparece "activo" aunque no haya canal. |
| Campana "Alertas" (`:187`) | `Button` sin `onClick` | — | no existe | **P** | |
| "Nueva cita" topbar (`:188`) | `onCompose` → `nav('/agenda')` (`:281`) | — | — | **P** (solo navega; no hay formulario) | `POST /appointments` existe en `BE appointments.py:56`. |
| BottomTabs móvil (`:194-218`) | `NAV[0].items` (`:195`): solo Inicio, Agenda, Servicios, Clientes | — | — | F (incompleto) | Con ancho < 880 px se oculta el Sidebar (`:268`) y no queda acceso a Conversaciones, Ajustes ni Cerrar sesión. Ver HIGH-4. |
| Onboarding a pantalla completa (`:256-264`) | Oculta sidebar/topbar | — | — | F | |

Existen `FE/components/app-sidebar.tsx` y `FE/components/app-header.tsx` (shadcn, con rutas y títulos propios, p. ej. "Agenda" → `/dashboard`). Nada los importa (grep). Código muerto y fuera del diseño HILO.

### 2.3 `/dashboard` — `FE/routes/_authenticated/dashboard.tsx` (roles: cualquiera con sesión; BE exige staff para citas, `appointments.py:30`, y customers, `conversations.py:27`)

| Acción | Handler | API | Endpoint BE | Estado |
|---|---|---|---|---|
| KPI "Citas de hoy" + línea del día (`:158-161,192,218-236`) | `useAppointments({from_date,to_date})` (`FE/hooks/use-appointments.ts:23-41`) | `GET /workspaces/{id}/appointments?from_date&to_date`, `GET /customers`, `GET /services` | `appointments.py:26`, `conversations.py:23`, `services.py:19` | F. Cargando: skeleton `:219-227`. Vacío: "Sin citas para hoy" `:229`. Error: toast `:163-165`. |
| Saludo "Buenos días, Camilo" y ciudad (`:180-182`) | Texto fijo y `HILO.business.city` | — | — | **M** |
| KPIs Ingresos del mes, Automatización, Respuesta media (`:174,193-195`) | `HILO.metrics`; delta `13` fijo | — | no existe | **M** |
| "Agenda" (`:206`) | `navigate('/agenda')` | — | — | F |
| Panel "Tu agente, ahora" (`:102-150,241`) | `HILO.conversation` + animación de "escribiendo" (`:105`) | — | — | **M** |
| "Ver" del panel agente (`:147`) | `Button` sin `onClick` | — | — | **P** |
| "Necesita tu atención" + CTA (`:246-255`) | `HILO.alerts`; el CTA no tiene `onClick` (`:253`) | — | no existe (PRD FE §5 pide alertas internas) | **M** |
| Tarjeta canal + "Google Calendar sincronizado · hace 1 min" (`:259-274`) | `HILO.channel` (número, proveedor, `lastSync`) | — | `GET /channels` y `/calendars` existen (`channels.py:23,202`) | **M**. Muestra "Activo" siempre. |

Diseño HILO: usa los componentes `FE/components/hilo/*` y las variables `--wine`, `--surface`, etc. No se observan desviaciones verificables.

### 2.4 `/agenda` — `FE/routes/_authenticated/agenda.tsx` (BE: staff para leer; manager para modificar, `appointments.py:183`)

| Acción | Handler | API | Endpoint BE | Estado |
|---|---|---|---|---|
| ‹ / › / "Hoy" (`:240,242,243`) | `setWeekOffset` | refetch de `useWeekAppointments` (`:229`) | `appointments.py:26` | F |
| Segmented "Semana" (`:247,268`) | `WeekView` con `useWeekAppointments` | `GET appointments?from_date&to_date`, `customers`, `services` | `appointments.py:26` | F. Cargando: bloque skeleton `:78`. Error: toast `:231-233`. **Vacío: ausente** (semana sin citas = cuadrícula en blanco). |
| Segmented "Día" (`:267`; `DayView` `:112-160`) | `useAppointments` con la fecha de hoy (`:113`) | ídem | ídem | F. **Ignora la navegación `weekOffset`**: siempre muestra hoy. Vacío: `:135`. |
| Segmented "Mes" (`:269`; `MonthView` `:168-204`) | Cuadrícula fija: `start=-3`, 35 celdas, `withAppt` literal (`:171-174`) | — | — | **M** |
| "Bloquear" (`:251`) | `Button` sin `onClick` | — | `POST /blocks` (`appointments.py:268`), sin wrapper en el front | **P** |
| "Nueva cita" (`:252`) | `Button` sin `onClick` | — | `POST /appointments` (`:56`), sin wrapper en el front | **P** |
| Chips "Barberos" (`:258-264`) | `HILO.team`, `cursor:pointer` sin handler | — | no hay endpoint de equipo | **M** |
| Bloque de cita (`:80-100`) | `cursor:'pointer'` y hover, sin `onClick` | — | `PATCH /appointments/{id}` (`:179`); existe `useUpdateAppointment` (`use-appointments.ts:114`) que nadie usa | **P**. No hay cancelar/reagendar/ver detalle. |

Cada bloque de la cuadrícula semanal sale con `pro:''` (`use-appointments.ts:104`) y la cuadrícula es fija de 9 a 19 h (`agenda.tsx:17`). Las citas fuera de ese rango quedan fuera o con posición negativa.

### 2.5 `/clients` — `FE/routes/_authenticated/clients.tsx` (BE: staff)

| Acción | Handler | API | Endpoint BE | Estado |
|---|---|---|---|---|
| Lista (`:191,217-227`) | `useCustomers` (`FE/hooks/use-customers.ts:16-46`) | `GET customers`, `GET appointments` (**sin filtro de fechas**), `GET services` | `conversations.py:23`, `appointments.py:26`, `services.py:19` | F. Cargando `:217`. Vacío `:225-227`. Error: toast `:194-196`. |
| Buscar por nombre (`:212`) | `setQ`, filtro en cliente | — | — | F |
| Seleccionar cliente (`:223`) | `setSel` | — | — | F |
| Stats Visitas / Gasto / Próxima (`:95-97`) | Derivadas de las citas reales (`adapters.ts:55-69`) | — | — | F |
| "Guardar nota" (`:104-117`, handler `:59-63`) | `useUpdateCustomer` → `{notes}` | `PATCH /workspaces/{id}/customers/{id}` | `conversations.py:57` | F. Toast OK/error en `use-customers.ts:59,62`. |
| "Escribir" (`:87-89`) | `Button` sin `onClick` | — | no existe envío saliente (el PRD FE §9 no lo pide en el MVP) | **P** |
| "Historial de citas" (`:65-70,127-146`) | Array literal con "Hoy · 09:00", "Julián", "Samuel"…; idéntico para todos los clientes | — | — | **M**. Muestra datos falsos en un cliente real. |

### 2.6 `/messages` — `FE/routes/_authenticated/messages.tsx` (BE: staff)

| Acción | Handler | API | Endpoint BE | Estado |
|---|---|---|---|---|
| Lista de conversaciones (`:165,193-218`) | `useConversations` (`use-conversations.ts:11`) + `useCustomers` para el nombre | `GET /conversations`, `GET /customers`, `GET /appointments`, `GET /services` | `conversations.py:94` y los anteriores | F. Cargando `:193`. Vacío `:207`. Error: toast `:168-170`. |
| Seleccionar y ver mensajes (`:215,122-156`) | `useMessages` | `GET /conversations/{id}/messages` | `conversations.py:138` | F. Cargando `:143`. Vacío `:151`. **Error: ausente** (`:123` solo lee `isLoading`). |

Sin envío ni handoff: consistente con el PRD (MVP sin handoff). El detalle no muestra intención, estado, alertas ni acciones ejecutadas (PRD FE §9, "Elementos"). En móvil no hay botón de volver (HIGH-4). `useCustomers` carga todas las citas solo para resolver nombres. El estado del canal en la cabecera es un punto verde fijo (`:131-134`).

### 2.7 `/services` — `FE/routes/_authenticated/services.tsx` (BE: viewer lee, manager escribe, owner borra)

| Acción | Handler | API | Endpoint BE | Estado |
|---|---|---|---|---|
| Lista (`:202,246-266`) | `useServices` | `GET /services` | `services.py:19` | F. Cargando: skeleton `:246`. Error: toast `:206-208`. **Vacío: solo el mosaico "Agregar servicio"**, sin mensaje. |
| "Nuevo servicio" (`:241`) y mosaico "Agregar servicio" (`:251`) | `handleCreate` (`:219-227`) crea `{name:'Nuevo servicio', 30 min, 20000 COP}` sin pedir datos | `POST /services` | `services.py:41` (manager) | F, **degradado**. El comentario de `:220` lo admite. Existe `components/service-form-dialog.tsx` sin uso. |
| Editar → "Guardar" (`:175,126,64-74,211-216`) | `useUpdateService` → PATCH con nombre, duración, buffer, precio, domicilio y `is_active` | `PATCH /services/{id}` | `services.py:99` (manager) | F. Toast OK/error (`use-services.ts:63,66`). Los campos son no controlados con `ref` (`:88-101`). |
| Switch "Servicio activo" y de domicilio en el panel de edición (`:101,119-121`; `handleSave :69-70`) | Estado local enviado en el PATCH | ídem | ídem | F |
| Switch de activo en la tarjeta (`:136,148`; `Toggle :18`) | `setActive` local, sin llamada API | — | `PATCH /services/{id}` existe | **P**. Se apaga visualmente pero no se persiste y se pierde al recargar. El subtítulo "el agente solo ofrece lo que esté encendido" (`:238`) es falso para este switch. |
| "Barberos habilitados" (`:102-118`) | `HILO.team`; `svc.pros` siempre `[]` (`adapters.ts:25`); los chips no tienen `onClick` | — | no hay endpoint | **M** |
| Contador "N este mes" (`:169`) | `svc.book` siempre `0` (`adapters.ts:26`) | — | no existe | **M** |
| Desactivar/eliminar servicio | No hay botón. `useDeactivateService` (`use-services.ts:72`) sin uso | `DELETE /services/{id}` | `services.py:151-160` exige `"owner"`, que da 403 siempre (HIGH-1) | **NC** (spec 002 FR-003 pide "desactivar") |

### 2.8 `/settings` — `FE/routes/_authenticated/settings.tsx` (sin guard de rol en el front; escrituras: manager para el workspace, workspace_owner para canales y calendarios)

| Acción | Handler | API | Endpoint BE | Estado |
|---|---|---|---|---|
| Cuenta: nombre, correo, rol, workspace ID (`:389-405`) | Solo lectura desde `useAuth().me` | `GET /auth/me` (en el arranque) | `auth.py:159` | F (solo lectura) |
| "Guardar" nombre del negocio (`:359-374,419`) | `apiFetch PATCH` | `PATCH /workspaces/{id}` `{name}` | `workspaces.py:73` (manager) | F. Toast OK/error. |
| Lista de canales WhatsApp (`:64-68,141-167`) | `listChannels` | `GET /workspaces/{id}/channels` | `channels.py:23` (viewer) | F. Cargando: texto `:137`. **Error: ausente** (un fallo cae en "Sin canal conectado"). Vacío `:169-186`. Muestra número, estado y coexistencia (`:156-157`); no muestra última sincronización ni errores recientes (PRD FE §10). |
| "Conectar" / "Agregar número" / icono sync (`:161,182,189`) → `runEmbeddedSignup` `:70-125` | `FB.login` → `fetch` crudo **sin `Authorization`** (`:101-105`) | `POST /workspaces/{id}/channels/embedded-signup` | `channels.py:118-127` (`require_workspace_access("workspace_owner")` + `HTTPBearer`) | **R**. Siempre falla con 401/403. El toast muestra el detalle (`:114`). Además usa `fetch` en lugar de `apiFetch` (no dispara el handler 401). El icono sync no tiene etiqueta ni `aria-label`. |
| "Desconectar" (`:163`, handler `:127-135`) | `updateChannelStatus(...,'disconnected')` | `PATCH /channels/{id}/status?new_status=disconnected` | `channels.py:76` (workspace_owner) | F. Sin confirmación. El `catch` descarta el detalle del backend (`:132`). |
| Lista de calendarios (`:203-207,224-254`) | `listCalendars` | `GET /workspaces/{id}/calendars` | `channels.py:202` (viewer) | F. Cargando `:220`. **Error: ausente.** Vacío `:256-273`. Muestra nombre, id, estado y última sync. |
| "Conectar" / "Agregar calendario" / icono sync (`:209-218,251,269,276`) | `getGoogleCalendarUrl(ws,'settings')` → `window.location.href` | `GET /auth/google/calendar/url` → Google → `GET /auth/google/callback` → 302 `/settings?calendar_connected=1` | `auth.py:169` y `:198`; retorno consumido en `settings.tsx:333-342` | F. El icono sync **re-autoriza** en lugar de sincronizar. Ver CRITICAL-1. |
| Desconectar calendario | No hay botón. `disconnectCalendar` (`FE/lib/api/channels.ts:22`) sin uso | `DELETE /calendars/{id}` | `channels.py:266` (workspace_owner) | **NC** (PRD FE §11 pide "Desconectar") |
| Tipografía (`:286-317`) | `useTypography().setPair`; persistencia no verificada | — | — | F (local) |

La vista de Ajustes sí implementa estado real de WhatsApp y Google Calendar. Faltan las pantallas de Canales/Calendarios/Equipo/Suscripción del PRD FE §4.

### 2.9 `/onboarding` — `FE/routes/_authenticated/onboarding.tsx` (BE: owner para canal y calendario; layout a pantalla completa)

Cargando: spinner `:567-576`. Si `GET /workspaces/{id}` falla, la query devuelve `null` en silencio (`:462-463`).

| Acción | Handler | API | Endpoint BE | Estado |
|---|---|---|---|---|
| Stepper lateral, "Atrás", "Continuar", "Saltar por ahora" (`:624,689,692,697`; `handleContinue :547-564`) | `setStep` / `navigate('/dashboard')` | — | — | F. "Saltar" no marca nada como pendiente. |
| Paso 0 — nombre y tipo de negocio (`:96,122,551-554`) | `patchWorkspace` `{name, business_type}` | `PATCH /workspaces/{id}` | `workspaces.py:73` | F. **El error se traga**: `console.warn` y avanza (`:556-557`). |
| Paso 0 — "Ciudad" (`:105`, estado `:495`) | Solo estado local; el PATCH no la envía (`:551-554`) y `WorkspaceUpdate` no tiene campo (`BE/schemas/workspace.py:20-29`) | — | no existe | **NC** |
| Paso 0 — "Tono del agente" (`:89,152`) | `setTone` local, sin envío | — | no existe | **NC** |
| Paso 1 — WhatsApp (`:196-280`) | `FB.login` → `fetch` **con** Bearer (`:241-248`) | `POST /channels/embedded-signup` | `channels.py:118` | F (requiere `VITE_META_*`; configuración no verificada). Muestra conectado si hay un canal activo (`:202`). |
| Paso 2 — Google Calendar (`:284-310`) | `getGoogleCalendarUrl(ws,'onboarding')` | `GET /auth/google/calendar/url` → callback → `/onboarding?step=2&calendar_connected=1` | `auth.py:169,198` | F. El retorno se procesa en `:516-529`. Ver CRITICAL-1. |
| Paso 3 — "Crear estos servicios" (`:327-347,399`) | `Promise.all(createService × N)` con el preset `BUSINESS_PRESETS` | `POST /services` × N | `services.py:41` | F. Un fallo parcial deja servicios creados y el botón desaparece (`:349`). |
| Paso 3 — "Horarios de atención sugeridos" (`:407-426`) | Solo muestra `preset.hours` | — | no hay endpoint de horarios/disponibilidad en `BE/api/routes` | **P**. Parece que se configuran, pero nada se guarda. |
| Paso 4 — "Prueba el agente" (`:434-448`) | Conversación estática | — | — | **M**. No hay prueba real. |

No se guarda el progreso del onboarding. El `onboardPct` del sidebar es fijo (`_authenticated.tsx:272`) y el paso inicial se recalcula en cada visita (`:533-540`). Nada fuerza el onboarding tras el registro más allá de `navigate('/onboarding')` en `signup.tsx:26`.

### 2.10 Conteo (83 acciones)

| Estado | Total |
|---|---|
| FUNCIONAL | 46 |
| MOCK | 13 |
| PLACEHOLDER | 17 |
| ROTO | 1 |
| NO CONECTADA | 6 |

Cada fila de las tablas cuenta una vez, y los grupos de elementos idénticos cuentan como una sola fila. Por ruta: públicas 20 (F 12, P 6, NC 2; la fila de páginas legales cuenta 2); layout 12 (F 6, P 4, M 2); dashboard 8 (F 2, M 5, P 1); agenda 8 (F 3, M 2, P 3); clients 7 (F 5, P 1, M 1); messages 2 (F 2); services 8 (F 4, P 1, M 2, NC 1); settings 9 (F 7, R 1, NC 1); onboarding 9 (F 5, NC 2, P 1, M 1).

> **Corrección ETAPA 2 (2026-10-28, verificada contra el código en `f0e97b0`)**: (1) el layout tiene 12 filas, no 11; la fila "Onboarding a pantalla completa" (F) existe en `FE/routes/_authenticated.tsx:255-263` y no se había contado. (2) `/clients` tiene 7 filas, no 6; las filas "Escribir" (P, `clients.tsx:87-89`) e "Historial de citas" (M, `clients.tsx:65-70`) existen ambas. Totales: 81 → 83 y FUNCIONAL 44 → 46.

---

## 3. Árbol de rutas

```
/                       (index.tsx)  público
├─ #producto #features #recursos #precios   anclas internas
├─ /login               Iniciar sesión, Empieza gratis (también Pruébalo hoy)
├─ /signup
├─ /dashboard           "Ver el panel", "Conoce la agenda", footer  → guard → /login si no hay sesión
├─ /services            "Conoce los servicios", footer
├─ /clients             "Conoce los clientes", footer
├─ /onboarding          "Cómo se conecta"
└─ href="#"             Contacto · Soporte · Privacidad · Términos   (muertos)

/login      → /signup, /          ; submit → /dashboard
/signup     → /login, /           ; submit → /onboarding
/verify-email → /login            ; ← NADIE enlaza aquí (HUÉRFANA)
/auth/callback → redirect /login  ; ← NADIE enlaza aquí (HUÉRFANA)
/condiciones-del-servicio ⇄ /politicas-de-privacidad ; ambas → /, /login, /signup
   (solo alcanzables entre sí o por URL; la landing no las enlaza)

/_authenticated (guard: JWT en localStorage con exp válido)
├─ Sidebar (escritorio)
│   ├─ Inicio          → /dashboard
│   ├─ Agenda          → /agenda
│   ├─ Servicios       → /services
│   ├─ Clientes        → /clients
│   ├─ Conversaciones  → /messages
│   ├─ Canales · Calendarios · Equipo · Suscripción → '#' (sin ruta, "pronto")
│   ├─ Configuración   → /settings
│   ├─ Tarjeta "Termina de configurar" → /onboarding
│   └─ icono ⋮         → logout → /login
├─ Topbar: "Nueva cita" → /agenda · buscador y campana sin acción
├─ BottomTabs (móvil): Inicio, Agenda, Servicios, Clientes
│     ✗ sin acceso a /messages, /settings ni logout en móvil
├─ /dashboard  → botón "Agenda" → /agenda
├─ /agenda · /clients · /messages · /services · /settings   (hojas, sin salidas)
│     /settings → Google OAuth → /auth/google/callback (BE) → /settings?calendar_connected=1
└─ /onboarding (sin chrome) → "Saltar" / "Finalizar" → /dashboard
      paso Calendar → Google OAuth → /auth/google/callback (BE) → /onboarding?step=2&calendar_connected=1

Huérfanas o inalcanzables por UI: /verify-email, /auth/callback.
Alcanzable solo en escritorio: /messages, /settings (en móvil, solo por URL).
Código muerto: components/app-sidebar.tsx, app-header.tsx, service-form-dialog.tsx, weekly-calendar.tsx, kpi-card.tsx
(grep sin importadores, salvo `app-sidebar`/`app-header`, que no tienen ninguno).
```

El archivo previo `specs/003-producto-final-citas/arbol-rutas.md` cubre roles y permisos; este árbol es solo de navegación.

---

## 4. Cobertura de WhatsApp y Google Calendar por vista

| Vista | Estado de WhatsApp | Estado de Google Calendar |
|---|---|---|
| `/settings` | **Real**: `GET /channels`, con número, estado y coexistencia (`:64-68,156-157`). Conectar está ROTO. | **Real**: `GET /calendars`, con estado y última sync (`:203-207,236-239`). Conectar funciona; no se puede desconectar. |
| `/onboarding` | **Real**: canal activo (`:202,469-474`); conectar funciona (Bearer en `:245`). | **Real**: `sync_status==='active'` (`:286,476-481`). |
| `/dashboard` | **Falso**: `HILO.channel` ("Activo", "Coexistencia activa", número demo) (`:264-268`). | **Falso**: "sincronizado · hace 1 min" fijo (`:272`). |
| Topbar (todas las vistas autenticadas) | **Falso**: "WhatsApp activo" fijo (`_authenticated.tsx:183-186`). | No aplica. |
| `/messages` | Datos reales de conversaciones; punto verde "WhatsApp" fijo (`:131-134`). No hay estado del canal. | No aplica. |
| `/agenda`, `/clients`, `/services` | No muestran estado de canal. | `/agenda` no muestra origen ni sincronización con Google (PRD FE §6 lo pide). |

Meta Embedded Signup lo usan Ajustes y Onboarding directamente, con `featureType: 'coexistence'` y `FB.login` (`settings.tsx:122`, `onboarding.tsx:260`). **Kapso** (`POST /workspaces/{id}/kapso/onboarding-link`, `BE kapso.py:27`) no tiene ningún consumidor y ninguna cadena `kapso` aparece en `FE/`. No se verificó si el plan Kapso (`documentation/Plan de implementación Kapso WhatsApp.md`) pide usarlo desde el panel.

---

## 5. Hallazgos priorizados

### CRITICAL

1. **OAuth de Google Calendar sin autenticación y con `state` sin firmar.**
   - `GET /auth/google/calendar/url` no tiene dependencia de auth y toma `workspace_id` de la query (`BE/api/routes/auth.py:169-172`).
   - `GET /auth/google/callback` es público (`auth.py:198-202`). Toma `workspace_id` del `state` JSON sin firma ni ligadura a sesión (`:207-217`), y hace `INSERT … ON CONFLICT DO UPDATE` del refresh token (`:222-228`).
   - Un atacante puede completar OAuth con su propia cuenta de Google y un `state` con el `workspace_id` de otra persona. Eso reemplaza el calendario de la víctima por el del atacante.
   - No se probó el flujo; está inferido del código leído.
   - El front lo llama en `FE/lib/api/auth.ts:34-38`, `settings.tsx:212` y `onboarding.tsx:293`.

### HIGH

1. **`require_workspace_access("owner")` siempre da 403.**
   - `"owner"` no está en `ROLE_HIERARCHY` (`BE/core/security.py:19-26`). `require_role` lo trata como 999 (`:79`).
   - Afecta a `GET /billing/workspaces/{id}/subscription` (`billing.py:61`), `DELETE /services/{id}` (`services.py:155`) y `POST`/`DELETE /workspaces/{id}/members` (`workspaces.py:125,155`).
   - Bloquea spec 002 FR-003 (desactivar servicio) y FR-011 (ver suscripción). Los contratos usan los nombres `owner` y `workspace_owner` de forma mezclada (`specs/001/.../workspaces.md:10,106,129`).
2. **Conectar WhatsApp desde Ajustes está roto** por la falta de `Authorization` (`settings.tsx:101-105`). Hay que usar `apiFetch` o enviar el token. El botón "Conectar" es la acción central del PRD General §9.
3. **Datos falsos presentados como reales.**
   - Estado de WhatsApp y Calendar en dashboard y topbar (`dashboard.tsx:264-272`, `_authenticated.tsx:183-186`).
   - Historial de citas inventado en cada cliente (`clients.tsx:65-70`).
   - KPIs de ingresos, automatización y respuesta, panel del agente y alertas (`dashboard.tsx:174,193-195,102-150,246-255`).
   - "Prueba el agente" estática en el onboarding (`onboarding.tsx:434-448`).
4. **Navegación móvil incompleta.**
   - BottomTabs solo usa `NAV[0]` (`_authenticated.tsx:195`) y el Sidebar se oculta en móvil (`:268`).
   - Resultado: sin acceso a Conversaciones, Ajustes (donde se conecta WhatsApp y Calendar) ni Cerrar sesión.
   - Además, en `/messages` no hay botón de volver del detalle a la lista (`messages.tsx:182-188,122-136`).
5. **La landing no enlaza a las páginas legales.** `href="#"` en `index.tsx:348`. Signup no pide aceptar términos (`signup.tsx:150-204`). Las políticas existen pero no están en el flujo de registro.
6. **Faltan funciones centrales de la agenda.** Crear, mover, cancelar y bloquear no tienen UI (`agenda.tsx:251-252`; bloques sin `onClick` en `:80-100`), aunque el backend sí expone los endpoints (`appointments.py:56,179,268`). Era el alcance de PRD FE §6, y el brief de esta auditoría los marca como acciones de la vista.
7. **Switch de activo en la tarjeta de servicio no persiste** (`services.tsx:136,148`). El dueño cree haber desactivado un servicio que el agente seguirá ofreciendo.
8. **Divergencia con spec 002 FR-001.** El spec pide el SDK de Supabase como gestor de sesión; el front usa solo el JWT propio en `localStorage` (`auth-context.tsx:1,16`), con guard que no verifica la firma (`_authenticated.tsx:14-28`). El token vive en `localStorage`, expuesto a XSS, y el "refresh" del backend no consulta la BD (`BE auth.py:133-156`).

### MEDIUM

1. Verify-email: el botón dice "Correo reenviado" sin enviar nada (`verify-email.tsx:18-21,79`). La ruta es inalcanzable.
2. Login y Signup muestran "Continuar con Google" (y Facebook) que siempre fallan con error (`auth-context.tsx:161-167`). Mejor ocultarlos.
3. "¿Olvidaste tu contraseña?" no hace nada y no hay endpoint (`login.tsx:122`).
4. Onboarding traga errores al guardar el paso 0 y avanza (`onboarding.tsx:556-557`). Ciudad y Tono no se guardan (`:105,89`).
5. Onboarding "Horarios de atención sugeridos" no se persiste (`:407-426`) y no hay endpoint de disponibilidad.
6. Ajustes: sin estado de error en canales y calendarios; un fallo parece "sin canal conectado" (`settings.tsx:64-68,203-207,169,256`). Falta el desconectar calendario (`channels.ts:22` sin uso).
7. Servicios: "Nuevo servicio" crea un registro con valores fijos en vez de abrir formulario (`services.tsx:219-227`). `ServiceFormDialog` quedó sin uso.
8. Mensajes: sin estado de error al cargar mensajes (`messages.tsx:123`). No muestra intención, estado, alertas ni acciones del agente (PRD FE §9).
9. Agenda: la vista Día ignora la semana navegada (`agenda.tsx:113`); la vista Semana no tiene estado vacío; el Mes es de relleno (`:168-204`).
10. Sin guard de rol en el front: staff y viewer ven los botones de Ajustes que el backend rechaza con 403 (`channels.py:80,127,230,270`).
11. `useCustomers` baja todas las citas sin filtro de fechas (`use-customers.ts:25`); `/messages` también, solo para resolver nombres. No escala.
12. PRD FE §4 pide Canales, Calendarios, Equipo y Suscripción. Las cuatro entradas del sidebar son "pronto" y los endpoints de miembros, billing y bloques no tienen consumidor.
13. La barra de progreso de onboarding es fija (75%) y no se persiste el avance (`_authenticated.tsx:272,144`).
14. `GET /workspaces/{id}` falla en silencio y cae a datos demo (`_authenticated.tsx:239-247`, `settings.tsx:347-350`, `onboarding.tsx:462-463`).

### LOW

1. Un usuario autenticado puede abrir `/login` y `/signup` (sin `beforeLoad`).
2. No hay `notFoundComponent` ni `errorComponent`.
3. Saludo "Camilo" y ciudad fijos (`dashboard.tsx:180-182`).
4. El buscador ⌘K y la campana de alertas no hacen nada (`_authenticated.tsx:171-187`).
5. "Escribir" por WhatsApp en clientes sin acción (`clients.tsx:87-89`).
6. Hook `useIsMobile` en el layout agrega un listener `resize` en cada render (`_authenticated.tsx:57-63`). Es una fuga de listeners.
7. Cerrar sesión es un icono `dotsV` sin etiqueta (`_authenticated.tsx:153`), y el botón de reconectar es un icono sync sin `aria-label` (`settings.tsx:161,251`).
8. Los bloques de cita no muestran el profesional (`pro:''`, `use-appointments.ts:104`) y la cuadrícula fija de 9 a 19 h (`agenda.tsx:17`) ignora el horario real.
9. `WorkspacePatch` incluye `primary_phone` y `timezone` (`workspaces.ts:5-10`), que ninguna vista envía.
10. Código muerto: `app-sidebar.tsx`, `app-header.tsx`, `service-form-dialog.tsx`, `weekly-calendar.tsx`, `kpi-card.tsx`, `useDeactivateService`, `useUpdateAppointment`, `getSubscription`, `listPlans`, `getAppointment`, `getCustomer`, `getConversation`, `getService`.
11. `CORS allow_origins=["*"]` junto con `allow_credentials=True` (`BE/api/main.py:66-72`). Fuera del alcance de las vistas, pero afecta al panel.

---

## 6. Endpoints del backend sin consumidor en el front

Los webhooks (`webhooks.py:76,98,232,279,379`) los consumen Meta, Kapso y Google, no el front. Se excluyen.

| Endpoint | Archivo:línea | Observación |
|---|---|---|
| `POST /workspaces/{id}/appointments` | `appointments.py:56` | Sin wrapper en `lib/api`. |
| `GET /workspaces/{id}/appointments/{id}` | `appointments.py:159` | Wrapper `getAppointment` sin uso. |
| `PATCH /workspaces/{id}/appointments/{id}` | `appointments.py:179` | Wrapper y hook `useUpdateAppointment` sin uso en vistas. |
| `GET`, `POST`, `DELETE /workspaces/{id}/blocks[/{id}]` | `appointments.py:252,268,310` | Sin wrapper. |
| `GET /billing/plans` | `billing.py:47` | `listPlans` sin uso; la landing no lo consume. |
| `GET /billing/workspaces/{id}/subscription` | `billing.py:57` | `getSubscription` sin uso (y 403, HIGH-1). |
| `PATCH /billing/workspaces/{id}/subscription/status` | `billing.py:76` | Sin wrapper (super_admin). |
| `POST /workspaces/{id}/channels` | `channels.py:37` | Sin wrapper. |
| `POST /workspaces/{id}/calendars` | `channels.py:225` | Sin wrapper (el alta real pasa por `/auth/google/callback`). |
| `DELETE /workspaces/{id}/calendars/{id}` | `channels.py:266` | `disconnectCalendar` sin uso. |
| `GET /workspaces/{id}/customers/{id}` | `conversations.py:37` | `getCustomer` sin uso. |
| `GET /workspaces/{id}/conversations/{id}` | `conversations.py:118` | `getConversation` sin uso. |
| `GET /workspaces/{id}/services/{id}` | `services.py:79` | `getService` sin uso. |
| `DELETE /workspaces/{id}/services/{id}` | `services.py:151` | `deactivateService` y `useDeactivateService` sin uso (y 403). |
| `POST /workspaces/` | `workspaces.py:21` | Sin consumidor (el registro crea el workspace). |
| `GET`, `POST`, `DELETE /workspaces/{id}/members[/{id}]` | `workspaces.py:104,120,151` | Sin consumidor. No hay pantalla de equipo. |
| `POST /workspaces/{id}/kapso/onboarding-link` | `kapso.py:27` | Sin consumidor. |

El resto sí se consume: `/auth/login`, `/auth/register`, `/auth/refresh`, `/auth/me`, `/auth/google/*`, `GET /workspaces/{id}`, `PATCH /workspaces/{id}`, `GET|POST|PATCH services`, `GET appointments`, `GET|PATCH customers`, `GET conversations`, `GET messages`, `GET channels`, `PATCH channels/{id}/status`, `POST channels/embedded-signup`, `GET calendars`.

## 7. Llamadas del front a endpoints inexistentes o con contrato distinto

**Ninguna llamada apunta a una ruta inexistente.** Se compararon los 24 wrappers y los `apiFetch` directos de `FE/lib/api/*.ts`, `FE/routes/*` y `FE/hooks/*` con las rutas de `BE/api/routes/*.py`. Los nombres de query params coinciden: `status`, `from_date` y `to_date` (`appointments.py`), `new_status` (`channels.py:76`) y `return_to` (`auth.py:170`).

Contratos con problema:

| Llamada | Problema | Archivo:línea |
|---|---|---|
| `POST /workspaces/{id}/channels/embedded-signup` desde Ajustes | Sin `Authorization`; el backend lo exige. ROTO. | `settings.tsx:101-105` vs `channels.py:118-127` |
| `GET /auth/google/calendar/url` | El front envía Bearer (vía `apiFetch`) pero el backend no lo valida ni comprueba que el `workspace_id` sea del usuario. Contrato más débil que el esperado. | `auth.ts:34-38` vs `auth.py:169-172` |
| `DELETE /services/{id}`, `GET /billing/.../subscription` | El contrato `workspace_owner` / `owner` no coincide con `ROLE_HIERARCHY`; siempre 403. | `services.py:155`, `billing.py:61` |
| `PATCH /workspaces/{id}` desde Onboarding | Ciudad y tono no existen en `WorkspaceUpdate`; el front tampoco los envía. | `workspace.py:20-29`, `onboarding.tsx:551-554` |
| `POST /auth/refresh` | El front manda el JWT propio como `refresh_token`. Coincide con `RefreshRequest`, pero el nombre del campo y el doc de spec 002 hablan de Supabase. | `auth.ts:18-24`, `auth.py:133-156`, `specs/002 FR-001` |
| `PATCH /workspaces/{id}` | Exige `manager`. Para `staff` y `viewer` el botón "Guardar" da 403 sin guard previo. | `workspaces.py:77`, `settings.tsx:419` |

No verificado: los campos de `AppointmentOut`, `ServiceOut`, `ConversationOut`, `MessageOut` y `BillingPlanOut` contra `FE/lib/types/api.ts`. Solo se comprobaron `ChannelOut`, `CustomerUpdate`, `MeResponse` y la existencia de `price_cop` en `BE/schemas/appointment.py:39`.

---

## 8. Pendiente / no verificado

- Contenido de la landing: precios, textos y claims. Solo se revisaron enlaces y acciones.
- Variables de entorno de Meta (`VITE_META_APP_ID`, `VITE_META_EMBEDDED_SIGNUP_CONFIG_ID`) en `settings.tsx:37,119` y `onboarding.tsx:257`. Se citan solo por nombre; no se leyó ningún `.env`.
- Persistencia de la tipografía (`FE/lib/typography-context`).
- Comparación visual con `html/Hilo*.html` y `html/hilo/*.jsx`: solo estructura de navegación. En `html/hilo/shell.jsx:99-106` "Conversaciones" y "Configuración" figuran como `soon:true`, mientras el front ya los tiene activos. No se compararon colores ni espaciados.
- No se leyó `webhooks.py` ni `appointments.py` en detalle; el comportamiento de sus handlers no forma parte de esta auditoría de vistas.
- El flujo OAuth de CRITICAL-1 y la colisión de slug en `/auth/register` se infirieron del código, sin ejecutar nada.
