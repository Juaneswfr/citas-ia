// Datos y acciones del panel de detalle de una cita: cita, servicio, cliente, venta asociada, completar y cancelar.

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/lib/auth-context';
import { getAppointment } from '@/lib/api/appointments';
import { listCustomers } from '@/lib/api/conversations';
import { listServices } from '@/lib/api/services';
import { getSalesOrderByAppointment } from '@/lib/api/accounting';
import { canCancelAppointments, canManageFinance } from '@/lib/nav';
import type { SalesOrderOut } from '@/lib/types/accounting';
import { useCancelAppointment, useUpdateAppointment } from '@/hooks/use-appointments';
import { useSaleByAppointment } from '@/hooks/use-accounting';

const STALE = 5 * 60 * 1000;

export function useAppointmentDetail(appointmentId: string) {
  const { workspaceId, role } = useAuth();
  const queryClient = useQueryClient();
  const canManage = canManageFinance(role);

  const appointment = useQuery({
    queryKey: ['appointment', workspaceId, appointmentId],
    queryFn: () => getAppointment(workspaceId as string, appointmentId),
    enabled: !!workspaceId,
    staleTime: 0,
  });
  const services = useQuery({
    queryKey: ['services-raw', workspaceId],
    queryFn: () => listServices(workspaceId as string),
    enabled: !!workspaceId,
    staleTime: STALE,
  });
  const customers = useQuery({
    queryKey: ['customers-raw', workspaceId],
    queryFn: () => listCustomers(workspaceId as string),
    enabled: !!workspaceId,
    staleTime: STALE,
  });

  const isCompleted = appointment.data?.status === 'completed';
  const sale = useSaleByAppointment(appointmentId, canManage && isCompleted);
  const update = useUpdateAppointment(appointmentId);

  /**
   * Marca la cita como completada (el backend genera la venta) y devuelve la venta, o null si no se generó.
   * También sirve para reintentar cuando la cita ya estaba completada pero la venta falló.
   */
  const complete = async (): Promise<SalesOrderOut | null> => {
    await update.mutateAsync({ body: { status: 'completed' } });
    await queryClient.invalidateQueries({ queryKey: ['appointment', workspaceId, appointmentId] });
    await queryClient.invalidateQueries({ queryKey: ['accounting', workspaceId] });
    return queryClient.fetchQuery({
      queryKey: ['accounting', workspaceId, 'sale-by-appointment', appointmentId],
      queryFn: () => getSalesOrderByAppointment(workspaceId as string, appointmentId),
      staleTime: 0,
    });
  };

  const cancelMutation = useCancelAppointment(appointmentId);
  const status = appointment.data?.status;

  return {
    canCancel: canCancelAppointments(role) && (status === 'pending' || status === 'confirmed'),
    /** Cancela la cita; el backend avisa al cliente por WhatsApp. Lanza si falla (el toast ya salió). */
    cancel: () => cancelMutation.mutateAsync(),
    isCancelling: cancelMutation.isPending,
    appointment,
    service: services.data?.find((s) => s.id === appointment.data?.service_id) ?? null,
    customer: customers.data?.find((c) => c.id === appointment.data?.customer_id) ?? null,
    sale,
    canManage,
    isCompleted,
    complete,
    isCompleting: update.isPending,
  };
}
