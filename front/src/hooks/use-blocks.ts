// React Query hooks para bloqueos de agenda

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { useAuth } from '@/lib/auth-context';
import { createBlock, deleteBlock, listBlocks } from '@/lib/api/blocks';
import type { AvailabilityBlockOut } from '@/lib/types/api';

const STALE = 30 * 1000;

/** Bloqueos que tocan el rango de días (YYYY-MM-DD, días del negocio). */
export function useBlocks(range: { from_date: string; to_date: string }) {
  const { workspaceId } = useAuth();
  return useQuery<AvailabilityBlockOut[], Error>({
    queryKey: ['blocks', workspaceId, range.from_date, range.to_date],
    queryFn: async () => (workspaceId ? listBlocks(workspaceId, range) : []),
    enabled: !!workspaceId,
    staleTime: STALE,
  });
}

interface CreateBlocksInput {
  /** Un bloqueo por calendario: «todo el equipo» es uno por cada profesional. */
  calendarIds: string[];
  start_at: string;
  end_at: string;
  reason?: string;
}

interface CreateBlocksResult {
  created: number;
  failed: number;
  /** Citas ya agendadas dentro del bloqueo: no se cancelan solas. */
  appointmentsInRange: number;
}

const detailOf = (error: unknown, fallback: string) =>
  (error as { detail?: string }).detail ?? (error as Error).message ?? fallback;

/** Mutación — bloquear un horario en uno o varios calendarios. */
export function useCreateBlocks() {
  const { workspaceId } = useAuth();
  const qc = useQueryClient();
  return useMutation<CreateBlocksResult, Error, CreateBlocksInput>({
    mutationFn: async ({ calendarIds, start_at, end_at, reason }) => {
      if (!workspaceId) throw new Error('No workspace');
      const results = await Promise.allSettled(
        calendarIds.map((calendar_id) => createBlock(workspaceId, { calendar_id, start_at, end_at, reason })),
      );
      const ok = results.filter((r): r is PromiseFulfilledResult<Awaited<ReturnType<typeof createBlock>>> => r.status === 'fulfilled');
      const bad = results.filter((r): r is PromiseRejectedResult => r.status === 'rejected');
      if (ok.length === 0 && bad.length > 0) throw bad[0].reason;
      return {
        created: ok.length,
        failed: bad.length,
        appointmentsInRange: ok.reduce((sum, r) => sum + r.value.appointments_in_range, 0),
      };
    },
    onSuccess: ({ created, failed, appointmentsInRange }) => {
      qc.invalidateQueries({ queryKey: ['blocks', workspaceId] });
      if (failed > 0) toast.warning(`Se bloquearon ${created} de ${created + failed} calendarios. Inténtalo de nuevo con el resto.`);
      else toast.success('Horario bloqueado. El agente ya no ofrecerá ese horario.');
      if (appointmentsInRange > 0) {
        toast.warning(
          `Ya había ${appointmentsInRange} cita${appointmentsInRange === 1 ? '' : 's'} agendada${appointmentsInRange === 1 ? '' : 's'} en ese horario: `
          + 'el bloqueo no las cancela. Muévelas o cancélalas desde la agenda.',
        );
      }
    },
    onError: (error) => toast.error(detailOf(error, 'No se pudo bloquear el horario')),
  });
}

/** Mutación — quitar uno o varios bloqueos (los de un mismo tramo en distintos calendarios). */
export function useDeleteBlocks() {
  const { workspaceId } = useAuth();
  const qc = useQueryClient();
  return useMutation<void, Error, string[]>({
    mutationFn: async (ids) => {
      if (!workspaceId) throw new Error('No workspace');
      await Promise.all(ids.map((id) => deleteBlock(workspaceId, id)));
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['blocks', workspaceId] });
      toast.success('Bloqueo quitado. Ese horario vuelve a estar disponible.');
    },
    onError: (error) => toast.error(detailOf(error, 'No se pudo quitar el bloqueo')),
  });
}
