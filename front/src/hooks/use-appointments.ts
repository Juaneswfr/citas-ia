// T016 — React Query hooks para citas

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { format, parseISO, getHours, getMinutes, differenceInMinutes } from 'date-fns';
import { useAuth } from '@/lib/auth-context';
import { listAppointments, updateAppointment, createAppointment } from '@/lib/api/appointments';
import { listCustomers } from '@/lib/api/conversations';
import { listServices } from '@/lib/api/services';
import { toHiloAppointment } from '@/lib/api/adapters';
import type { HiloAppointment } from '@/lib/hilo-data';
import type { AppointmentCreate, AppointmentOut, AppointmentStatus, AppointmentUpdate, ServiceOut, CustomerOut } from '@/lib/types/api';

const STALE = 60 * 1000; // 1 min

interface UseAppointmentsOptions {
  status?: AppointmentStatus;
  from_date?: string;
  to_date?: string;
}

/** React Query hook — lista citas enriquecidas con datos de clientes y servicios */
export function useAppointments(options?: UseAppointmentsOptions) {
  const { workspaceId } = useAuth();
  return useQuery<HiloAppointment[], Error>({
    queryKey: ['appointments', workspaceId, options],
    queryFn: async () => {
      if (!workspaceId) return [];
      // Cargar en paralelo citas, clientes y servicios
      const [apts, customers, services] = await Promise.all([
        listAppointments(workspaceId, options),
        listCustomers(workspaceId),
        listServices(workspaceId),
      ]);
      const customersMap = new Map<string, CustomerOut>(customers.map(c => [c.id, c]));
      const servicesMap = new Map<string, ServiceOut>(services.map(s => [s.id, s]));
      return apts.map(apt => toHiloAppointment(apt, customersMap, servicesMap));
    },
    enabled: !!workspaceId,
    staleTime: STALE,
  });
}

/** Formato de evento para el calendario semanal */
export interface CalendarEvent {
  id: string;
  d: number;     // índice de día relativo al inicio de semana (0 = primer día)
  s: number;     // hora de inicio decimal (ej. 9.5 = 09:30)
  m: number;     // duración en minutos
  client: string;
  svc: string;   // nombre del servicio
  pro: string;
}

interface UseWeekAppointmentsOptions {
  weekStart: Date;
  weekEnd: Date;
}

/**
 * React Query hook — citas de la semana en formato de evento de calendario.
 * Retorna CalendarEvent[] listos para renderizar en WeekView.
 */
export function useWeekAppointments({ weekStart, weekEnd }: UseWeekAppointmentsOptions) {
  const { workspaceId } = useAuth();
  const from_date = format(weekStart, 'yyyy-MM-dd');
  const to_date = format(weekEnd, 'yyyy-MM-dd');

  return useQuery<CalendarEvent[], Error>({
    queryKey: ['appointments-week', workspaceId, from_date, to_date],
    queryFn: async () => {
      if (!workspaceId) return [];
      const [apts, customers, services] = await Promise.all([
        listAppointments(workspaceId, { from_date, to_date }),
        listCustomers(workspaceId),
        listServices(workspaceId),
      ]);
      const customersMap = new Map<string, CustomerOut>(customers.map(c => [c.id, c]));
      const servicesMap = new Map<string, ServiceOut>(services.map(s => [s.id, s]));

      return apts
        .filter(apt => apt.status !== 'cancelled' && apt.status !== 'noshow')
        .map((apt): CalendarEvent => {
          const start = parseISO(apt.start_at);
          const end = parseISO(apt.end_at);

          // Día relativo al inicio de semana (0 = lunes si weekStart es lunes)
          const msPerDay = 24 * 60 * 60 * 1000;
          const d = Math.floor((start.getTime() - weekStart.getTime()) / msPerDay);

          const s = getHours(start) + getMinutes(start) / 60;
          const m = differenceInMinutes(end, start);

          const customer = customersMap.get(apt.customer_id);
          const service = servicesMap.get(apt.service_id);

          return {
            id: apt.id,
            d,
            s,
            m,
            client: customer?.name ?? customer?.phone ?? '',
            svc: service?.name ?? '',
            pro: '',
          };
        });
    },
    enabled: !!workspaceId,
    staleTime: STALE,
  });
}

/** React Query mutation — crear una cita manualmente */
export function useCreateAppointment() {
  const { workspaceId } = useAuth();
  const qc = useQueryClient();
  return useMutation<AppointmentOut, Error, AppointmentCreate>({
    mutationFn: (body) => {
      if (!workspaceId) throw new Error('No workspace');
      return createAppointment(workspaceId, body);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['appointments', workspaceId] });
      qc.invalidateQueries({ queryKey: ['appointments-week', workspaceId] });
      toast.success('Cita creada');
    },
    onError: (error) => {
      toast.error((error as { detail?: string }).detail ?? error.message ?? 'Error al crear cita');
    },
  });
}

/** React Query mutation — actualizar o cancelar una cita */
export function useUpdateAppointment(appointmentId: string) {
  const { workspaceId } = useAuth();
  const qc = useQueryClient();
  return useMutation<void, Error, { body: AppointmentUpdate; confirmed?: boolean }>({
    mutationFn: async ({ body, confirmed }) => {
      if (!workspaceId) throw new Error('No workspace');
      await updateAppointment(workspaceId, appointmentId, body, confirmed);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['appointments', workspaceId] });
      qc.invalidateQueries({ queryKey: ['appointments-week', workspaceId] });
      toast.success('Cita actualizada');
    },
    onError: (error) => {
      toast.error((error as { detail?: string }).detail ?? error.message ?? 'Error al actualizar cita');
    },
  });
}
