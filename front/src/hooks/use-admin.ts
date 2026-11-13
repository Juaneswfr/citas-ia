// Hooks del panel de administración de la plataforma (solo super_admin).

import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { adminService } from '@/lib/api/admin';
import { ApiError } from '@/lib/api/client';
import type { AdminWorkspaceFilters, AdminWorkspaceUpdate } from '@/lib/types/admin';

const errorDetail = (error: unknown, fallback: string) =>
  error instanceof ApiError ? error.detail : fallback;

export function useAdminOverview() {
  return useQuery({ queryKey: ['admin', 'overview'], queryFn: adminService.getOverview });
}

/** Cada consulta hace una llamada real a Anthropic y a Kapso: no se repite sola, solo con «Volver a comprobar». */
export function useAdminHealth() {
  return useQuery({
    queryKey: ['admin', 'health'],
    queryFn: adminService.getHealth,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    retry: false,
  });
}

export function useAdminWorkspaces(filters: AdminWorkspaceFilters, page: number) {
  return useQuery({
    queryKey: ['admin', 'workspaces', filters, page],
    queryFn: () => adminService.listWorkspaces(filters, page),
    placeholderData: keepPreviousData, // la lista no parpadea al escribir en el buscador o paginar
  });
}

export function useAdminWorkspace(workspaceId: string) {
  return useQuery({
    queryKey: ['admin', 'workspace', workspaceId],
    queryFn: () => adminService.getWorkspace(workspaceId),
  });
}

export function useUpdateAdminWorkspace(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: AdminWorkspaceUpdate) => adminService.updateWorkspace(workspaceId, body),
    onSuccess: (detail) => {
      queryClient.setQueryData(['admin', 'workspace', workspaceId], detail);
      queryClient.invalidateQueries({ queryKey: ['admin', 'workspaces'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'overview'] });
      toast.success('Negocio actualizado');
    },
    onError: (error) => toast.error(errorDetail(error, 'No se pudo actualizar el negocio')),
  });
}

export function useAdminUsers(search: string, page: number) {
  return useQuery({
    queryKey: ['admin', 'users', search, page],
    queryFn: () => adminService.listUsers(search, page),
    placeholderData: keepPreviousData,
  });
}

export function useSetAdminUserActive() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, isActive }: { userId: string; isActive: boolean }) =>
      adminService.setUserActive(userId, isActive),
    onSuccess: (_data, { isActive }) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
      toast.success(isActive ? 'Acceso restablecido' : 'Acceso bloqueado');
    },
    onError: (error) => toast.error(errorDetail(error, 'No se pudo actualizar el usuario')),
  });
}
