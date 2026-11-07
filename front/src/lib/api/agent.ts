// API calls para configuración del agente de WhatsApp

import { apiFetch } from './client';
import type { AgentConfigOut, AgentConfigUpdate, AgentHoursOut } from '../types/api';

export async function getAgentConfig(workspaceId: string): Promise<AgentConfigOut> {
  return apiFetch(`/workspaces/${workspaceId}/agent/config`);
}

export async function updateAgentConfig(workspaceId: string, body: AgentConfigUpdate): Promise<AgentConfigOut> {
  return apiFetch(`/workspaces/${workspaceId}/agent/config`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function getAgentHours(workspaceId: string): Promise<AgentHoursOut[]> {
  return apiFetch(`/workspaces/${workspaceId}/agent/hours`);
}

export async function updateAgentHours(workspaceId: string, hours: AgentHoursOut[]): Promise<AgentHoursOut[]> {
  return apiFetch(`/workspaces/${workspaceId}/agent/hours`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ hours }),
  });
}
