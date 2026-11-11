// Resumen de un cliente. Cuelga de ['accounting', ws, ...] para que cobrar/anular un pago lo refresque solo.

import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/lib/auth-context';
import { getCustomerSummary } from '@/lib/api/conversations';

export function useCustomerSummary(customerId: string) {
  const { workspaceId } = useAuth();
  return useQuery({
    queryKey: ['accounting', workspaceId, 'customer-summary', customerId],
    queryFn: () => getCustomerSummary(workspaceId as string, customerId),
    enabled: !!workspaceId && !!customerId,
    staleTime: 30 * 1000,
  });
}
