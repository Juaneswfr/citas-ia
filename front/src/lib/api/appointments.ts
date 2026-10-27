// T014 — Módulo de API de citas

import { apiFetch } from './client';
import type { AppointmentOut, AppointmentUpdate, AppointmentStatus } from '../types/api';

interface ListAppointmentsParams {
  status?: AppointmentStatus;
  from_date?: string; // ISO date YYYY-MM-DD
  to_date?: string;   // ISO date YYYY-MM-DD
}

/** GET /workspaces/{workspaceId}/appointments */
export async function listAppointments(
  workspaceId: string,
  params?: ListAppointmentsParams,
): Promise<AppointmentOut[]> {
  const qs = new URLSearchParams();
  if (params?.status) qs.set('status', params.status);
  if (params?.from_date) qs.set('from_date', params.from_date);
  if (params?.to_date) qs.set('to_date', params.to_date);
  const query = qs.toString() ? `?${qs.toString()}` : '';
  return apiFetch<AppointmentOut[]>(`/workspaces/${workspaceId}/appointments${query}`);
}

/** GET /workspaces/{workspaceId}/appointments/{appointmentId} */
export async function getAppointment(
  workspaceId: string,
  appointmentId: string,
): Promise<AppointmentOut> {
  return apiFetch<AppointmentOut>(`/workspaces/${workspaceId}/appointments/${appointmentId}`);
}

/**
 * PATCH /workspaces/{workspaceId}/appointments/{appointmentId}
 * Para cancelar: body.status = 'cancelled' + confirmed = true (Principio IX)
 */
export async function updateAppointment(
  workspaceId: string,
  appointmentId: string,
  body: AppointmentUpdate,
  confirmed?: boolean,
): Promise<AppointmentOut> {
  const qs = confirmed ? '?confirmed=true' : '';
  return apiFetch<AppointmentOut>(
    `/workspaces/${workspaceId}/appointments/${appointmentId}${qs}`,
    { method: 'PATCH', body: JSON.stringify(body) },
  );
}
