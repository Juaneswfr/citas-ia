// T023 — React Query hooks para conversaciones y mensajes

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { useAuth } from '@/lib/auth-context';
import { listConversations, listMessages, sendMessage } from '@/lib/api/conversations';
import type { ConversationOut, MessageOut } from '@/lib/types/api';

const STALE = 30 * 1000; // 30 seg (las conversaciones cambian frecuentemente)
// El chat se actualiza solo: no hay websockets, se vuelve a consultar cada pocos segundos.
const POLL_LIST = 15 * 1000;
const POLL_CHAT = 5 * 1000;
/** Ventana de atención de WhatsApp: texto libre solo hasta 24 h después del último mensaje del cliente. */
const WINDOW_MS = 24 * 60 * 60 * 1000;

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
    refetchInterval: POLL_LIST,
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
    refetchInterval: POLL_CHAT,
  });
}

/** Momento en que se cierra la ventana de 24 h, o null si el cliente nunca ha escrito. */
export function replyWindowEnd(conv: Pick<ConversationOut, 'last_inbound_at'>): Date | null {
  if (!conv.last_inbound_at) return null;
  return new Date(new Date(conv.last_inbound_at).getTime() + WINDOW_MS);
}

/** Mutación — responder al cliente desde Hilo */
export function useSendMessage(conversationId: string) {
  const { workspaceId } = useAuth();
  const queryClient = useQueryClient();
  return useMutation<MessageOut, Error, string>({
    mutationFn: (text) => {
      if (!workspaceId) throw new Error('No workspace');
      return sendMessage(workspaceId, conversationId, text);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['messages', workspaceId, conversationId] });
      queryClient.invalidateQueries({ queryKey: ['conversations', workspaceId] });
    },
    onError: (error) => {
      toast.error((error as { detail?: string }).detail ?? 'No se pudo enviar el mensaje.');
      // Si WhatsApp cerró la ventana, la lista trae el estado real.
      queryClient.invalidateQueries({ queryKey: ['conversations', workspaceId] });
    },
  });
}
