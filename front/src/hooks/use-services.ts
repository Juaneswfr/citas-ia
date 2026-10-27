// T012 — React Query hooks para servicios

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { useAuth } from '@/lib/auth-context';
import { listServices, createService, updateService, deactivateService } from '@/lib/api/services';
import { toHiloService } from '@/lib/api/adapters';
import type { HiloService } from '@/lib/hilo-data';
import type { ServiceCreate, ServiceUpdate } from '@/lib/types/api';

const STALE = 5 * 60 * 1000; // 5 min

/** React Query hook — lista servicios del workspace */
export function useServices(activeOnly?: boolean) {
  const { workspaceId } = useAuth();
  return useQuery<HiloService[], Error>({
    queryKey: ['services', workspaceId, activeOnly],
    queryFn: async () => {
      if (!workspaceId) return [];
      const svcs = await listServices(workspaceId, activeOnly);
      return svcs.map((svc, i) => toHiloService(svc, i));
    },
    enabled: !!workspaceId,
    staleTime: STALE,
  });
}

/** React Query mutation — crear servicio */
export function useCreateService() {
  const { workspaceId } = useAuth();
  const qc = useQueryClient();
  return useMutation<HiloService, Error, ServiceCreate>({
    mutationFn: async (body) => {
      if (!workspaceId) throw new Error('No workspace');
      const existing = qc.getQueryData<HiloService[]>(['services', workspaceId]) ?? [];
      const svc = await createService(workspaceId, body);
      return toHiloService(svc, existing.length);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['services', workspaceId] });
      toast.success('Servicio creado');
    },
    onError: (error) => {
      toast.error((error as { detail?: string }).detail ?? error.message ?? 'Error al crear servicio');
    },
  });
}

/** React Query mutation — actualizar servicio */
export function useUpdateService(serviceId: string) {
  const { workspaceId } = useAuth();
  const qc = useQueryClient();
  return useMutation<HiloService, Error, ServiceUpdate>({
    mutationFn: async (body) => {
      if (!workspaceId) throw new Error('No workspace');
      const existing = qc.getQueryData<HiloService[]>(['services', workspaceId]) ?? [];
      const idx = existing.findIndex(s => s.id === serviceId);
      const svc = await updateService(workspaceId, serviceId, body);
      return toHiloService(svc, idx >= 0 ? idx : existing.length);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['services', workspaceId] });
      toast.success('Cambios guardados');
    },
    onError: (error) => {
      toast.error((error as { detail?: string }).detail ?? error.message ?? 'Error al guardar');
    },
  });
}

/** React Query mutation — desactivar servicio (soft delete) */
export function useDeactivateService() {
  const { workspaceId } = useAuth();
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: async (svcId) => {
      if (!workspaceId) throw new Error('No workspace');
      await deactivateService(workspaceId, svcId);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['services', workspaceId] });
      toast.success('Servicio desactivado');
    },
    onError: (error) => {
      toast.error((error as { detail?: string }).detail ?? error.message ?? 'Error al desactivar');
    },
  });
}
