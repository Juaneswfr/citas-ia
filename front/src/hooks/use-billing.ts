// Hooks de plan, suscripción y facturación. El dueño ve su plan; el super_admin opera el cobro manual.

import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { format, parseISO } from 'date-fns';
import { toast } from 'sonner';
import { useAuth } from '@/lib/auth-context';
import { adminBillingService, billingService, listPlans } from '@/lib/api/billing';
import { ApiError } from '@/lib/api/client';
import type { ActivatePlanBody, BillingProfile, CarteraScope, Issuer, PlanChanges } from '@/lib/types/billing';

const errorDetail = (error: unknown, fallback: string) => (error instanceof ApiError ? error.detail : fallback);

/** Plan, uso y facturas del negocio. Solo el dueño (o super_admin) puede pedirlo: el resto recibiría 403. */
export function useBillingSummary(enabled = true) {
  const { me, role } = useAuth();
  const workspaceId = me?.workspace_id ?? '';
  const allowed = role === 'workspace_owner' || role === 'super_admin';
  return useQuery({
    queryKey: ['billing', 'summary', workspaceId],
    queryFn: () => billingService.getSummary(workspaceId),
    enabled: enabled && !!workspaceId && allowed,
    staleTime: 60_000,
    retry: false,
  });
}

/** Saldo de citas del asistente y de profesionales. Lo puede ver todo el equipo (no trae precios ni facturas). */
export function useBillingUsage() {
  const { me } = useAuth();
  const workspaceId = me?.workspace_id ?? '';
  return useQuery({
    queryKey: ['billing', 'usage', workspaceId],
    queryFn: () => billingService.getUsage(workspaceId),
    enabled: !!workspaceId,
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: false,
  });
}

/** Pedir más citas: quedan acreditadas de inmediato y se crea el saldo pendiente. */
export function useRequestAppointments(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (quantity: number) => billingService.requestAppointments(workspaceId, quantity),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['billing'] });
      toast.success(
        `Sumamos ${res.quantity} citas hasta el ${format(parseISO(res.valid_until), 'd/MM')}. ` +
        `Quedó un saldo pendiente de $${res.amount_cop.toLocaleString('es-CO')} que vence el ${format(parseISO(res.due_date), 'd/MM')}.`,
      );
    },
    onError: (error) => toast.error(errorDetail(error, 'No se pudo pedir las citas adicionales.')),
  });
}

export function useBillingProfile(workspaceId: string) {
  return useQuery({
    queryKey: ['billing', 'profile', workspaceId],
    queryFn: () => billingService.getProfile(workspaceId),
    enabled: !!workspaceId,
  });
}

export function useSaveBillingProfile(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: BillingProfile) => billingService.saveProfile(workspaceId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['billing'] });
      toast.success('Datos de cobro guardados');
    },
    onError: (error) => toast.error(errorDetail(error, 'No se pudieron guardar los datos de cobro.')),
  });
}

export function useCancelSubscription(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (undo: boolean) => billingService.cancel(workspaceId, undo),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['billing'] });
      toast.success(res.cancel_at_period_end ? 'Cancelación programada para el final del ciclo' : 'Cancelación deshecha');
    },
    onError: (error) => toast.error(errorDetail(error, 'No se pudo actualizar la suscripción.')),
  });
}

// ── Super admin ──────────────────────────────────────────────────────────────

export function useBillingOverview() {
  return useQuery({
    queryKey: ['admin', 'billing', 'overview'],
    queryFn: () => adminBillingService.getOverview(),
    staleTime: 60_000,
  });
}

export function useAdminWorkspaceBilling(workspaceId: string) {
  return useQuery({
    queryKey: ['admin', 'billing', 'workspace', workspaceId],
    queryFn: () => adminBillingService.getWorkspace(workspaceId),
  });
}

/** Cualquier acción de cobro refresca la ficha del negocio, la lista y el tablero. */
function useBillingAction<TArgs, TResult>(
  workspaceId: string,
  run: (args: TArgs) => Promise<TResult>,
  success: string | ((result: TResult) => string),
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: run,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['admin'] });
      queryClient.invalidateQueries({ queryKey: ['billing'] });
      toast.success(typeof success === 'function' ? success(result) : success);
    },
    onError: (error) => toast.error(errorDetail(error, 'No se pudo completar la acción.')),
  });
}

export function useBillingActions(workspaceId: string) {
  const activate = useBillingAction(
    workspaceId, (body: ActivatePlanBody) => adminBillingService.activate(workspaceId, body),
    (res) => (res.discount_applied
      ? 'Plan activado con el descuento de lanzamiento'
      : 'Plan activado a valor real: ese número ya había usado el descuento'));
  const payment = useBillingAction(
    workspaceId,
    (a: { invoiceId: string; method: string; reference?: string }) =>
      adminBillingService.registerPayment(a.invoiceId, { payment_method: a.method, payment_reference: a.reference }),
    (res) => (res.reactivated ? 'Pago registrado: el asistente vuelve a atender' : 'Pago registrado'));
  const voidInvoice = useBillingAction(
    workspaceId, (a: { invoiceId: string; reason?: string }) => adminBillingService.voidInvoice(a.invoiceId, a.reason),
    'Factura anulada');
  const extendTrial = useBillingAction(
    workspaceId, (days: number) => adminBillingService.extendTrial(workspaceId, days), 'Prueba extendida');
  const pause = useBillingAction(workspaceId, () => adminBillingService.pause(workspaceId), 'Asistente pausado');
  const reactivate = useBillingAction(
    workspaceId, () => adminBillingService.reactivate(workspaceId), 'Asistente reactivado');
  const changePlan = useBillingAction(
    workspaceId, (plan: 'emprendedor' | 'equipo') => adminBillingService.changePlan(workspaceId, plan),
    (res) => (res.applies === 'now' ? 'Plan cambiado' : 'Bajada de plan agendada para el siguiente ciclo'));
  const addAddon = useBillingAction(
    workspaceId,
    (a: { kind: 'appointments_block' | 'appointments_topup'; quantity: number }) =>
      adminBillingService.addAddon(workspaceId, a.kind, a.quantity),
    'Citas adicionales agregadas');
  const founder = useBillingAction(
    workspaceId, () => adminBillingService.grantFounder(workspaceId), (res) => `Fundador n.º ${res.founder_number}`);
  return { activate, payment, voidInvoice, extendTrial, pause, reactivate, changePlan, addAddon, founder };
}

/** Parámetros de la plataforma, tasa del dólar y tarifa de Meta (alimentan el margen del tablero). */
export function useBillingSettings() {
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['admin', 'billing'] });
  const onError = (error: unknown) => toast.error(errorDetail(error, 'No se pudo guardar.'));
  const setting = useMutation({
    mutationFn: (a: { key: string; value: number }) => adminBillingService.setSetting(a.key, a.value),
    onSuccess: () => { refresh(); toast.success('Parámetro guardado'); }, onError,
  });
  const fx = useMutation({
    mutationFn: (usdCop: number) => adminBillingService.setFx(format(new Date(), 'yyyy-MM-dd'), usdCop),
    onSuccess: () => { refresh(); toast.success('Tasa del dólar guardada'); }, onError,
  });
  const metaRate = useMutation({
    mutationFn: (a: { category: string; usdPrice: number }) =>
      adminBillingService.setMetaRate(a.category, a.usdPrice, format(new Date(), 'yyyy-MM-dd')),
    onSuccess: () => { refresh(); toast.success('Tarifa de Meta guardada'); }, onError,
  });
  return { setting, fx, metaRate };
}

// ── Cartera, cuenta de cobro y costos ────────────────────────────────────────

export function useCartera(scope: CarteraScope) {
  return useQuery({
    queryKey: ['admin', 'billing', 'cartera', scope],
    queryFn: () => adminBillingService.getCartera(scope),
    staleTime: 30_000,
  });
}

export function useBalances() {
  return useQuery({ queryKey: ['admin', 'billing', 'balances'], queryFn: () => adminBillingService.getBalances(), staleTime: 30_000 });
}

export function useUpcoming() {
  return useQuery({ queryKey: ['admin', 'billing', 'upcoming'], queryFn: () => adminBillingService.getUpcoming(), staleTime: 30_000 });
}

export function useIssuer() {
  return useQuery({ queryKey: ['admin', 'billing', 'issuer'], queryFn: () => adminBillingService.getIssuer() });
}

export function useSaveIssuer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Issuer) => adminBillingService.saveIssuer(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'billing', 'issuer'] });
      toast.success('Datos de quien cobra guardados');
    },
    onError: (error) => toast.error(errorDetail(error, 'No se pudieron guardar los datos.')),
  });
}

/** Guarda un archivo que ya se descargó (el PDF se pide con el token en memoria; un enlace simple no serviría). */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/**
 * Todo lo que se hace con una factura desde la cartera: generar la cuenta de cobro, descargarla, enviarla, marcarla
 * pagada o anularla. Cualquier cambio refresca la cartera, los próximos cobros, el tablero y la ficha del negocio.
 */
export function useInvoiceActions() {
  const queryClient = useQueryClient();
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['admin'] });
    queryClient.invalidateQueries({ queryKey: ['billing'] });
  };
  const onError = (error: unknown) => toast.error(errorDetail(error, 'No se pudo completar la acción.'));

  const generate = useMutation({
    mutationFn: (invoiceId: string) => adminBillingService.generateDocument(invoiceId),
    onSuccess: (res) => { refresh(); toast.success(res.issued ? `Cuenta de cobro ${res.document_number} generada` : `Ya tenía la cuenta ${res.document_number}`); },
    onError,
  });
  const download = useMutation({
    mutationFn: async (a: { invoiceId: string; filename: string }) => saveBlob(await adminBillingService.downloadDocument(a.invoiceId), a.filename),
    onError,
  });
  const send = useMutation({
    mutationFn: (a: { invoiceId: string; to?: string }) => adminBillingService.sendDocument(a.invoiceId, a.to),
    onSuccess: (res) => { refresh(); toast.success(`Cuenta de cobro ${res.document_number} enviada a ${res.sent_to}`); },
    onError,
  });
  const pay = useMutation({
    mutationFn: (a: { invoiceId: string; method: string; reference?: string }) =>
      adminBillingService.registerPayment(a.invoiceId, { payment_method: a.method, payment_reference: a.reference }),
    onSuccess: (res) => { refresh(); toast.success(res.reactivated ? 'Pago registrado: el asistente vuelve a atender' : 'Pago registrado'); },
    onError,
  });
  const voidInvoice = useMutation({
    mutationFn: (a: { invoiceId: string; reason?: string }) => adminBillingService.voidInvoice(a.invoiceId, a.reason),
    onSuccess: () => { refresh(); toast.success('Factura anulada'); },
    onError,
  });
  return { generate, download, send, pay, voidInvoice };
}

export function useCosts(days: number) {
  return useQuery({ queryKey: ['admin', 'billing', 'costs', days], queryFn: () => adminBillingService.getCosts(days), staleTime: 30_000 });
}

export function useSyncCosts() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (days: number) => adminBillingService.syncCosts(days),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'billing'] });
      if (res.ok) toast.success(`Sincronizado: ${res.runs} llamadas de ${res.workspaces} negocio(s)`);
      else toast.error(`LangSmith no respondió: ${res.error ?? 'error desconocido'}`);
    },
    onError: (error) => toast.error(errorDetail(error, 'No se pudo sincronizar.')),
  });
}

export function useLangsmithPing() {
  return useMutation({
    mutationFn: () => adminBillingService.pingLangsmith(),
    onSuccess: (res) => (res.ok ? toast.success(res.detail) : toast.error(res.detail)),
    onError: (error) => toast.error(errorDetail(error, 'No se pudo probar la conexión.')),
  });
}

export function useSaveClientProfile(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: BillingProfile) => adminBillingService.saveClientProfile(workspaceId, body),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['admin'] }); toast.success('Datos de cobro del negocio guardados'); },
    onError: (error) => toast.error(errorDetail(error, 'No se pudieron guardar los datos de cobro.')),
  });
}


// ── Planes ───────────────────────────────────────────────────────────────────

/** El análisis semana a semana. Al cambiar el periodo conserva lo anterior a la vista. */
export function useInsights(weeks: number) {
  return useQuery({
    queryKey: ['admin', 'billing', 'insights', weeks],
    queryFn: () => adminBillingService.getInsights(weeks),
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });
}

/** El tablero de planes. Al cambiar el periodo conserva lo anterior a la vista (opaco) en vez de vaciar la pantalla. */
export function usePlansDashboard(days: number) {
  return useQuery({
    queryKey: ['admin', 'billing', 'plans', days],
    queryFn: () => adminBillingService.getPlans(days),
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });
}

export function usePlanPreview(planId: string) {
  return useMutation({
    mutationFn: (changes: PlanChanges) => adminBillingService.previewPlan(planId, changes),
    onError: (error) => toast.error(errorDetail(error, 'No se pudo calcular el impacto.')),
  });
}

export function useUpdatePlan(planId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (changes: PlanChanges) => adminBillingService.updatePlan(planId, changes),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['admin'] });
      queryClient.invalidateQueries({ queryKey: ['billing'] });
      toast.success(`Plan «${res.plan.name}» actualizado`);
    },
    onError: (error) => toast.error(errorDetail(error, 'No se pudo actualizar el plan.')),
  });
}


/**
 * Los planes que se pueden vender, con su nombre actual. Los textos de las pantallas muestran el nombre (que se puede
 * cambiar), nunca el código; los nombres se leen de aquí para seguir cualquier cambio. Editar un plan refresca esto.
 */
export function usePlans() {
  return useQuery({ queryKey: ['billing', 'plans'], queryFn: listPlans, staleTime: 60_000 });
}
