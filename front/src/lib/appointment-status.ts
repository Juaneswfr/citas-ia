// Cómo se llama y de qué color es cada estado de una cita (una sola fuente para buscador, historial y listas).

import type { AppointmentStatus } from '@/lib/types/api';

export const STATUS_LABEL: Record<AppointmentStatus, string> = {
  pending: 'Pendiente',
  confirmed: 'Confirmada',
  completed: 'Completada',
  cancelled: 'Cancelada',
  noshow: 'No asistió',
  rescheduled: 'Reagendada',
};

/** Tono del `Tag` (los de la paleta de Hilo). */
export const STATUS_HUE: Record<AppointmentStatus, string> = {
  pending: 'mustard',
  confirmed: 'steel',
  completed: 'sage',
  cancelled: 'clay',
  noshow: 'clay',
  rescheduled: 'plum',
};
