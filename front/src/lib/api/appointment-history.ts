// Módulo de API del historial de citas

import { apiDownload, apiFetch } from './client';
import type { AppointmentStatus } from '../types/api';

export interface HistoryItem {
  id: string;
  start_at: string; // ISO 8601
  end_at: string;
  status: AppointmentStatus;
  customer_id: string;
  customer_name: string | null;
  customer_phone: string;
  service_id: string;
  service_name: string;
  calendar_id: string | null;
  staff_name: string | null;
  price_cop: number;
  is_home_service: boolean;
  cancellation_reason: string | null;
  cancelled_by_name: string | null;
  /** 'agent': la agendó el agente por WhatsApp · 'panel': la creó una persona del equipo. */
  booked_by: 'agent' | 'panel';
  created_at: string;
}

export interface HistorySummary {
  total: number;
  completed: number;
  cancelled: number;
  noshow: number;
  /** Pendientes y confirmadas. */
  upcoming: number;
  /** Cobrado en las completadas; null si el rol no ve el dinero. */
  revenue_cop: number | null;
}

export interface HistoryPage {
  items: HistoryItem[];
  /** Cuántas coinciden con el filtro, estado incluido: para paginar. */
  matching: number;
  /** Reparto por estado de todo lo filtrado, sin contar el filtro de estado: alimenta los contadores. */
  summary: HistorySummary;
  limit: number;
  offset: number;
}

export interface HistoryFilters {
  q: string;
  statuses: AppointmentStatus[];
  from?: string; // YYYY-MM-DD, día del negocio
  to?: string;
  calendarId?: string;
  serviceId?: string;
  customerId?: string;
  order: 'asc' | 'desc';
}

function toQuery(f: HistoryFilters): URLSearchParams {
  const qs = new URLSearchParams();
  if (f.q.trim()) qs.set('q', f.q.trim());
  f.statuses.forEach((s) => qs.append('status', s));
  if (f.from) qs.set('from_date', f.from);
  if (f.to) qs.set('to_date', f.to);
  if (f.calendarId) qs.set('calendar_id', f.calendarId);
  if (f.serviceId) qs.set('service_id', f.serviceId);
  if (f.customerId) qs.set('customer_id', f.customerId);
  return qs;
}

/** GET /workspaces/{workspaceId}/appointment-history */
export function fetchHistory(workspaceId: string, f: HistoryFilters, limit: number, offset: number): Promise<HistoryPage> {
  const qs = toQuery(f);
  qs.set('order', f.order);
  qs.set('limit', String(limit));
  qs.set('offset', String(offset));
  return apiFetch<HistoryPage>(`/workspaces/${workspaceId}/appointment-history?${qs.toString()}`);
}

/** GET …/appointment-history/export — CSV de lo filtrado (hasta 5 000 citas); solo dueño y administradores. */
export function downloadHistoryCsv(workspaceId: string, f: HistoryFilters): Promise<Blob> {
  return apiDownload(`/workspaces/${workspaceId}/appointment-history/export?${toQuery(f).toString()}`);
}
