// Tipos del panel de administración de la plataforma (espejo de backend-lang/src/schemas/admin.py).

export interface CountByKey {
  key: string;
  count: number;
}

export interface WeeklySignups {
  week_start: string;
  count: number;
}

export interface AdminOverview {
  workspaces_total: number;
  workspaces_active: number;
  workspaces_new_30d: number;
  users_total: number;
  channels_active: number;
  appointments_30d: number;
  messages_30d: number;
  by_business_type: CountByKey[];
  by_subscription_status: CountByKey[];
  signups_by_week: WeeklySignups[];
}

export interface AdminWorkspaceRow {
  id: string;
  name: string;
  slug: string;
  business_type: string | null;
  is_active: boolean;
  timezone: string;
  created_at: string;
  owner_email: string | null;
  plan_name: string | null;
  subscription_status: string | null;
  members: number;
  channels_active: number;
  appointments_30d: number;
  last_message_at: string | null;
}

export interface AdminWorkspaceList {
  items: AdminWorkspaceRow[];
  total: number;
}

export interface AdminMember {
  user_id: string;
  name: string | null;
  email: string;
  member_role: string;
  status: string;
}

export interface AdminChannel {
  id: string;
  provider: string;
  phone_number: string;
  display_name: string | null;
  status: string;
}

export interface AdminCalendar {
  id: string;
  name: string;
  sync_status: string;
}

export interface AdminWorkspaceDetail {
  workspace: AdminWorkspaceRow;
  members: AdminMember[];
  channels: AdminChannel[];
  calendars: AdminCalendar[];
  counts: { services: number; customers: number; appointments: number };
}

export interface AdminWorkspaceUpdate {
  is_active?: boolean;
  business_type?: string;
}

export interface AdminWorkspaceFilters {
  search: string;
  businessType: string;
  /** '' = todos, 'active' = activos, 'suspended' = suspendidos. */
  status: '' | 'active' | 'suspended';
}

export type HealthStatus = 'ok' | 'warn' | 'bad';

export interface HealthCheck {
  id: string;
  label: string;
  status: HealthStatus;
  detail: string;
  latency_ms: number | null;
  action_url: string | null;
}

export interface HealthNumber {
  channel_id: string;
  workspace_name: string;
  phone_number: string;
  status: HealthStatus;
  detail: string;
}

export interface HealthError {
  id: string;
  severity: string;
  reason: string | null;
  created_at: string;
  workspace_name: string;
}

export interface AdminHealth {
  checks: HealthCheck[];
  numbers: HealthNumber[];
  activity: {
    inbound_24h: number;
    outbound_24h: number;
    last_inbound_at: string | null;
    last_outbound_at: string | null;
    runs_ok_24h: number;
    runs_error_24h: number;
    unanswered_24h: number;
    recent_errors: HealthError[];
  };
}

export interface AdminUserRow {
  id: string;
  email: string;
  name: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
  workspace_id: string | null;
  workspace_name: string | null;
}

export interface AdminUserList {
  items: AdminUserRow[];
  total: number;
}
