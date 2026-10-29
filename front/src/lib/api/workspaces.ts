// API helpers para workspaces

import { apiFetch } from './client';
import type { MemberOut, BusinessHoursOut } from '../types/api';

export interface WorkspacePatch {
  name?: string;
  business_type?: string;
  primary_phone?: string;
  timezone?: string;
}

/** PATCH /workspaces/{id} — actualiza datos del workspace */
export async function patchWorkspace(workspaceId: string, data: WorkspacePatch): Promise<void> {
  await apiFetch(`/workspaces/${workspaceId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

/** GET /workspaces/{id}/members — lista miembros con nombre y email */
export async function listMembers(workspaceId: string): Promise<MemberOut[]> {
  return apiFetch<MemberOut[]>(`/workspaces/${workspaceId}/members`);
}

/** GET /workspaces/{id}/business-hours */
export async function getBusinessHours(workspaceId: string): Promise<BusinessHoursOut[]> {
  return apiFetch<BusinessHoursOut[]>(`/workspaces/${workspaceId}/business-hours`);
}

/** PUT /workspaces/{id}/business-hours */
export async function updateBusinessHours(workspaceId: string, hours: BusinessHoursOut[]): Promise<BusinessHoursOut[]> {
  return apiFetch<BusinessHoursOut[]>(`/workspaces/${workspaceId}/business-hours`, {
    method: 'PUT',
    body: JSON.stringify({ hours }),
  });
}
