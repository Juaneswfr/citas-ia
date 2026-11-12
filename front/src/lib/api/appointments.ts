// T014 — Módulo de API de citas

import { apiFetch } from './client';
import type {
  AppointmentCancelOut, AppointmentOut, AppointmentUpdate, AppointmentStatus, AppointmentCreate,
} from '../types/api';

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

/** POST /workspaces/{workspaceId}/appointments */
export async function createAppointment(
  workspaceId: string,
  body: AppointmentCreate,
): Promise<AppointmentOut> {
  return apiFetch<AppointmentOut>(`/workspaces/${workspaceId}/appointments`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

/**
 * POST /workspaces/{workspaceId}/appointments/{appointmentId}/cancel
 * Cancela la cita (cualquier miembro del equipo) y avisa al cliente por WhatsApp.
 * Solo se llama después de que la persona confirmó (Principio IX).
 */
export async function cancelAppointment(
  workspaceId: string,
  appointmentId: string,
  reason?: string,
): Promise<AppointmentCancelOut> {
  return apiFetch<AppointmentCancelOut>(
    `/workspaces/${workspaceId}/appointments/${appointmentId}/cancel?confirmed=true`,
    { method: 'POST', body: JSON.stringify({ reason: reason ?? null }) },
  );
}

/**
 * PATCH /workspaces/{workspaceId}/appointments/{appointmentId}
 * Solo dueño o administrador. Para cancelar desde el panel usar cancelAppointment.
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
