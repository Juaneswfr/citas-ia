// T004 — Tipos TypeScript espejo de los schemas Pydantic del backend

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  workspace_id?: string; // presente en /auth/register
}

export interface MeResponse {
  user_id: string;
  email: string;
  role: string; // 'workspace_owner' | 'manager' | 'staff' | 'viewer'
  workspace_id: string;
}

// ── Workspace ─────────────────────────────────────────────────────────────────

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
  business_type: string | null;
  created_at: string;
  updated_at: string;
}

// ── Services ──────────────────────────────────────────────────────────────────

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

// ── Appointments ──────────────────────────────────────────────────────────────

export type AppointmentStatus =
  | 'pending'
  | 'confirmed'
  | 'cancelled'
  | 'completed'
  | 'noshow'
  | 'rescheduled';

export interface AppointmentOut {
  id: string;
  workspace_id: string;
  customer_id: string;
  service_id: string;
  channel_id: string;
  calendar_id: string;
  start_at: string; // ISO 8601
  end_at: string;   // ISO 8601
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

// ── Customers ─────────────────────────────────────────────────────────────────

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

// ── Conversations ─────────────────────────────────────────────────────────────

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

// ── Channels & Calendars ──────────────────────────────────────────────────────

export interface ChannelOut {
  id: string;
  workspace_id: string;
  channel_type: string;
  provider: string;
  phone_number: string;
  phone_number_id?: string;
  display_name: string | null;
  status: string; // 'active' | 'paused' | 'disconnected'
  coexistence_enabled: boolean;
  external_account_id: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface MemberOut {
  id: string;
  workspace_id: string;
  user_id: string;
  member_role: string;
  status: string;
  joined_at: string | null;
  created_at: string;
  name: string | null;
  email: string | null;
}

export interface BusinessHoursOut {
  day_of_week: number;   // 0=Lunes … 6=Domingo
  open_time: string;     // "HH:MM"
  close_time: string;
  is_open: boolean;
}

export interface AppointmentCreate {
  customer_id: string;
  service_id: string;
  channel_id: string;
  calendar_id: string;
  start_at: string;             // ISO 8601 with timezone
  price_cop: number;
  is_home_service?: boolean;
  home_address?: string;
  home_service_price_cop?: number;
}

export interface CalendarOut {
  id: string;
  workspace_id: string;
  name: string;
  google_calendar_id: string;
  connected_by_user_id: string | null;
  sync_enabled: boolean;
  sync_status: string; // 'active' | 'disconnected' | 'error'
  last_synced_at: string | null;
  created_at: string;
  updated_at: string;
}

// ── Billing ───────────────────────────────────────────────────────────────────

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
