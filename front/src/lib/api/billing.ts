// Planes, suscripción y facturación. El cobro es manual: no hay pasarela de pago.

import { apiDownload, apiFetch } from './client';
import type { BillingPlanOut, SubscriptionOut } from '../types/api';
import type {
  Insights, ActivationRequest, ActivationRequestBody, PaymentInfo,
  ActivatePlanBody, AdminWorkspaceBilling, Balance, BillingOverview, BillingUsage, ExtraAppointmentsResult, BillingProfile, BillingSummary, Cartera,
  CarteraScope, CostsOverview, Issuer, PlanChangePreview, PlanChanges, PlanPreview, PlansDashboard, PlanUpdateResult,
  PublicPricing, SyncResult, UpcomingCharge,
} from '../types/billing';

/** GET /billing/plans — endpoint público, no requiere JWT */
export async function listPlans(): Promise<BillingPlanOut[]> {
  return apiFetch<BillingPlanOut[]>('/billing/plans', { public: true });
}

/** GET /billing/pricing — los precios de la landing: público, sin sesión. */
export async function getPricing(): Promise<PublicPricing> {
  return apiFetch<PublicPricing>('/billing/pricing', { public: true });
}

/** GET /billing/workspaces/{workspaceId}/subscription */
export async function getSubscription(workspaceId: string): Promise<SubscriptionOut> {
  return apiFetch<SubscriptionOut>(`/billing/workspaces/${workspaceId}/subscription`);
}

const json = (body: unknown) => ({ method: 'POST', body: JSON.stringify(body) });

/** Lo que ve el dueño del negocio (workspace_owner o super_admin). */
export const billingService = {
  /** Saldo de citas del asistente y de profesionales: cualquier miembro del equipo. */
  getUsage(workspaceId: string): Promise<BillingUsage> {
    return apiFetch<BillingUsage>(`/billing/workspaces/${workspaceId}/usage`);
  },

  /** Plan, uso del ciclo, próximo cobro y facturas */
  getSummary(workspaceId: string): Promise<BillingSummary> {
    return apiFetch<BillingSummary>(`/billing/workspaces/${workspaceId}/summary`);
  },

  /** El dueño pide más citas: se acreditan ya y queda un saldo pendiente de pago. */
  requestAppointments(workspaceId: string, quantity: number): Promise<ExtraAppointmentsResult> {
    return apiFetch<ExtraAppointmentsResult>(
      `/billing/workspaces/${workspaceId}/request-appointments?confirmed=true`, json({ quantity }),
    );
  },

  getPaymentInfo(workspaceId: string): Promise<PaymentInfo> {
    return apiFetch<PaymentInfo>(`/billing/workspaces/${workspaceId}/payment-info`);
  },

  /** El dueño avisa que quiere activar su plan: no activa nada, avisa al equipo de Zumit. */
  requestActivation(workspaceId: string, body: ActivationRequestBody): Promise<{ ok: boolean; already_requested: boolean }> {
    return apiFetch(`/billing/workspaces/${workspaceId}/request-activation?confirmed=true`, json(body));
  },

  getProfile(workspaceId: string): Promise<BillingProfile | null> {
    return apiFetch<BillingProfile | null>(`/billing/workspaces/${workspaceId}/profile`);
  },

  saveProfile(workspaceId: string, body: BillingProfile): Promise<{ ok: boolean }> {
    return apiFetch(`/billing/workspaces/${workspaceId}/profile`, { method: 'PUT', body: JSON.stringify(body) });
  },

  previewPlanChange(workspaceId: string, plan: string): Promise<PlanChangePreview> {
    return apiFetch<PlanChangePreview>(`/billing/workspaces/${workspaceId}/plan-change-preview?plan=${plan}`);
  },

  /** La cancelación vale al final del ciclo pagado. `undo` la deshace. */
  cancel(workspaceId: string, undo = false): Promise<{ cancel_at_period_end: boolean }> {
    const query = undo ? 'undo=true' : 'confirmed=true';
    return apiFetch(`/billing/workspaces/${workspaceId}/cancel?${query}`, { method: 'POST' });
  },
};

const ADMIN = '/zmanager/billing';

/** Solo super_admin. Toda acción que cambia estado va con confirmed=true. */
export const adminBillingService = {
  getOverview(funnelDays = 90): Promise<BillingOverview> {
    return apiFetch<BillingOverview>(`${ADMIN}/overview?funnel_days=${funnelDays}`);
  },

  getWorkspace(workspaceId: string): Promise<AdminWorkspaceBilling> {
    return apiFetch<AdminWorkspaceBilling>(`${ADMIN}/workspaces/${workspaceId}`);
  },

  activate(workspaceId: string, body: ActivatePlanBody) {
    return apiFetch<{ invoice_id: string | null; discount_applied: boolean }>(
      `${ADMIN}/workspaces/${workspaceId}/activate?confirmed=true`, json(body));
  },

  registerPayment(invoiceId: string, body: { payment_method: string; payment_reference?: string }) {
    return apiFetch<{ amount_cop: number; reactivated: boolean }>(
      `${ADMIN}/invoices/${invoiceId}/payment?confirmed=true`, json(body));
  },

  voidInvoice(invoiceId: string, reason?: string) {
    return apiFetch(`${ADMIN}/invoices/${invoiceId}/void?confirmed=true`, json({ reason }));
  },

  extendTrial(workspaceId: string, days: number) {
    return apiFetch(`${ADMIN}/workspaces/${workspaceId}/trial/extend?confirmed=true`, json({ days }));
  },

  pause(workspaceId: string) {
    return apiFetch(`${ADMIN}/workspaces/${workspaceId}/pause?confirmed=true`, { method: 'POST' });
  },

  reactivate(workspaceId: string) {
    return apiFetch(`${ADMIN}/workspaces/${workspaceId}/reactivate?confirmed=true`, { method: 'POST' });
  },

  changePlan(workspaceId: string, plan: 'emprendedor' | 'equipo') {
    return apiFetch<PlanChangePreview>(`${ADMIN}/workspaces/${workspaceId}/plan-change?confirmed=true`, json({ plan }));
  },

  addAddon(workspaceId: string, kind: 'appointments_block' | 'appointments_topup', quantity: number) {
    return apiFetch(`${ADMIN}/workspaces/${workspaceId}/addons?confirmed=true`, json({ kind, quantity }));
  },

  grantFounder(workspaceId: string) {
    return apiFetch<{ founder_number: number }>(`${ADMIN}/workspaces/${workspaceId}/founder?confirmed=true`, { method: 'POST' });
  },

  setSetting(key: string, value: number) {
    return apiFetch(`${ADMIN}/settings/${key}`, { method: 'PUT', body: JSON.stringify({ value }) });
  },

  setFx(day: string, usdCop: number) {
    return apiFetch(`${ADMIN}/fx`, { method: 'PUT', body: JSON.stringify({ day, usd_cop: usdCop }) });
  },

  setMetaRate(category: string, usdPrice: number, validFrom: string) {
    return apiFetch(`${ADMIN}/meta-rates`, {
      method: 'PUT', body: JSON.stringify({ category, usd_price: usdPrice, valid_from: validFrom }),
    });
  },

  // ── Planes ──

  /** Análisis semana a semana (ingreso vs costo, citas, plantillas) y el precipicio de precio. */
  getInsights(weeks = 12): Promise<Insights> {
    return apiFetch<Insights>(`${ADMIN}/insights?weeks=${weeks}`);
  },

  /** Cada plan con su configuración y estadísticas, y las series para los gráficos. `days` acota margen y activaciones. */
  getPlans(days = 30): Promise<PlansDashboard> {
    return apiFetch<PlansDashboard>(`${ADMIN}/plans?days=${days}`);
  },

  /** Qué pasaría al aplicar los cambios (no cambia nada). */
  previewPlan(planId: string, changes: PlanChanges): Promise<PlanPreview> {
    return apiFetch<PlanPreview>(`${ADMIN}/plans/${planId}/preview`, json(changes));
  },

  updatePlan(planId: string, changes: PlanChanges): Promise<PlanUpdateResult> {
    return apiFetch<PlanUpdateResult>(`${ADMIN}/plans/${planId}?confirmed=true`, { method: 'PUT', body: JSON.stringify(changes) });
  },

  // ── Cartera y cuenta de cobro ──

  /** Facturas con su cuenta de cobro y los totales de la cartera. */
  getCartera(scope: CarteraScope): Promise<Cartera> {
    return apiFetch<Cartera>(`${ADMIN}/invoices?scope=${scope}`);
  },

  getActivationRequests(): Promise<ActivationRequest[]> {
    return apiFetch<ActivationRequest[]>(`${ADMIN}/activation-requests`);
  },

  getBalances(): Promise<Balance[]> {
    return apiFetch<Balance[]>(`${ADMIN}/balances`);
  },

  getUpcoming(days = 45): Promise<UpcomingCharge[]> {
    return apiFetch<UpcomingCharge[]>(`${ADMIN}/upcoming?days=${days}`);
  },

  /** Asigna el consecutivo (CC-0001). Si ya lo tiene, devuelve el mismo. */
  generateDocument(invoiceId: string) {
    return apiFetch<{ document_number: string; issued: boolean }>(
      `${ADMIN}/invoices/${invoiceId}/document?confirmed=true`, { method: 'POST' });
  },

  /** El PDF de la cuenta de cobro (ya emitida). */
  downloadDocument(invoiceId: string): Promise<Blob> {
    return apiDownload(`${ADMIN}/invoices/${invoiceId}/document.pdf`);
  },

  /** Envía la cuenta de cobro por correo (la genera si hace falta). Sin `to`, va al correo de cobro del negocio. */
  sendDocument(invoiceId: string, to?: string) {
    return apiFetch<{ document_number: string; sent_to: string; issued_now: boolean }>(
      `${ADMIN}/invoices/${invoiceId}/send?confirmed=true`, json({ to: to || null }));
  },

  // ── Quien cobra y datos de cobro de un negocio ──

  getIssuer(): Promise<Issuer | null> {
    return apiFetch<Issuer | null>(`${ADMIN}/issuer`);
  },

  saveIssuer(body: Issuer): Promise<Issuer> {
    return apiFetch<Issuer>(`${ADMIN}/issuer`, { method: 'PUT', body: JSON.stringify(body) });
  },

  saveClientProfile(workspaceId: string, body: BillingProfile) {
    return apiFetch(`${ADMIN}/workspaces/${workspaceId}/profile`, { method: 'PUT', body: JSON.stringify(body) });
  },

  // ── Costo por negocio (LangSmith) ──

  getCosts(days = 30): Promise<CostsOverview> {
    return apiFetch<CostsOverview>(`${ADMIN}/costs?days=${days}`);
  },

  syncCosts(days = 7): Promise<SyncResult> {
    return apiFetch<SyncResult>(`${ADMIN}/costs/sync?days=${days}`, { method: 'POST' });
  },

  pingLangsmith(): Promise<{ ok: boolean; detail: string }> {
    return apiFetch(`${ADMIN}/langsmith/ping`);
  },

  /** CSV de facturas para la contadora (hasta 5 000), con los datos de cobro de cada negocio. */
  exportInvoices(): Promise<Blob> {
    return apiDownload(`${ADMIN}/invoices/export`);
  },
};
