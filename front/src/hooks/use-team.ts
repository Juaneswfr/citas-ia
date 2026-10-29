import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/lib/auth-context';
import { listMembers } from '@/lib/api/workspaces';
import type { MemberOut } from '@/lib/types/api';

export function useTeamMembers() {
  const { workspaceId } = useAuth();
  return useQuery<MemberOut[], Error>({
    queryKey: ['team', workspaceId],
    queryFn: () => listMembers(workspaceId!),
    enabled: !!workspaceId,
    staleTime: 5 * 60 * 1000,
  });
}
