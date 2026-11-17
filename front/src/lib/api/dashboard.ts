// Módulo de API del dashboard

import { apiFetch } from './client';

export interface DayPoint { date: string; completed: number; lost: number; open: number }
export interface StatusMix { completed: number; cancelled: number; noshow: number; open: number }
export interface TopService { id: string; name: string; count: number; revenue_cop: number | null }
export interface HeatCell { dow: number; hour: number; count: number } // dow: 0 = lunes … 6 = domingo
export interface CustomerMix { new: number; returning: number }
export interface Comparison { current: number; previous: number }
export interface RevenuePoint { date: string; amount_cop: number }

export interface Revenue {
  days: RevenuePoint[];
  /** Cobrado en los últimos 30 días. */
  collected: number;
  /** Cobrado en los 30 días anteriores. */
  previous: number;
  /** Agendado por atender: citas pendientes o confirmadas de hoy en adelante. */
  booked_open: number;
}

export interface InsightActions {
  to_complete: number;
  unconfirmed_tomorrow: number;
  lapsed_customers: number;
  receipts_pending: number | null;
  receivable_cop: number | null;
  receivable_orders: number | null;
}

export interface DashboardInsights {
  timezone: string;
  today: string; // YYYY-MM-DD, día del negocio
  days: DayPoint[];
  status_30d: StatusMix;
  top_services: TopService[];
  busy_hours: HeatCell[];
  customers: CustomerMix;
  week: Comparison;
  week_lost: Comparison;
  /** null si el rol no ve el dinero (solo dueño y administradores). */
  revenue: Revenue | null;
  actions: InsightActions;
}

/** GET /workspaces/{workspaceId}/dashboard/insights */
export function getDashboardInsights(workspaceId: string): Promise<DashboardInsights> {
  return apiFetch<DashboardInsights>(`/workspaces/${workspaceId}/dashboard/insights`);
}
