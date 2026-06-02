# Contracts: Frontend API Service Layer

**Feature**: `002-frontend-api-services`  
**Backend contracts (fuente de verdad)**: `specs/001-db-and-endpoints/contracts/`

Este documento define las funciones y hooks que el frontend expone internamente.
Los contratos del backend REST no se repiten aquí — ver `001-db-and-endpoints/contracts/`.

---

## lib/api/client.ts — API Client base

```typescript
/** Opciones para apiFetch */
interface ApiFetchOptions extends RequestInit {
  /** Si true, omite el header Authorization (para endpoints públicos) */
  public?: boolean;
}

/**
 * Wrapper sobre fetch que añade:
 * - Base URL desde import.meta.env.VITE_API_URL
 * - Header Authorization: Bearer <backendJwt>
 * - Content-Type: application/json
 * - Lanza ApiError con status y mensaje del backend en caso de error HTTP
 */
export async function apiFetch<T>(path: string, options?: ApiFetchOptions): Promise<T>

/** Error tipado para respuestas HTTP del backend */
export class ApiError extends Error {
  status: number;
  detail: string;
}
```

---

## lib/api/auth.ts

```typescript
/** POST /auth/login — obtiene JWT del backend */
export async function loginToBackend(email: string, password: string): Promise<TokenResponse>

/** GET /auth/me — datos del usuario autenticado (requiere JWT) */
export async function getMe(): Promise<MeResponse>
```

---

## lib/api/services.ts

```typescript
/** GET /workspaces/{workspaceId}/services */
export async function listServices(workspaceId: string, activeOnly?: boolean): Promise<ServiceOut[]>

/** GET /workspaces/{workspaceId}/services/{serviceId} */
export async function getService(workspaceId: string, serviceId: string): Promise<ServiceOut>

/** POST /workspaces/{workspaceId}/services */
export async function createService(workspaceId: string, body: ServiceCreate): Promise<ServiceOut>

/** PATCH /workspaces/{workspaceId}/services/{serviceId} */
export async function updateService(workspaceId: string, serviceId: string, body: ServiceUpdate): Promise<ServiceOut>

/** DELETE /workspaces/{workspaceId}/services/{serviceId} — soft delete */
export async function deactivateService(workspaceId: string, serviceId: string): Promise<void>
```

---

## lib/api/appointments.ts

```typescript
interface ListAppointmentsParams {
  status?: AppointmentStatus;
  from_date?: string;   // ISO date
  to_date?: string;     // ISO date
}

/** GET /workspaces/{workspaceId}/appointments */
export async function listAppointments(workspaceId: string, params?: ListAppointmentsParams): Promise<AppointmentOut[]>

/** GET /workspaces/{workspaceId}/appointments/{appointmentId} */
export async function getAppointment(workspaceId: string, appointmentId: string): Promise<AppointmentOut>

/**
 * PATCH /workspaces/{workspaceId}/appointments/{appointmentId}
 * Para cancelar: body.status = 'cancelled' + confirmed = true
 */
export async function updateAppointment(
  workspaceId: string,
  appointmentId: string,
  body: AppointmentUpdate,
  confirmed?: boolean
): Promise<AppointmentOut>
```

---

## lib/api/conversations.ts

```typescript
/** GET /workspaces/{workspaceId}/customers */
export async function listCustomers(workspaceId: string): Promise<CustomerOut[]>

/** GET /workspaces/{workspaceId}/customers/{customerId} */
export async function getCustomer(workspaceId: string, customerId: string): Promise<CustomerOut>

/** PATCH /workspaces/{workspaceId}/customers/{customerId} */
export async function updateCustomer(workspaceId: string, customerId: string, body: CustomerUpdate): Promise<CustomerOut>

/** GET /workspaces/{workspaceId}/conversations */
export async function listConversations(workspaceId: string, status?: string): Promise<ConversationOut[]>

/** GET /workspaces/{workspaceId}/conversations/{conversationId} */
export async function getConversation(workspaceId: string, conversationId: string): Promise<ConversationOut>

/** GET /workspaces/{workspaceId}/conversations/{conversationId}/messages */
export async function listMessages(workspaceId: string, conversationId: string): Promise<MessageOut[]>
```

---

## lib/api/billing.ts

```typescript
/** GET /billing/plans — público */
export async function listPlans(): Promise<BillingPlanOut[]>

/** GET /billing/workspaces/{workspaceId}/subscription */
export async function getSubscription(workspaceId: string): Promise<SubscriptionOut>
```

---

## lib/api/adapters.ts

```typescript
/** ServiceOut → HiloService */
export function toHiloService(svc: ServiceOut, index: number): HiloService

/** AppointmentOut → HiloAppointment (requiere lookup de customer y service) */
export function toHiloAppointment(
  apt: AppointmentOut,
  customers: Map<string, CustomerOut>,
  services: Map<string, ServiceOut>
): HiloAppointment

/** CustomerOut → HiloClient (requiere appointments para derivar visitas, fav, spend, next) */
export function toHiloClient(
  customer: CustomerOut,
  appointments: AppointmentOut[]
): HiloClient
```

---

## lib/hooks/use-services.ts

```typescript
/** React Query hook — lista servicios del workspace */
export function useServices(activeOnly?: boolean): UseQueryResult<HiloService[]>

/** React Query hook — servicio individual */
export function useService(serviceId: string): UseQueryResult<HiloService>

/** React Query mutation — crear servicio */
export function useCreateService(): UseMutationResult<HiloService, ApiError, ServiceCreate>

/** React Query mutation — actualizar servicio */
export function useUpdateService(serviceId: string): UseMutationResult<HiloService, ApiError, ServiceUpdate>

/** React Query mutation — desactivar servicio */
export function useDeactivateService(): UseMutationResult<void, ApiError, string>
```

---

## lib/hooks/use-appointments.ts

```typescript
interface UseAppointmentsOptions {
  status?: AppointmentStatus;
  from_date?: string;
  to_date?: string;
}

/** React Query hook — lista citas (con datos de clientes y servicios enriquecidos) */
export function useAppointments(options?: UseAppointmentsOptions): UseQueryResult<HiloAppointment[]>

/** React Query mutation — actualizar/cancelar cita */
export function useUpdateAppointment(appointmentId: string): UseMutationResult<HiloAppointment, ApiError, { body: AppointmentUpdate; confirmed?: boolean }>
```

---

## lib/hooks/use-customers.ts

```typescript
/** React Query hook — lista clientes */
export function useCustomers(): UseQueryResult<HiloClient[]>

/** React Query hook — cliente individual */
export function useCustomer(customerId: string): UseQueryResult<HiloClient>

/** React Query mutation — actualizar cliente */
export function useUpdateCustomer(customerId: string): UseMutationResult<HiloClient, ApiError, CustomerUpdate>
```

---

## lib/hooks/use-conversations.ts

```typescript
/** React Query hook — lista conversaciones */
export function useConversations(status?: string): UseQueryResult<ConversationOut[]>

/** React Query hook — mensajes de una conversación */
export function useMessages(conversationId: string): UseQueryResult<MessageOut[]>
```

---

## Comportamiento de errores (cross-cutting)

Todos los hooks/mutations invocan `apiFetch` que lanza `ApiError`. Los hooks de React Query
propagan el error a su estado `error`. Las mutations muestran el error via toast de Sonner.

| HTTP Status | Comportamiento |
|-------------|----------------|
| 401 | `useAuth().logout()` + redirect a `/login` |
| 403 | toast: "No tienes permisos para esta acción" |
| 404 | estado vacío (no datos) |
| 409 | toast con `error.detail` del backend |
| 422 | toast con primer mensaje de error de validación |
| 5xx | toast: "Error del servidor, intenta de nuevo" |
| Network error | toast: "Sin conexión, verifica tu red" |
