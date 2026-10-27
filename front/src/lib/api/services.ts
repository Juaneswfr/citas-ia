// T010 — Módulo de API de servicios

import { apiFetch } from './client';
import type { ServiceOut, ServiceCreate, ServiceUpdate } from '../types/api';

/** GET /workspaces/{workspaceId}/services */
export async function listServices(workspaceId: string, activeOnly?: boolean): Promise<ServiceOut[]> {
  const qs = activeOnly ? '?active_only=true' : '';
  return apiFetch<ServiceOut[]>(`/workspaces/${workspaceId}/services${qs}`);
}

/** GET /workspaces/{workspaceId}/services/{serviceId} */
export async function getService(workspaceId: string, serviceId: string): Promise<ServiceOut> {
  return apiFetch<ServiceOut>(`/workspaces/${workspaceId}/services/${serviceId}`);
}

/** POST /workspaces/{workspaceId}/services */
export async function createService(workspaceId: string, body: ServiceCreate): Promise<ServiceOut> {
  return apiFetch<ServiceOut>(`/workspaces/${workspaceId}/services`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

/** PATCH /workspaces/{workspaceId}/services/{serviceId} */
export async function updateService(
  workspaceId: string,
  serviceId: string,
  body: ServiceUpdate,
): Promise<ServiceOut> {
  return apiFetch<ServiceOut>(`/workspaces/${workspaceId}/services/${serviceId}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

/** DELETE /workspaces/{workspaceId}/services/{serviceId} — soft delete */
export async function deactivateService(workspaceId: string, serviceId: string): Promise<void> {
  return apiFetch<void>(`/workspaces/${workspaceId}/services/${serviceId}`, {
    method: 'DELETE',
  });
}
