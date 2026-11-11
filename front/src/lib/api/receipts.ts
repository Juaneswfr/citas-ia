// Módulo de API de comprobantes recibidos por WhatsApp: /workspaces/{id}/accounting/receipts

import { apiDownload, apiFetch } from './client';
import type { ReceiptApprove, ReceiptDetailOut, ReceiptOut, ReceiptStatus } from '../types/receipts';

const base = (workspaceId: string) => `/workspaces/${workspaceId}/accounting/receipts`;
const post = <T>(path: string, body: unknown) => apiFetch<T>(path, { method: 'POST', body: JSON.stringify(body) });

export const listReceipts = (workspaceId: string, status?: ReceiptStatus) =>
  apiFetch<ReceiptOut[]>(`${base(workspaceId)}${status ? `?status=${status}` : ''}`);

export const countPendingReceipts = (workspaceId: string) =>
  apiFetch<{ pending: number }>(`${base(workspaceId)}/count`);

export const getReceipt = (workspaceId: string, receiptId: string) =>
  apiFetch<ReceiptDetailOut>(`${base(workspaceId)}/${receiptId}`);

/** El archivo exige el JWT: se baja como Blob y se muestra con una URL local. */
export const downloadReceipt = (workspaceId: string, receiptId: string) =>
  apiDownload(`${base(workspaceId)}/${receiptId}/file`);

export const approveReceipt = (workspaceId: string, receiptId: string, body: ReceiptApprove) =>
  post<ReceiptOut>(`${base(workspaceId)}/${receiptId}/approve`, body);

export const rejectReceipt = (workspaceId: string, receiptId: string, reason: string) =>
  post<ReceiptOut>(`${base(workspaceId)}/${receiptId}/reject?confirmed=true`, { reason: reason || null });
