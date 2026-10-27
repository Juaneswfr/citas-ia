// API helpers para workspaces

import { apiFetch } from './client';

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
