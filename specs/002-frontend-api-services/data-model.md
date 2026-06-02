# Data Model: Frontend API Services

**Feature**: `002-frontend-api-services` | **Phase**: 1 — 2026-06-01

Este documento describe los tipos TypeScript del frontend — los tipos del backend (fuente de verdad)
y los tipos de UI Hilo (usados por los componentes), más los adaptadores que los conectan.

---

## Backend Response Types (espejo de schemas Pydantic del backend)

Estos tipos reflejan exactamente lo que el backend retorna. Viven en `lib/types/api.ts`.

```typescript
// auth
export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface MeResponse {
  user_id: string;
  email: string;
  role: string;           // 'workspace_owner' | 'manager' | 'staff' | 'viewer'
  workspace_id: string;
}

// workspace
export interface WorkspaceOut {
  id: string;
  name: string;
  slug: string;
  country: string;
  timezone: string;
  primary_phone: string | null;
  primary_email: string | null;
  brand_color: string | null;
  logo_url: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// services
export interface ServiceOut {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  duration_minutes: number;
  buffer_minutes: number;
  price_cop: number;
  home_service_enabled: boolean;
  home_service_extra_minutes: number;
  home_service_extra_price_cop: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ServiceCreate {
  name: string;
  description?: string;
  duration_minutes: number;
  buffer_minutes?: number;
  price_cop: number;
  home_service_enabled?: boolean;
  home_service_extra_minutes?: number;
  home_service_extra_price_cop?: number;
}

export interface ServiceUpdate {
  name?: string;
  description?: string;
  duration_minutes?: number;
  buffer_minutes?: number;
  price_cop?: number;
  home_service_enabled?: boolean;
  home_service_extra_minutes?: number;
  home_service_extra_price_cop?: number;
  is_active?: boolean;
}

// appointments
export type AppointmentStatus = 'pending' | 'confirmed' | 'cancelled' | 'completed' | 'noshow' | 'rescheduled';

export interface AppointmentOut {
  id: string;
  workspace_id: string;
  customer_id: string;
  service_id: string;
  channel_id: string;
  calendar_id: string;
  start_at: string;   // ISO 8601
  end_at: string;     // ISO 8601
  status: AppointmentStatus;
  price_cop: number;
  home_service_price_cop: number;
  is_home_service: boolean;
  home_address: string | null;
  google_event_id: string | null;
  cancellation_reason: string | null;
  cancelled_by: string | null;
  created_by: string | null;
  confirmed_at: string | null;
  cancelled_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AppointmentUpdate {
  start_at?: string;
  status?: AppointmentStatus;
  cancellation_reason?: string;
}

// customers
export interface CustomerOut {
  id: string;
  workspace_id: string;
  phone: string;
  name: string | null;
  email: string | null;
  notes: string | null;
  last_seen_at: string | null;
  source_channel_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CustomerUpdate {
  name?: string;
  email?: string;
  notes?: string;
}

// conversations
export interface ConversationOut {
  id: string;
  workspace_id: string;
  channel_id: string;
  customer_id: string;
  status: string;
  current_intent: string | null;
  last_message_at: string | null;
  last_agent_state: string | null;
  needs_review: boolean;
  created_at: string;
  updated_at: string;
}

export interface MessageOut {
  id: string;
  workspace_id: string;
  conversation_id: string;
  channel_id: string;
  customer_id: string | null;
  direction: 'inbound' | 'outbound';
  sender_type: 'customer' | 'agent' | 'system';
  message_type: string;
  content: string | null;
  media_url: string | null;
  provider_message_id: string | null;
  status: string;
  sent_at: string | null;
  received_at: string | null;
  created_at: string;
}

// billing
export interface BillingPlanOut {
  id: string;
  name: string;
  description: string | null;
  price_cop: number;
  billing_interval: string;
  max_channels: number;
  max_calendars: number;
  max_services: number;
  max_messages: number;
  is_active: boolean;
  created_at: string;
}

export interface SubscriptionOut {
  id: string;
  workspace_id: string;
  billing_plan_id: string;
  status: string;
  payment_method: string | null;
  paid_this_month: boolean;
  current_period_start: string | null;
  current_period_end: string | null;
  next_billing_date: string | null;
  created_at: string;
  updated_at: string;
}
```

---

## UI Types (Hilo) — preservados sin cambios

Estos tipos viven en `lib/hilo-data.ts` y `lib/mock-data.ts`. Los componentes los consumen directamente.
**No se modifican** — los adaptadores convierten backend types a estos.

```typescript
// HiloService (lib/hilo-data.ts)
interface HiloService {
  id: string; name: string; dur: number; buffer: number; price: number;
  home: boolean; extra: number; active: boolean; hue: ServiceHue;
  pros: string[]; book: number;
}

// HiloAppointment (lib/hilo-data.ts)
interface HiloAppointment {
  id: string; time: string; end: string; client: string;
  svc: string; pro: string; status: AppointmentStatus;
  via: 'wa' | 'manual'; phone: string; home?: boolean;
}

// HiloClient (lib/hilo-data.ts)
interface HiloClient {
  id: string; name: string; phone: string; last: string; next: string;
  visits: number; fav: string; spend: number;
  status: 'VIP' | 'frecuente' | 'activo' | 'nuevo'; note: string;
}
```

---

## Adaptadores: Backend → UI

Viven en `lib/api/adapters.ts`.

### ServiceOut → HiloService

| Backend campo | UI campo | Transformación |
|---------------|----------|----------------|
| `id` | `id` | directo |
| `name` | `name` | directo |
| `duration_minutes` | `dur` | directo |
| `buffer_minutes` | `buffer` | directo |
| `price_cop` | `price` | directo |
| `home_service_enabled` | `home` | directo |
| `home_service_extra_price_cop` | `extra` | directo |
| `is_active` | `active` | directo |
| `hue` | `hue` | derivado por índice de posición en lista (hues: clay/wine/mustard/steel/sage/plum) |
| `pros` | `pros` | `[]` vacío (no hay equipo en v1) |
| `book` | `book` | `0` (no hay contador de bookings en v1) |

### AppointmentOut → HiloAppointment

| Backend campo | UI campo | Transformación |
|---------------|----------|----------------|
| `id` | `id` | directo |
| `start_at` | `time` | `format(start_at, 'HH:mm')` |
| `end_at` | `end` | `format(end_at, 'HH:mm')` |
| `customer_id` | `client` | lookup de CustomerOut.name o phone |
| `service_id` | `svc` | lookup de ServiceOut.name |
| `status` | `status` | `confirmed→done/next/now/upcoming`, `pending→upcoming`, `cancelled→done` |
| `is_home_service` | `home` | directo |
| — | `via` | `'wa'` por defecto (origen WhatsApp) |
| — | `pro` | `''` (sin asignación de barbero en v1) |
| — | `phone` | lookup de CustomerOut.phone |

### CustomerOut → HiloClient

| Backend campo | UI campo | Transformación |
|---------------|----------|----------------|
| `id` | `id` | directo |
| `name` | `name` | `name ?? phone` |
| `phone` | `phone` | directo |
| `last_seen_at` | `last` | `formatDistanceToNow(last_seen_at)` |
| — | `next` | lookup de próxima cita activa |
| — | `visits` | count de appointments del customer |
| — | `fav` | servicio más repetido |
| — | `spend` | suma de `price_cop` de appointments completadas |
| — | `status` | derivado de `visits`: ≥10→VIP, ≥5→frecuente, ≥1→activo, 0→nuevo |
| `notes` | `note` | directo |

---

## Auth Context State

El contexto de autenticación actualizado (`lib/auth-context.tsx`) almacena:

```typescript
interface AuthState {
  supabaseSession: Session | null;    // sesión Supabase SDK
  backendJwt: string | null;          // JWT del backend (memory only)
  me: MeResponse | null;              // user_id, email, role, workspace_id
}
```

El `workspace_id` se accede siempre como `me.workspace_id` en todas las llamadas de API.
