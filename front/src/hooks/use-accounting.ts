// React Query hooks del módulo de finanzas.
// Todas las queries cuelgan de ['accounting', workspaceId, ...]; cualquier mutación invalida el árbol completo
// porque un cobro afecta ventas, movimientos, resumen y comisiones a la vez.

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { useAuth } from '@/lib/auth-context';
import * as api from '@/lib/api/accounting';
import type {
  CompensationUpsert, MovementCreate, PaymentCreate, PaymentMethod, PurchaseOrderCreate,
  SalesOrderCreate, ThirdPartyCreate,
} from '@/lib/types/accounting';
import { latestPaymentId, validateReceipt } from '@/lib/receipts';

const STALE = 30 * 1000;

/** Query genérica del módulo: se activa solo cuando hay workspace. */
export function useAccountingQuery<T>(key: unknown[], fetcher: (workspaceId: string) => Promise<T>) {
  const { workspaceId } = useAuth();
  return useQuery<T, Error>({
    queryKey: ['accounting', workspaceId, ...key],
    queryFn: () => fetcher(workspaceId as string),
    enabled: !!workspaceId,
    staleTime: STALE,
  });
}

/** Mutación genérica: llama a la API con el workspace, invalida y notifica. */
export function useAccountingMutation<TVars, TOut>(
  run: (workspaceId: string, vars: TVars) => Promise<TOut>,
  messages: { success: string; error: string },
) {
  const { workspaceId } = useAuth();
  const queryClient = useQueryClient();
  return useMutation<TOut, Error, TVars>({
    mutationFn: (vars) => {
      if (!workspaceId) throw new Error('No workspace');
      return run(workspaceId, vars);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounting', workspaceId] });
      toast.success(messages.success);
    },
    onError: (error) => {
      toast.error((error as { detail?: string }).detail ?? error.message ?? messages.error);
    },
  });
}

// ── Lecturas ──────────────────────────────────────────────────────────────────

export const useSummary = (month: string) =>
  useAccountingQuery(['summary', month], (w) => api.getSummary(w, month));

export const useSalesOrders = (status?: string) =>
  useAccountingQuery(['sales', status], (w) => api.listSalesOrders(w, status));

export const usePurchaseOrders = (status?: string) =>
  useAccountingQuery(['purchases', status], (w) => api.listPurchaseOrders(w, status));

export const useMovements = (from?: string, to?: string) =>
  useAccountingQuery(['movements', from, to], (w) => api.listMovements(w, from, to));

export const useThirdParties = () =>
  useAccountingQuery(['third-parties'], (w) => api.listThirdParties(w));

/** Venta de una cita (null si aún no está completada). Solo se consulta si hay cita y permiso. */
export function useSaleByAppointment(appointmentId: string | null, enabled = true) {
  const { workspaceId } = useAuth();
  return useQuery({
    queryKey: ['accounting', workspaceId, 'sale-by-appointment', appointmentId],
    queryFn: () => api.getSalesOrderByAppointment(workspaceId as string, appointmentId as string),
    enabled: !!workspaceId && !!appointmentId && enabled,
    staleTime: 0,
  });
}

export const useAttachments = (movementId: string) =>
  useAccountingQuery(['attachments', movementId], (w) => api.listAttachments(w, movementId));

export const useCategories = () =>
  useAccountingQuery(['categories'], (w) => api.listCategories(w));

export const useCompensation = () =>
  useAccountingQuery(['compensation'], (w) => api.listCompensation(w));

export const usePayouts = () =>
  useAccountingQuery(['payouts'], (w) => api.listPayouts(w));

export const useCommissions = () =>
  useAccountingQuery(['commissions'], (w) => api.getCommissions(w));

/** Vista previa de una liquidación; solo se consulta con miembro y periodo completos. */
export function usePayoutPreview(memberId: string, start: string, end: string) {
  const { workspaceId } = useAuth();
  return useQuery({
    queryKey: ['accounting', workspaceId, 'payout-preview', memberId, start, end],
    queryFn: () => api.previewPayout(workspaceId as string, memberId, start, end),
    enabled: !!workspaceId && !!memberId && !!start && !!end && end >= start,
    staleTime: 0,
  });
}

// ── Escrituras ────────────────────────────────────────────────────────────────

export const useCreateSalesOrder = () =>
  useAccountingMutation((w, body: SalesOrderCreate) => api.createSalesOrder(w, body),
    { success: 'Venta registrada', error: 'Error al registrar la venta' });

export const usePaySalesOrder = () =>
  useAccountingMutation((w, v: { id: string; body: PaymentCreate }) => api.paySalesOrder(w, v.id, v.body),
    { success: 'Cobro registrado', error: 'Error al registrar el cobro' });

export const useVoidSalesOrder = () =>
  useAccountingMutation((w, id: string) => api.voidSalesOrder(w, id),
    { success: 'Venta anulada', error: 'Error al anular la venta' });

export const useCreatePurchaseOrder = () =>
  useAccountingMutation((w, body: PurchaseOrderCreate) => api.createPurchaseOrder(w, body),
    { success: 'Compra registrada', error: 'Error al registrar la compra' });

export const usePayPurchaseOrder = () =>
  useAccountingMutation((w, v: { id: string; body: PaymentCreate }) => api.payPurchaseOrder(w, v.id, v.body),
    { success: 'Pago registrado', error: 'Error al registrar el pago' });

export const useVoidPurchaseOrder = () =>
  useAccountingMutation((w, id: string) => api.voidPurchaseOrder(w, id),
    { success: 'Compra anulada', error: 'Error al anular la compra' });

export const useCreateMovement = () =>
  useAccountingMutation((w, body: MovementCreate) => api.createMovement(w, body),
    { success: 'Movimiento registrado', error: 'Error al registrar el movimiento' });

export const useVoidMovement = () =>
  useAccountingMutation((w, id: string) => api.voidMovement(w, id),
    { success: 'Movimiento anulado', error: 'Error al anular el movimiento' });

export const useCreateThirdParty = () =>
  useAccountingMutation((w, body: ThirdPartyCreate) => api.createThirdParty(w, body),
    { success: 'Tercero creado', error: 'Error al crear el tercero' });

export const useSaveCompensation = () =>
  useAccountingMutation((w, v: { memberId: string; body: CompensationUpsert }) =>
    api.saveCompensation(w, v.memberId, v.body),
    { success: 'Regla de pago guardada', error: 'Error al guardar la regla' });

export const useCreatePayout = () =>
  useAccountingMutation((w, v: { memberId: string; start: string; end: string }) =>
    api.createPayout(w, v.memberId, v.start, v.end),
    { success: 'Liquidación creada', error: 'Error al crear la liquidación' });

export const usePayPayout = () =>
  useAccountingMutation((w, v: { id: string; method: PaymentMethod }) => api.payPayout(w, v.id, v.method),
    { success: 'Liquidación pagada', error: 'Error al pagar la liquidación' });

export const useCancelPayout = () =>
  useAccountingMutation((w, id: string) => api.cancelPayout(w, id),
    { success: 'Liquidación cancelada', error: 'Error al cancelar la liquidación' });

// ── Comprobantes ──────────────────────────────────────────────────────────────

export const useUploadAttachment = () =>
  useAccountingMutation((w, v: { movementId: string; file: File }) => api.uploadAttachment(w, v.movementId, v.file),
    { success: 'Comprobante adjuntado', error: 'Error al adjuntar el comprobante' });

export const useDeleteAttachment = () =>
  useAccountingMutation((w, id: string) => api.deleteAttachment(w, id),
    { success: 'Comprobante eliminado', error: 'Error al eliminar el comprobante' });

/**
 * Registra un cobro (venta) o pago (compra) y, si se eligió un archivo, lo adjunta al movimiento creado.
 * Si el cobro se registra pero el archivo falla, el cobro NO se revierte: se avisa para reintentar desde la orden.
 */
export function usePayWithReceipt(kind: 'sales' | 'purchases') {
  const paySale = usePaySalesOrder();
  const payPurchase = usePayPurchaseOrder();
  const upload = useUploadAttachment();
  const pay = kind === 'sales' ? paySale : payPurchase;

  const submit = async (orderId: string, body: PaymentCreate, receipt: File | null) => {
    const invalid = receipt ? validateReceipt(receipt) : null;
    if (invalid) {
      toast.error(invalid);
      throw new Error(invalid);
    }
    const order = await pay.mutateAsync({ id: orderId, body });
    if (!receipt) return order;
    const movementId = latestPaymentId(order.payments);
    if (!movementId) return order;
    try {
      await upload.mutateAsync({ movementId, file: receipt });
    } catch {
      toast.error('El cobro quedó registrado, pero el comprobante no se pudo adjuntar. Adjúntalo desde la orden.');
    }
    return order;
  };

  return { submit, isPending: pay.isPending || upload.isPending };
}

/**
 * Abre un comprobante en una pestaña nueva. La descarga exige el JWT, así que se baja como Blob.
 * La pestaña se abre ANTES del await para que el bloqueador de ventanas emergentes no la impida.
 */
export function useOpenAttachment() {
  const { workspaceId } = useAuth();
  return async (attachmentId: string, fileName: string) => {
    if (!workspaceId) return;
    const tab = window.open('', '_blank');
    try {
      const blob = await api.downloadAttachment(workspaceId, attachmentId);
      const url = URL.createObjectURL(blob);
      if (tab) {
        tab.location.href = url;
      } else {
        const link = document.createElement('a');
        link.href = url;
        link.download = fileName;
        link.click();
      }
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (error) {
      tab?.close();
      toast.error((error as { detail?: string }).detail ?? 'No se pudo abrir el comprobante');
    }
  };
}
