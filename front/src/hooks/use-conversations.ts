// T023 — React Query hooks para conversaciones y mensajes

import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/lib/auth-context';
import { listConversations, listMessages } from '@/lib/api/conversations';
import type { ConversationOut, MessageOut } from '@/lib/types/api';

const STALE = 30 * 1000; // 30 seg (las conversaciones cambian frecuentemente)

/** React Query hook — lista de conversaciones del workspace */
export function useConversations(status?: string) {
  const { workspaceId } = useAuth();
  return useQuery<ConversationOut[], Error>({
    queryKey: ['conversations', workspaceId, status],
    queryFn: async () => {
      if (!workspaceId) return [];
      return listConversations(workspaceId, status);
    },
    enabled: !!workspaceId,
    staleTime: STALE,
  });
}

/** React Query hook — mensajes de una conversación específica */
export function useMessages(conversationId: string) {
  const { workspaceId } = useAuth();
  return useQuery<MessageOut[], Error>({
    queryKey: ['messages', workspaceId, conversationId],
    queryFn: async () => {
      if (!workspaceId || !conversationId) return [];
      return listMessages(workspaceId, conversationId);
    },
    enabled: !!workspaceId && !!conversationId,
    staleTime: STALE,
  });
}
