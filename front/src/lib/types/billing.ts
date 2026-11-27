// Tipos de planes, suscripción y facturación (espejo de backend-lang/src/services/subscription_service.py
// y billing_metrics.py). Los montos van en pesos colombianos.

export type SubscriptionStatus =
  | 'none' | 'trial' | 'active' | 'past_due' | 'paused' | 'cancelled' | 'expired' | 'pending_payment' | 'suspended';

export type InvoiceStatus = 'pending' | 'paid' | 'overdue' | 'void';

export interface BillingInvoice {
  id: string;
  kind: 'cycle' | 'proration';
  period_start: string;
  period_end: string;
  due_date: string;
  amount_cop: number;
  status: InvoiceStatus;
  paid_at: string | null;
  payment_method: string | null;
  payment_reference: string | null;
  document_number: string | null;
  last_sent_at: string | null;
  last_sent_to: string | null;
}

export interface QuotaInfo {
  included: number | null;
  extra: number;
  total: number | null;
  used: number;
  remaining: number | null;
  /** ok → warn (80 %) → over (se acabó, aún agenda dentro del margen) → blocked */
  level: 'ok' | 'warn' | 'over' | 'blocked';
  can_book: boolean;
}

/** GET /billing/workspaces/{id}/summary. Sin `plan` = el negocio no tiene plan asignado (no tiene límites). */
export interface BillingSummary {
  has_subscription: boolean;
  status: SubscriptionStatus;
  serving: boolean;
  plan?: { code: string; name: string; price_cop: number; launch_price_cop: number | null };
  trial_ends_at?: string | null;
  cycle_start?: string;
  cycle_end?: string;
  next_cycle_plan_price_cop?: number | null;
  discount_cycles_remaining?: number;
  is_founder?: boolean;
  founder_number?: number | null;
  cancel_at_period_end?: boolean;
  pending_plan?: string | null;
  /** El nombre del plan pendiente (el código es solo para el sistema). */
  pending_plan_name?: string | null;
  appointments?: QuotaInfo;
  professionals?: { limit: number | null; active: number; extra: number; extra_price_cop: number };
  profile_complete?: boolean;
  invoices?: BillingInvoice[];
}

export interface BillingProfile {
  legal_name: string;
  tax_id: string;
  billing_email: string;
  address: string | null;
}

export interface PlanChangePreview {
  direction: 'up' | 'down';
  from_plan: string;
  to_plan: string;
  applies: 'now' | 'next_cycle';
  effective_date: string;
  charge_now_cop: number;
  next_cycle_price_cop: number;
  keeps_discount_cycles: number;
  blockers: string[];
}

// ── Panel de plataforma ──────────────────────────────────────────────────────

export interface BillingEvent {
  type: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface AdminWorkspaceBilling extends BillingSummary {
  events: BillingEvent[];
  profile: BillingProfile | null;
}

export interface FunnelStep { key: string; label: string; count: number; pct_of_registered: number | null }

export interface AgingBucket { count: number; amount_cop: number }

export interface OverdueInvoice {
  invoice_id: string; workspace_id: string; workspace: string; amount_cop: number; days_overdue: number;
}

export interface BillingOverview {
  status_counts: Record<string, number>;
  without_subscription: number;
  income: {
    mrr_list: number; mrr_actual: number; discount_given: number; paying: number; arpa: number; addons_mrr: number;
    by_plan: { plan: string; negocios: number; mrr_actual: number }[];
  };
  funnel: { days: number; steps: FunnelStep[]; avg_days_to_activate: number | null };
  expiring_trials: { workspace_id: string; workspace: string; owner_email: string | null; trial_ends_at: string }[];
  collections: {
    aging: Record<'por_vencer' | '1_5' | '6_30' | 'mas_30', AgingBucket>;
    overdue: OverdueInvoice[];
    billed_30d: number; collected_30d: number; collection_rate_pct: number | null; avg_days_to_pay: number | null;
  };
  risk: {
    usage_distribution: Record<'0_25' | '25_50' | '50_80' | '80_100' | 'mas_100', number>;
    near_quota: { workspace_id: string; workspace: string; plan: string; used: number; total: number; pct: number; level: string }[];
    extra_professionals: { workspace_id: string; workspace: string; professionals: number; limit: number }[];
    low_usage: { workspace_id: string; workspace: string; plan: string; last_cycles: number[]; included: number }[];
    discount_cliff: { workspace_id: string; workspace: string; plan: string; from_cop: number; to_cop: number }[];
    cancellations_30d: number;
  };
  founders: { cap: number; taken: number; items: { workspace_id: string; workspace: string; number: number | null }[] };
  settings: Record<string, number>;
}

export interface ActivatePlanBody {
  plan: 'emprendedor' | 'equipo';
  whatsapp_phone: string;
  payment_method: string;
  payment_reference?: string;
}

/** GET /billing/workspaces/{id}/payment-info: cómo pagar a Zumit y a qué WhatsApp mandar el comprobante. */
export interface PaymentInfo {
  payment_instructions: string | null;
  phone: string | null;
}

/** POST /billing/workspaces/{id}/request-activation: el dueño avisa que quiere activar su plan. */
export interface ActivationRequestBody {
  plan: 'emprendedor' | 'equipo';
  whatsapp_phone: string;
  payment_reference?: string;
}

/** GET /zmanager/billing/activation-requests */
export interface ActivationRequest {
  workspace_id: string;
  workspace: string;
  requested_at: string;
  plan: string | null;
  phone: string | null;
  reference: string | null;
  status: string;
}

// ── Cartera, cuenta de cobro y costos (Zumit Manager) ────────────────────────

/** Una factura de la cartera, con su cuenta de cobro y si ya se envió. Los montos van en pesos. */
export interface CarteraInvoice {
  id: string;
  workspace_id: string;
  workspace: string;
  kind: 'cycle' | 'proration';
  period_start: string;
  period_end: string;
  due_date: string;
  amount_cop: number;
  status: InvoiceStatus;
  paid_at: string | null;
  payment_method: string | null;
  payment_reference: string | null;
  document_number: string | null;
  document_issued_at: string | null;
  last_sent_at: string | null;
  last_sent_to: string | null;
  send_count: number;
  legal_name: string | null;
  billing_email: string | null;
  days_overdue: number;
  is_overdue: boolean;
}

export interface CarteraTotals {
  open_total: number;
  open_count: number;
  overdue_total: number;
  overdue_count: number;
  due_7d: number;
  collected_month: number;
  without_document: number;
}

export type CarteraScope = 'open' | 'paid' | 'all';

export interface Cartera {
  scope: CarteraScope;
  items: CarteraInvoice[];
  totals: CarteraTotals;
}

/** Saldo de un negocio: lo que tiene pendiente o vencido. No hay abonos parciales. */
export interface Balance {
  workspace_id: string;
  workspace: string;
  invoices: number;
  balance_cop: number;
  oldest_due: string;
  overdue_cop: number;
  max_days_overdue: number;
}

export interface UpcomingCharge {
  workspace_id: string;
  workspace: string;
  plan: string;
  charge_date: string;
  days_until: number;
  will_cancel: boolean;
  discount_cycles_remaining: number;
  invoice_id: string | null;
  invoice_status: InvoiceStatus | null;
  document_number: string | null;
  last_sent_at: string | null;
  last_sent_to: string | null;
  /** true = todavía no existe la factura (se genera 3 días antes): el valor es una estimación. */
  estimated: boolean;
  amount_cop: number;
  pending_plan: string | null;
  pending_plan_name: string | null;
}

export interface Issuer {
  legal_name: string;
  id_type: 'CC' | 'NIT' | 'CE' | 'PASAPORTE';
  id_number: string;
  city: string | null;
  address: string | null;
  email: string | null;
  phone: string | null;
  payment_instructions: string | null;
  legal_note: string | null;
}

export type CostSource = 'langsmith' | 'estimate' | 'mixed';

/** Categorías de plantilla de Meta. Cada una tiene SU tarifa: no se comparten. */
export type MetaCategory = 'utility' | 'marketing';

export interface WhatsappKind {
  kind: string;
  category: MetaCategory;
  sent: number;
  billable: number;
  free: number;
  /** null = falta la tarifa de esa categoría (no es cero: no se sabe). */
  cost_usd: number | null;
}

export interface CostRow {
  workspace_id: string;
  workspace: string;
  plan: string | null;
  status: string | null;
  /** false = en prueba, pausado o sin plan: cuesta y no paga. */
  paying: boolean;
  bookings: number;
  ai: {
    calls: number; tokens: number; cost_usd: number; cost_cop: number | null; source: CostSource;
    /** Transcripción de audios: ya está incluida en cost_usd. Siempre una estimación (tokens o segundos × tarifa). */
    audio: { count: number; seconds: number | null; cost_usd: number };
  };
  /** Siempre una estimación: plantillas enviadas × la tarifa de Meta que cargaste. */
  whatsapp: {
    sent: number; billable: number; free: number; cost_usd: number; cost_cop: number | null;
    rates_missing: MetaCategory[]; by_kind: WhatsappKind[];
  };
  fixed_cop: number;
  /** null = hay dólares y falta la tasa del dólar. */
  cost_cop: number | null;
  revenue_cop: number;
  margin_cop: number | null;
  margin_pct: number | null;
  /** (IA + WhatsApp) ÷ citas del asistente. No incluye costos fijos. */
  per_booking: { usd: number | null; cop: number | null };
}

export interface LangsmithStatus {
  configured: boolean;
  project: string | null;
  last_sync: {
    started_at: string;
    day_from: string;
    day_to: string;
    runs: number;
    workspaces: number;
    cost_usd: number;
    without_cost: number;
    error: string | null;
  } | null;
}

export interface CostsTotals {
  revenue_cop: number;
  cost_cop: number | null;
  margin_cop: number | null;
  margin_pct: number | null;
  ai_cost_usd: number;
  whatsapp_cost_usd: number;
  /** Lo que de `ai_cost_usd` corresponde a transcribir audios (estimado). */
  audio_cost_usd: number;
  audio_count: number;
  fixed_cop: number;
  whatsapp_sent: number;
  whatsapp_billable: number;
  bookings: number;
  per_booking: { usd: number | null; cop: number | null };
  /** Lo que cuestan los negocios que no pagan (pruebas). */
  trial_cost_cop: number | null;
}

export interface CostsOverview {
  days: number;
  since: string;
  until: string;
  usd_cop: number | null;
  usd_cop_day: string | null;
  /** Tarifa vigente de cada categoría (USD por mensaje). Falta la clave si aún no se cargó. */
  meta_rates: Partial<Record<MetaCategory, number>>;
  fixed_costs_cop_month: number;
  /** Plan de Kapso: topes y día de corte de la tarjeta «Uso de Kapso» (Estado). */
  kapso_plan: { messages_included: number; numbers_included: number; cycle_day: number };
  rates_missing: MetaCategory[];
  totals: CostsTotals;
  langsmith: LangsmithStatus;
  items: CostRow[];
}

export interface SyncResult {
  ok: boolean;
  error: string | null;
  runs: number;
  workspaces: number;
  cost_usd: number;
  without_cost: number;
}

// ── Planes ───────────────────────────────────────────────────────────────────

export type PlanStatusKey = 'trial' | 'active' | 'past_due' | 'paused' | 'cancelled' | 'expired';
export type UsageBucket = '0_25' | '25_50' | '50_80' | '80_100' | 'mas_100';

export interface PlanStats {
  subscribers: Record<PlanStatusKey, number>;
  paying: number;
  trials: number;
  /** Lo que pagan hoy por el plan (con descuento de lanzamiento o valor congelado), sin citas adicionales. */
  mrr_plan_cop: number;
  /** Lo que pagarían al valor completo. */
  mrr_list_cop: number;
  discount_cop: number;
  addons_cop: number;
  arpa_cop: number;
  usage: { avg_pct: number | null; near: number; blocked: number; distribution: Record<UsageBucket, number> };
  professionals: { avg: number | null; extra: number };
  cancelled_30d: number;
  cancelling: number;
  conversion: { trials: number; converted: number; pct: number | null };
  margin: { revenue_cop: number; cost_cop: number | null; margin_cop: number | null; margin_pct: number | null };
}

export interface PlanConfig {
  id: string;
  code: string | null;
  name: string;
  description: string | null;
  price_cop: number;
  launch_price_cop: number | null;
  max_appointments: number | null;
  max_professionals: number | null;
  extra_professional_price_cop: number;
  is_active: boolean;
}

export interface PlanWithStats extends PlanConfig {
  stats: PlanStats;
}

export interface ActivationsWeek {
  week: string;
  total: number;
  by_plan: Record<string, number>;
}

export interface PlansDashboard {
  days: number;
  since: string;
  until: string;
  usd_cop: number | null;
  plans: PlanWithStats[];
  series: { activations_by_week: ActivationsWeek[] };
  totals: {
    plans_active: number; paying: number; trials: number; mrr_cop: number; discount_cop: number; arpa_cop: number;
    margin_cop: number | null; margin_pct: number | null; revenue_cop: number;
  };
}

/** Lo que se puede editar. Solo se envía lo que cambia; `launch_price_cop: null` quita el precio de lanzamiento. */
export type PlanChanges = Partial<Pick<PlanConfig,
  'name' | 'description' | 'price_cop' | 'launch_price_cop' | 'max_appointments' | 'max_professionals' |
  'extra_professional_price_cop' | 'is_active'>>;

export interface OverLimit {
  workspace_id: string;
  workspace: string;
  used?: number;
  active?: number;
  limit: number;
}

export interface PlanPreview {
  plan_id: string;
  code: string | null;
  has_changes: boolean;
  changes: Record<string, { from: unknown; to: unknown }>;
  subscribers: number;
  paying: number;
  price: { affected: number; protected_founders: number; mrr_delta_cop: number };
  limits: { over_appointments: OverLimit[]; over_professionals: OverLimit[] };
  warnings: string[];
}

export interface PlanUpdateResult {
  plan: PlanConfig;
  before: Record<string, unknown>;
  impact: PlanPreview;
}

// ── Precios para la landing (público) ────────────────────────────────────────

export interface PublicPlan {
  code: string;
  name: string;
  description: string | null;
  price_cop: number;
  launch_price_cop: number | null;
  max_appointments: number | null;
  max_professionals: number | null;
  extra_professional_price_cop: number;
}

/** GET /billing/pricing. Con `plans` vacío la landing usa sus valores de fábrica. */
export interface PublicPricing {
  plans: PublicPlan[];
  trial_days: number;
  launch_discount_cycles: number;
  founder_cap: number;
  addons: { appointment_price_cop: number; blocks: number[] };
}

// ── Análisis (GET /zmanager/billing/insights) ────────────────────────────────

export interface InsightsWeek {
  /** El lunes de la semana (YYYY-MM-DD). */
  week: string;
  revenue_cop: number;
  /** null = falta la tasa del dólar. */
  ai_cop: number | null;
  whatsapp_cop: number | null;
  fixed_cop: number;
  cost_cop: number | null;
  margin_cop: number | null;
  /** Citas creadas esa semana (todas) y cuántas agendó el asistente. */
  appointments: number;
  assistant: number;
  templates_sent: number;
  templates_billable: number;
  templates_free: number;
  rates_missing: MetaCategory[];
}

export interface InsightsCliffMonth {
  /** YYYY-MM */
  month: string;
  businesses: number;
  /** Cuánto suben los cobros mensuales cuando llegan al precio completo. */
  extra_cop: number;
  by_plan: Record<string, number>;
}

export interface TopAppointment {
  id: string;
  value_cop: number;
  start_at: string;
  status: string;
  workspace: string;
  service: string;
}

export type AiCostSource = 'langsmith' | 'estimate' | 'mixed';

export interface AiCostAppointment {
  id: string;
  created_at: string;
  workspace: string;
  service: string;
  usd: number;
  /** null = falta la tasa del dólar. */
  cop: number | null;
  tokens: number;
  /** Ejecuciones del agente que hicieron falta (los mensajes de ida y vuelta hasta agendar). */
  runs: number;
  source: AiCostSource;
}

/** `available: false` = falta la migración 024 (aún no se guarda el costo de cada ejecución). */
export type AiPerAppointment =
  | { available: false }
  | {
      available: true;
      /** Citas con costo medido, y las que no (anteriores a la migración 024: no son gratis, no se midieron). */
      measured: number;
      without_measure: number;
      avg_usd: number | null;
      median_usd: number | null;
      avg_cop: number | null;
      median_cop: number | null;
      top: AiCostAppointment[];
    };

export interface Insights {
  weeks: number;
  since: string;
  until: string;
  usd_cop: number | null;
  rates_missing: MetaCategory[];
  weekly: InsightsWeek[];
  price_cliff: InsightsCliffMonth[];
  top_appointments: TopAppointment[];
  appointments_all_time: { total: number; assistant: number };
  ai_per_appointment: AiPerAppointment;
}

/** POST /billing/workspaces/{id}/request-appointments: las citas ya están acreditadas; el cobro queda pendiente. */
export interface ExtraAppointmentsResult {
  invoice_id: string;
  quantity: number;
  amount_cop: number;
  due_date: string;
  valid_until: string;
}

/** GET /billing/workspaces/{id}/usage: el saldo que ve todo el equipo (sin precios ni facturas). */
export interface BillingUsage {
  has_subscription: boolean;
  status: SubscriptionStatus;
  serving: boolean;
  plan_name?: string | null;
  cycle_end?: string | null;
  appointments?: QuotaInfo;
  professionals?: { limit: number | null; active: number; extra: number };
}

// ── Detalle de costos de IA por cliente, ejecución y cita ──

export type DetailSource = 'langsmith' | 'mixed' | 'estimate' | null;

export interface CostCustomerRow {
  customer_id: string;
  name: string | null;
  phone: string | null;
  runs: number;
  calls: number;
  tokens: number;
  cost_usd: number;
  cost_cop: number | null;
  /** Ejecuciones sin costo medido (anteriores a la migración 024): no cuentan como gratis. */
  unmeasured: number;
  source: DetailSource;
  bookings: number;
  per_booking_usd: number | null;
  per_booking_cop: number | null;
  last_at: string | null;
}

export type CostCustomers =
  | { available: false }
  | { available: true; days: number; usd_cop: number | null; items: CostCustomerRow[]; truncated: boolean };

export interface CostRun {
  id: string;
  started_at: string | null;
  seconds: number | null;
  status: string;
  model: string | null;
  calls: number;
  tokens: number | null;
  cost_usd: number | null;
  cost_cop: number | null;
  source: DetailSource;
  input: string | null;
  output: string | null;
}

export interface CostBooking {
  id: string;
  service: string | null;
  status: string;
  price_cop: number | null;
  created_at: string | null;
  start_at: string | null;
  /** Ejecuciones del agente que hicieron falta para llegar a esta cita. */
  runs: number;
  unmeasured: number;
  tokens: number;
  cost_usd: number;
  cost_cop: number | null;
}

export type CostCustomerDetail =
  | { available: false }
  | {
      available: true;
      customer: { id: string; name: string | null; phone: string | null };
      /** Nombre del hilo en LangSmith («Negocio | Teléfono»). */
      thread: string;
      usd_cop: number | null;
      totals: {
        runs: number; cost_usd: number; cost_cop: number | null; unmeasured: number;
        without_booking_usd: number; without_booking_runs: number;
      };
      appointments: CostBooking[];
      runs: CostRun[];
      truncated: boolean;
    };
