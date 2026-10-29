// API functions — canales WhatsApp y calendarios Google

import { apiFetch } from './client';
import type { ChannelOut, CalendarOut } from '../types/api';

export function listChannels(workspaceId: string): Promise<ChannelOut[]> {
  return apiFetch(`/workspaces/${workspaceId}/channels`);
}

export function updateChannelStatus(
  workspaceId: string,
  channelId: string,
  status: 'active' | 'paused' | 'disconnected',
): Promise<ChannelOut> {
  return apiFetch(`/workspaces/${workspaceId}/channels/${channelId}/status?new_status=${status}`, {
    method: 'PATCH',
  });
}

export function listCalendars(workspaceId: string): Promise<CalendarOut[]> {
  return apiFetch(`/workspaces/${workspaceId}/calendars`);
}

export function disconnectCalendar(workspaceId: string, calendarId: string): Promise<void> {
  return apiFetch(`/workspaces/${workspaceId}/calendars/${calendarId}`, { method: 'DELETE' });
}

/** Genera un link de onboarding de Kapso para conectar WhatsApp */
export function createKapsoOnboardingLink(workspaceId: string): Promise<{ url: string; expires_at: string }> {
  return apiFetch(`/workspaces/${workspaceId}/kapso/onboarding-link`, { method: 'POST' });
}

// ── Sandbox ──────────────────────────────────────────────────────────────────

export interface SandboxSession {
  id?: string;
  status: string;
  activation_code: string;
  activation_link: string;
  expires_at: string;
}

export function createSandboxSession(workspaceId: string, phoneNumber: string): Promise<SandboxSession> {
  return apiFetch(`/workspaces/${workspaceId}/kapso/sandbox-sessions`, {
    method: 'POST',
    body: JSON.stringify({ phone_number: phoneNumber }),
  });
}

export function listSandboxSessions(workspaceId: string): Promise<SandboxSession[]> {
  return apiFetch(`/workspaces/${workspaceId}/kapso/sandbox-sessions`);
}

export function getSandboxSession(workspaceId: string, sessionId: string): Promise<SandboxSession> {
  return apiFetch(`/workspaces/${workspaceId}/kapso/sandbox-sessions/${sessionId}`);
}
