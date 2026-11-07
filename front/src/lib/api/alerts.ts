// API calls para alertas del agente

import { apiFetch } from './client';
import type { AgentAlertOut } from '../types/api';

export async function listAgentAlerts(
  workspaceId: string,
  resolved = false,
): Promise<AgentAlertOut[]> {
  return apiFetch(`/workspaces/${workspaceId}/agent-alerts?resolved=${resolved}`);
}

export async function countAgentAlerts(workspaceId: string): Promise<{ count: number }> {
  return apiFetch(`/workspaces/${workspaceId}/agent-alerts/count`);
}

export async function resolveAgentAlert(
  workspaceId: string,
  alertId: string,
): Promise<AgentAlertOut> {
  return apiFetch(`/workspaces/${workspaceId}/agent-alerts/${alertId}/resolve`, {
    method: 'PATCH',
  });
}
