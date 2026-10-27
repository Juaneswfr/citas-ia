// T021 — React Query hooks para clientes

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { useAuth } from '@/lib/auth-context';
import { listCustomers, updateCustomer } from '@/lib/api/conversations';
import { listAppointments } from '@/lib/api/appointments';
import { listServices } from '@/lib/api/services';
import { toHiloClient } from '@/lib/api/adapters';
import type { HiloClient } from '@/lib/hilo-data';
import type { CustomerUpdate, AppointmentOut, ServiceOut } from '@/lib/types/api';

const STALE = 5 * 60 * 1000; // 5 min

/** React Query hook — lista de clientes enriquecidos con stats de citas */
export function useCustomers() {
  const { workspaceId } = useAuth();
  return useQuery<HiloClient[], Error>({
    queryKey: ['customers', workspaceId],
    queryFn: async () => {
      if (!workspaceId) return [];
      // Cargar en paralelo: clientes, todas las citas y servicios (para derivar stats)
      const [customers, appointments, services] = await Promise.all([
        listCustomers(workspaceId),
        listAppointments(workspaceId),
        listServices(workspaceId),
      ]);

      const servicesMap = new Map<string, ServiceOut>(services.map(s => [s.id, s]));

      // Agrupar citas por customer_id
      const aptsByCustomer = new Map<string, AppointmentOut[]>();
      for (const apt of appointments) {
        const existing = aptsByCustomer.get(apt.customer_id) ?? [];
        existing.push(apt);
        aptsByCustomer.set(apt.customer_id, existing);
      }

      return customers.map(c =>
        toHiloClient(c, aptsByCustomer.get(c.id) ?? [], servicesMap),
      );
    },
    enabled: !!workspaceId,
    staleTime: STALE,
  });
}

/** React Query mutation — actualizar datos de un cliente */
export function useUpdateCustomer(customerId: string) {
  const { workspaceId } = useAuth();
  const qc = useQueryClient();
  return useMutation<void, Error, CustomerUpdate>({
    mutationFn: async (body) => {
      if (!workspaceId) throw new Error('No workspace');
      await updateCustomer(workspaceId, customerId, body);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['customers', workspaceId] });
      toast.success('Cliente actualizado');
    },
    onError: (error) => {
      toast.error((error as { detail?: string }).detail ?? error.message ?? 'Error al actualizar cliente');
    },
  });
}
