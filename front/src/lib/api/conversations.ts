// T019 — Módulo de API de clientes, conversaciones y mensajes

import { apiFetch } from './client';
import type { CustomerOut, CustomerUpdate, ConversationOut, MessageOut } from '../types/api';

// ── Customers ─────────────────────────────────────────────────────────────────

/** GET /workspaces/{workspaceId}/customers */
export async function listCustomers(workspaceId: string): Promise<CustomerOut[]> {
  return apiFetch<CustomerOut[]>(`/workspaces/${workspaceId}/customers`);
}

/** GET /workspaces/{workspaceId}/customers/{customerId} */
export async function getCustomer(workspaceId: string, customerId: string): Promise<CustomerOut> {
  return apiFetch<CustomerOut>(`/workspaces/${workspaceId}/customers/${customerId}`);
}

/** PATCH /workspaces/{workspaceId}/customers/{customerId} */
export async function updateCustomer(
  workspaceId: string,
  customerId: string,
  body: CustomerUpdate,
): Promise<CustomerOut> {
  return apiFetch<CustomerOut>(`/workspaces/${workspaceId}/customers/${customerId}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

// ── Conversations ─────────────────────────────────────────────────────────────

/** GET /workspaces/{workspaceId}/conversations */
export async function listConversations(
  workspaceId: string,
  status?: string,
): Promise<ConversationOut[]> {
  const qs = status ? `?status=${status}` : '';
  return apiFetch<ConversationOut[]>(`/workspaces/${workspaceId}/conversations${qs}`);
}

/** GET /workspaces/{workspaceId}/conversations/{conversationId} */
export async function getConversation(
  workspaceId: string,
  conversationId: string,
): Promise<ConversationOut> {
  return apiFetch<ConversationOut>(`/workspaces/${workspaceId}/conversations/${conversationId}`);
}

/** GET /workspaces/{workspaceId}/conversations/{conversationId}/messages */
export async function listMessages(
  workspaceId: string,
  conversationId: string,
): Promise<MessageOut[]> {
  return apiFetch<MessageOut[]>(
    `/workspaces/${workspaceId}/conversations/${conversationId}/messages`,
  );
}
