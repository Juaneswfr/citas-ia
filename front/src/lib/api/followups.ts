// Módulo de API del seguimiento por WhatsApp: /workspaces/{id}/followups

import { apiFetch } from './client';
import type { FollowupSettings, FollowupTemplatesOut } from '../types/followups';

const base = (workspaceId: string) => `/workspaces/${workspaceId}/followups`;

export const getFollowupSettings = (workspaceId: string) =>
  apiFetch<FollowupSettings>(`${base(workspaceId)}/settings`);

export const updateFollowupSettings = (workspaceId: string, body: FollowupSettings) =>
  apiFetch<FollowupSettings>(`${base(workspaceId)}/settings`, { method: 'PUT', body: JSON.stringify(body) });

export const listFollowupTemplates = (workspaceId: string) =>
  apiFetch<FollowupTemplatesOut>(`${base(workspaceId)}/templates`);

/** Envía a revisión de WhatsApp las plantillas que falten y devuelve el estado de todas. */
export const activateFollowupTemplates = (workspaceId: string) =>
  apiFetch<FollowupTemplatesOut>(`${base(workspaceId)}/templates/activate`, { method: 'POST' });

/** Vuelve a consultar en WhatsApp si las plantillas ya fueron aprobadas. */
export const syncFollowupTemplates = (workspaceId: string) =>
  apiFetch<FollowupTemplatesOut>(`${base(workspaceId)}/templates/sync`, { method: 'POST' });
