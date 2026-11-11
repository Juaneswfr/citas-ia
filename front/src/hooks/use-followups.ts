// React Query hooks del seguimiento por WhatsApp. Todo cuelga de ['followups', workspaceId, ...].

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { useAuth } from '@/lib/auth-context';
import * as api from '@/lib/api/followups';
import type { FollowupSettings, FollowupTemplatesOut } from '@/lib/types/followups';

const errorText = (error: Error, fallback: string) =>
  (error as { detail?: string }).detail ?? error.message ?? fallback;

export function useFollowupSettings() {
  const { workspaceId } = useAuth();
  return useQuery<FollowupSettings, Error>({
    queryKey: ['followups', workspaceId, 'settings'],
    queryFn: () => api.getFollowupSettings(workspaceId as string),
    enabled: !!workspaceId,
    staleTime: 60_000,
  });
}

export function useUpdateFollowupSettings() {
  const { workspaceId } = useAuth();
  const queryClient = useQueryClient();
  return useMutation<FollowupSettings, Error, FollowupSettings>({
    mutationFn: (body) => api.updateFollowupSettings(workspaceId as string, body),
    onSuccess: (saved) => {
      queryClient.setQueryData(['followups', workspaceId, 'settings'], saved);
      toast.success('Seguimiento guardado');
    },
    onError: (error) => toast.error(errorText(error, 'Error al guardar el seguimiento')),
  });
}

export function useFollowupTemplates() {
  const { workspaceId } = useAuth();
  return useQuery<FollowupTemplatesOut, Error>({
    queryKey: ['followups', workspaceId, 'templates'],
    queryFn: () => api.listFollowupTemplates(workspaceId as string),
    enabled: !!workspaceId,
    staleTime: 60_000,
  });
}

/** `activate` crea las plantillas que falten; `sync` solo vuelve a consultar su estado de aprobación. */
export function useFollowupTemplateAction(action: 'activate' | 'sync') {
  const { workspaceId } = useAuth();
  const queryClient = useQueryClient();
  const run = action === 'activate' ? api.activateFollowupTemplates : api.syncFollowupTemplates;
  return useMutation<FollowupTemplatesOut, Error, void>({
    mutationFn: () => run(workspaceId as string),
    onSuccess: (result) => {
      queryClient.setQueryData(['followups', workspaceId, 'templates'], result);
      toast.success(action === 'activate' ? 'Plantillas enviadas a revisión de WhatsApp' : 'Estado actualizado');
    },
    onError: (error) => toast.error(errorText(error, 'No se pudo contactar a WhatsApp')),
  });
}
