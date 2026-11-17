// React Query hook del dashboard: gráficas y cosas por hacer.

import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/lib/auth-context';
import { getDashboardInsights, type DashboardInsights } from '@/lib/api/dashboard';

export function useDashboardInsights() {
  const { workspaceId } = useAuth();
  return useQuery<DashboardInsights, Error>({
    queryKey: ['dashboard-insights', workspaceId],
    queryFn: () => getDashboardInsights(workspaceId!),
    enabled: !!workspaceId,
    staleTime: 2 * 60 * 1000,
    refetchOnWindowFocus: true, // al volver a la pestaña se actualiza: es lo primero que se mira
  });
}
