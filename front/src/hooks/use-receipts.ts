// React Query hooks de los comprobantes recibidos por WhatsApp.
// Cuelgan de ['accounting', workspaceId, 'receipts', ...]: aprobar uno registra un cobro,
// así que la invalidación del árbol de finanzas refresca también ventas, movimientos y resumen.

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/lib/auth-context';
import { canManageFinance } from '@/lib/nav';
import * as api from '@/lib/api/receipts';
import type { ReceiptApprove, ReceiptStatus } from '@/lib/types/receipts';
import { useAccountingMutation, useAccountingQuery } from './use-accounting';

export const useReceipts = (status?: ReceiptStatus) =>
  useAccountingQuery(['receipts', 'list', status], (w) => api.listReceipts(w, status));

export const useReceipt = (receiptId: string) =>
  useAccountingQuery(['receipts', 'detail', receiptId], (w) => api.getReceipt(w, receiptId));

/** Pendientes de revisión (para los contadores). Solo consulta si el rol puede ver finanzas. */
export function usePendingReceiptCount(): number {
  const { workspaceId, role } = useAuth();
  const { data } = useQuery({
    queryKey: ['accounting', workspaceId, 'receipts', 'count'],
    queryFn: () => api.countPendingReceipts(workspaceId as string),
    enabled: !!workspaceId && canManageFinance(role),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
  return data?.pending ?? 0;
}

export const useApproveReceipt = () =>
  useAccountingMutation((w, v: { id: string; body: ReceiptApprove }) => api.approveReceipt(w, v.id, v.body),
    { success: 'Cobro registrado con su comprobante', error: 'Error al aprobar el comprobante' });

export const useRejectReceipt = () =>
  useAccountingMutation((w, v: { id: string; reason: string }) => api.rejectReceipt(w, v.id, v.reason),
    { success: 'Comprobante rechazado', error: 'Error al rechazar el comprobante' });

/**
 * URL local (blob) del archivo de un comprobante. La descarga exige el JWT, así que no se puede
 * usar la ruta del API directamente en un <img>. La URL se libera al desmontar.
 */
export function useReceiptFile(receiptId: string) {
  const { workspaceId } = useAuth();
  const { data: blob, isLoading, isError } = useQuery({
    queryKey: ['accounting', workspaceId, 'receipts', 'file', receiptId],
    queryFn: () => api.downloadReceipt(workspaceId as string, receiptId),
    enabled: !!workspaceId,
    staleTime: 5 * 60_000,
  });
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!blob) return;
    const objectUrl = URL.createObjectURL(blob);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [blob]);
  return { url, isLoading, isError };
}
