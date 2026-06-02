# Research: Frontend API Services Integration

**Feature**: `002-frontend-api-services` | **Phase**: 0 — Completed 2026-06-01

## Technology Decisions

### 1. API Client base

**Decision**: Wrapper nativo sobre `fetch` (sin librería adicional como axios)  
**Rationale**: TanStack Start ya incluye `fetch` polyfilled. Un wrapper ligero que añade el header `Authorization: Bearer <jwt>`, el `Content-Type` y serialización JSON es suficiente. Evita añadir dependencias cuando el proyecto ya tiene React Query para caché y refetch.  
**Alternatives considered**: `axios` (más features pero ~14KB extra, ya no necesario con fetch moderno); `ofetch` (buena API pero otra dependencia innecesaria).  
**Implementation**: `lib/api/client.ts` — función `apiFetch(path, options)` que lee el JWT del contexto de auth y lo adjunta automáticamente.

---

### 2. Gestión del ciclo de vida de sesión

**Decision**: Supabase JS SDK para el ciclo completo (login, refresh automático, logout); JWT del backend obtenido en el login y almacenado en contexto de React  
**Rationale**: El SDK de Supabase gestiona el refresh automático del token de Supabase (que expira en 1h y se renueva con refresh_token almacenado por el SDK en localStorage). El backend JWT se obtiene llamando `POST /auth/login` con las mismas credenciales justo después del login de Supabase. El backend JWT se guarda en React Context (memoria), no en localStorage, para minimizar superficie de ataque.  
**Lifecycle**: `supabase.auth.signIn()` → `POST /auth/login` → almacenar JWT en contexto → `GET /auth/me` → poblar perfil de usuario.  
**Token refresh**: Cuando el backend JWT de 1h expira, el SDK de Supabase ya habrá renovado la sesión de Supabase; el frontend solicita un nuevo backend JWT con `POST /auth/login` usando `supabase.auth.getSession()` para obtener las credenciales actualizadas.  
**Alternatives considered**: Almacenar backend JWT en localStorage (más simple pero mayor superficie de ataque XSS); usar `/auth/refresh` del backend (requeriría que el login retorne el Supabase refresh_token, lo cual no hace actualmente).

---

### 3. State management y data fetching

**Decision**: TanStack React Query v5 para todas las llamadas al backend  
**Rationale**: Ya está en el proyecto (`@tanstack/react-query ^5.83.0`). Provee caché automático, invalidación por mutation, estados de loading/error/success, y `staleTime` configurable. Los hooks encapsulan la lógica de llamada y proveen las interfaces de tipo.  
**Query keys**: `['services', workspaceId]`, `['appointments', workspaceId, filters]`, `['customers', workspaceId]`, `['conversations', workspaceId]`.  
**Alternatives considered**: SWR (similar pero React Query tiene mejor integración con mutations y más comunidad en TanStack ecosystem); Zustand con fetch manual (más control pero más boilerplate).

---

### 4. Estrategia de adaptadores (backend schemas → UI types)

**Decision**: Capa de adaptadores en `lib/api/adapters.ts` que convierte `ServiceOut` → `HiloService`, `AppointmentOut` → `HiloAppointment`, etc.  
**Rationale**: Los componentes visuales actuales usan tipos Hilo (`HiloService`, `HiloAppointment`) con nombres de campo propios del UI (`dur`, `buffer`, `price`, `home`, `extra`). Cambiar los componentes viola la restricción SC-004. Los adaptadores desacoplan el contrato del backend del contrato del UI.  
**Mapping clave**:
- `duration_minutes` → `dur`
- `buffer_minutes` → `buffer`  
- `price_cop` → `price`
- `home_service_enabled` → `home`
- `home_service_extra_price_cop` → `extra`
- `is_active` → `active`
- `start_at` ISO → `time` / `end` strings formateados
- `status` backend → `status` UI (mapping: `confirmed`→`confirmada`, `pending`→`pendiente`, `cancelled`→`cancelada`)  
**Alternatives considered**: Modificar los componentes para usar tipos del backend directamente (viola SC-004 — cambio visual y de prop types visible en desarrollo).

---

### 5. Estados de carga

**Decision**: Client-side loading con skeleton/spinner discreto usando la infraestructura CSS variable existente (`--line`, `--surface`, animación CSS)  
**Rationale**: El usuario respondió Opción B. La UI de Hilo ya tiene variables CSS como `--surface`, `--line-strong` que permiten crear placeholders de skeleton sin añadir librerías. Los componentes que renderizan listas/tarjetas muestran un layout idéntico con shimmer animation mientras cargan.  
**Pattern**: Pasar `isLoading` al componente → renderiza estructura idéntica con placeholder content; `isError` → toast de error via Sonner (ya incluido en el proyecto).  
**Alternatives considered**: Suspense + Server loaders (Opción A, rechazada); `react-loading-skeleton` (dependencia extra innecesaria cuando CSS puede hacerlo).

---

### 6. Manejo de errores

**Decision**: Error boundary en `_authenticated.tsx` + toasts de Sonner para errores de mutación + estados de error en-page para fetch fallido  
**Rationale**: Sonner (`sonner ^2.0.7`) ya está instalado. Los errores de mutación (guardar servicio, actualizar cliente) se muestran como toast. Los errores de fetch (lista de citas no carga) se muestran en el lugar de la lista con un mensaje en lugar de un crash.  
**HTTP error mapping**:
- 401: redirect a login (sesión expirada)
- 403: toast "No tienes permisos para esta acción"
- 404: estado vacío (no hay datos)
- 409: toast con mensaje específico del backend (ej: "Horario no disponible")
- 422: toast con el primer error de validación del backend
- 5xx: toast genérico "Error del servidor, intenta de nuevo"

---

### 7. Variables de entorno

**Decision**: `VITE_API_URL` para el client-side; leída una vez en `lib/api/client.ts`  
**Rationale**: Vite expone variables `VITE_*` al bundle del cliente via `import.meta.env.VITE_API_URL`. No contiene secretos (solo la URL base). El servidor de TanStack Start puede leerlo también via `process.env`.  
**Development default**: `http://localhost:8000` si `VITE_API_URL` no está definido.

---

### 8. Workspace ID

**Decision**: Extraído del JWT del backend vía `GET /auth/me` response (`workspace_id`), almacenado en el contexto de autenticación  
**Rationale**: El backend ya incluye `workspace_id` en el payload del JWT y lo retorna en `GET /auth/me`. El frontend lo lee una vez al iniciar sesión y lo pasa a todas las llamadas como path param. Un usuario tiene un único workspace en MVP.  
**Alternatives considered**: Extraer el workspace_id del JWT en el cliente (requiere parsear el JWT — añade complejidad y duplica lógica que ya hace `/auth/me`).
