// Módulo de API del buscador global

import { apiFetch } from './client';

export interface SearchCustomer {
  id: string;
  name: string | null;
  phone: string;
  email: string | null;
}

export interface SearchService {
  id: string;
  name: string;
  duration_minutes: number;
  price_cop: number;
  is_active: boolean;
}

export interface SearchAppointment {
  id: string;
  start_at: string; // ISO 8601
  status: 'pending' | 'confirmed' | 'cancelled' | 'completed' | 'noshow' | 'rescheduled';
  customer_name: string | null;
  customer_phone: string;
  service_name: string;
  staff_name: string | null;
}

export interface SearchResults {
  customers: SearchCustomer[];
  services: SearchService[];
  appointments: SearchAppointment[];
}

/** GET /workspaces/{workspaceId}/search?q= — citas, clientes y servicios que coinciden (pocos por tipo). */
export function searchWorkspace(workspaceId: string, q: string, signal?: AbortSignal): Promise<SearchResults> {
  return apiFetch<SearchResults>(`/workspaces/${workspaceId}/search?q=${encodeURIComponent(q)}`, { signal });
}
