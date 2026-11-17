// Módulo de API de bloqueos de agenda

import { apiFetch } from './client';
import type { AvailabilityBlockCreate, AvailabilityBlockCreated, AvailabilityBlockOut } from '../types/api';

/** GET /workspaces/{workspaceId}/blocks — con rango, solo los bloqueos que lo tocan (días del negocio). */
export async function listBlocks(
  workspaceId: string,
  params?: { from_date?: string; to_date?: string }, // YYYY-MM-DD
): Promise<AvailabilityBlockOut[]> {
  const qs = new URLSearchParams();
  if (params?.from_date) qs.set('from_date', params.from_date);
  if (params?.to_date) qs.set('to_date', params.to_date);
  const query = qs.toString() ? `?${qs.toString()}` : '';
  return apiFetch<AvailabilityBlockOut[]>(`/workspaces/${workspaceId}/blocks${query}`);
}

/** POST /workspaces/{workspaceId}/blocks — solo dueño o administrador; la persona ya confirmó en el diálogo. */
export async function createBlock(
  workspaceId: string,
  body: AvailabilityBlockCreate,
): Promise<AvailabilityBlockCreated> {
  return apiFetch<AvailabilityBlockCreated>(`/workspaces/${workspaceId}/blocks?confirmed=true`, {
    method: 'POST',
    body: JSON.stringify({ block_type: 'manual', ...body }),
  });
}

/** DELETE /workspaces/{workspaceId}/blocks/{blockId} — solo dueño o administrador. */
export async function deleteBlock(workspaceId: string, blockId: string): Promise<void> {
  return apiFetch<void>(`/workspaces/${workspaceId}/blocks/${blockId}?confirmed=true`, { method: 'DELETE' });
}
