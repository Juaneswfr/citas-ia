// Módulo de API de finanzas — un solo dominio: /workspaces/{id}/accounting

import { apiDownload, apiFetch, apiUpload } from './client';
import type {
  AttachmentOut, CategoryOut, CommissionRow, CompensationOut, CompensationUpsert, FlowKind, MovementCreate,
  MovementOut, PaymentCreate, PaymentMethod, PayoutOut, PurchaseOrderCreate, PurchaseOrderOut,
  SalesOrderCreate, SalesOrderOut, SummaryOut, ThirdPartyCreate, ThirdPartyKind, ThirdPartyOut,
} from '../types/accounting';

const base = (workspaceId: string) => `/workspaces/${workspaceId}/accounting`;
const post = <T>(path: string, body?: unknown) =>
  apiFetch<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) });

// ── Terceros y categorías ─────────────────────────────────────────────────────

export const listThirdParties = (workspaceId: string, kind?: ThirdPartyKind) =>
  apiFetch<ThirdPartyOut[]>(`${base(workspaceId)}/third-parties${kind ? `?kind=${kind}` : ''}`);

export const createThirdParty = (workspaceId: string, body: ThirdPartyCreate) =>
  post<ThirdPartyOut>(`${base(workspaceId)}/third-parties`, body);

export const listCategories = (workspaceId: string, kind?: FlowKind) =>
  apiFetch<CategoryOut[]>(`${base(workspaceId)}/categories${kind ? `?kind=${kind}` : ''}`);

// ── Ventas ────────────────────────────────────────────────────────────────────

export const listSalesOrders = (workspaceId: string, status?: string) =>
  apiFetch<SalesOrderOut[]>(`${base(workspaceId)}/sales-orders${status ? `?status=${status}` : ''}`);

export const createSalesOrder = (workspaceId: string, body: SalesOrderCreate) =>
  post<SalesOrderOut>(`${base(workspaceId)}/sales-orders`, body);

/** Venta de una cita; null si la cita todavía no se completó. */
export const getSalesOrderByAppointment = (workspaceId: string, appointmentId: string) =>
  apiFetch<SalesOrderOut | null>(`${base(workspaceId)}/sales-orders/by-appointment/${appointmentId}`);

export const paySalesOrder = (workspaceId: string, orderId: string, body: PaymentCreate) =>
  post<SalesOrderOut>(`${base(workspaceId)}/sales-orders/${orderId}/payments`, body);

export const voidSalesOrder = (workspaceId: string, orderId: string) =>
  post<SalesOrderOut>(`${base(workspaceId)}/sales-orders/${orderId}/void?confirmed=true`);

// ── Compras ───────────────────────────────────────────────────────────────────

export const listPurchaseOrders = (workspaceId: string, status?: string) =>
  apiFetch<PurchaseOrderOut[]>(`${base(workspaceId)}/purchase-orders${status ? `?status=${status}` : ''}`);

export const createPurchaseOrder = (workspaceId: string, body: PurchaseOrderCreate) =>
  post<PurchaseOrderOut>(`${base(workspaceId)}/purchase-orders`, body);

export const payPurchaseOrder = (workspaceId: string, orderId: string, body: PaymentCreate) =>
  post<PurchaseOrderOut>(`${base(workspaceId)}/purchase-orders/${orderId}/payments`, body);

export const voidPurchaseOrder = (workspaceId: string, orderId: string) =>
  post<PurchaseOrderOut>(`${base(workspaceId)}/purchase-orders/${orderId}/void?confirmed=true`);

// ── Movimientos ───────────────────────────────────────────────────────────────

export const listMovements = (workspaceId: string, from?: string, to?: string) => {
  const qs = new URLSearchParams();
  if (from) qs.set('from_date', from);
  if (to) qs.set('to_date', to);
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return apiFetch<MovementOut[]>(`${base(workspaceId)}/movements${suffix}`);
};

export const createMovement = (workspaceId: string, body: MovementCreate) =>
  post<MovementOut>(`${base(workspaceId)}/movements`, body);

export const voidMovement = (workspaceId: string, movementId: string) =>
  post<MovementOut>(`${base(workspaceId)}/movements/${movementId}/void?confirmed=true`);

// ── Compensación y liquidaciones ──────────────────────────────────────────────

export const listCompensation = (workspaceId: string) =>
  apiFetch<CompensationOut[]>(`${base(workspaceId)}/compensation`);

export const saveCompensation = (workspaceId: string, memberId: string, body: CompensationUpsert) =>
  apiFetch<CompensationOut>(`${base(workspaceId)}/compensation/${memberId}`, {
    method: 'PUT', body: JSON.stringify(body),
  });

export const listPayouts = (workspaceId: string) =>
  apiFetch<PayoutOut[]>(`${base(workspaceId)}/payouts`);

export const previewPayout = (workspaceId: string, memberId: string, start: string, end: string) =>
  apiFetch<PayoutOut>(
    `${base(workspaceId)}/payouts/preview?member_id=${memberId}&period_start=${start}&period_end=${end}`,
  );

export const createPayout = (workspaceId: string, memberId: string, start: string, end: string) =>
  post<PayoutOut>(`${base(workspaceId)}/payouts`, { member_id: memberId, period_start: start, period_end: end });

export const payPayout = (workspaceId: string, payoutId: string, method: PaymentMethod) =>
  post<PayoutOut>(`${base(workspaceId)}/payouts/${payoutId}/pay`, { method });

export const cancelPayout = (workspaceId: string, payoutId: string) =>
  post<PayoutOut>(`${base(workspaceId)}/payouts/${payoutId}/cancel?confirmed=true`);

// ── Reportes ──────────────────────────────────────────────────────────────────

export const getSummary = (workspaceId: string, month: string) =>
  apiFetch<SummaryOut>(`${base(workspaceId)}/reports/summary?month=${month}`);

export const getCommissions = (workspaceId: string) =>
  apiFetch<CommissionRow[]>(`${base(workspaceId)}/reports/commissions`);

// ── Comprobantes de pago ──────────────────────────────────────────────────────

export const listAttachments = (workspaceId: string, movementId: string) =>
  apiFetch<AttachmentOut[]>(`${base(workspaceId)}/movements/${movementId}/attachments`);

export const uploadAttachment = (workspaceId: string, movementId: string, file: File) =>
  apiUpload<AttachmentOut>(`${base(workspaceId)}/movements/${movementId}/attachments`, file);

export const downloadAttachment = (workspaceId: string, attachmentId: string) =>
  apiDownload(`${base(workspaceId)}/attachments/${attachmentId}/file`);

export const deleteAttachment = (workspaceId: string, attachmentId: string) =>
  apiFetch<void>(`${base(workspaceId)}/attachments/${attachmentId}?confirmed=true`, { method: 'DELETE' });
