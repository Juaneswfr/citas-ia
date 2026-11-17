// React Query hook del historial de citas

import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useAuth } from '@/lib/auth-context';
import { fetchHistory, type HistoryFilters, type HistoryPage } from '@/lib/api/appointment-history';

export const HISTORY_PAGE_SIZE = 25;

export function useAppointmentHistory(filters: HistoryFilters, page: number) {
  const { workspaceId } = useAuth();
  return useQuery<HistoryPage, Error>({
    queryKey: ['appointment-history', workspaceId, filters, page],
    queryFn: () => fetchHistory(workspaceId!, filters, HISTORY_PAGE_SIZE, page * HISTORY_PAGE_SIZE),
    enabled: !!workspaceId,
    staleTime: 30_000,
    placeholderData: keepPreviousData, // al cambiar de página o de filtro se sigue viendo lo anterior
  });
}
