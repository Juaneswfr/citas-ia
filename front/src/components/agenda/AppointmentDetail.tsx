// Panel de detalle de una cita: información del servicio, completarla y cobrarla con comprobante, o cancelarla.

import { useState } from 'react';
import { format, parseISO } from 'date-fns';
import { es } from 'date-fns/locale';
import { Button } from '@/components/hilo/primitives';
import { fmtCOP } from '@/lib/hilo-data';
import { usePayWithReceipt, useVoidMovement } from '@/hooks/use-accounting';
import { useAppointmentDetail } from '@/hooks/use-appointment-detail';
import { useBusinessTerms } from '@/hooks/use-workspace';
import { PaymentDialog } from '@/components/finanzas/PaymentDialog';
import { PaymentsList } from '@/components/finanzas/PaymentsList';
import { AsyncState, Modal, PaymentProgress, PaymentStatusTag } from '@/components/finanzas/ui';
import type { PaymentOut, SalesOrderOut } from '@/lib/types/accounting';
import styles from './AppointmentDetail.module.css';

const STATUS_LABEL: Record<string, string> = {
  pending: 'Pendiente', confirmed: 'Confirmada', completed: 'Completada',
  cancelled: 'Cancelada', noshow: 'No asistió', rescheduled: 'Reagendada',
};

function Item({ label, value, wide = false }: { label: string; value: string; wide?: boolean }) {
  return (
    <div className={`${styles.detail__item} ${wide ? styles['detail__item--wide'] : ''}`}>
      <span className={styles.detail__label}>{label}</span>
      <span className={styles.detail__value}>{value}</span>
    </div>
  );
}

function SaleSummary({ sale, onVoid }: { sale: SalesOrderOut; onVoid?: (payment: PaymentOut) => void }) {
  return (
    <>
      <div className={styles.detail__totals}>
        <div className={styles.detail__total}>
          <span className={styles.detail__label}>Total</span>
          <span className={styles['detail__total-value']}>{fmtCOP(sale.total_cop)}</span>
        </div>
        <div className={styles.detail__total}>
          <span className={styles.detail__label}>Cobrado</span>
          <span className={styles['detail__total-value']}>{fmtCOP(sale.paid_cop)}</span>
        </div>
        <div className={styles.detail__total}>
          <span className={styles.detail__label}>Pendiente</span>
          <span className={`${styles['detail__total-value']} ${sale.balance_cop > 0 ? styles['detail__total-value--pending'] : ''}`}>
            {fmtCOP(sale.balance_cop)}
          </span>
        </div>
        <PaymentStatusTag order={sale} />
      </div>
      <PaymentProgress paid={sale.paid_cop} total={sale.total_cop} />
      <PaymentsList payments={sale.payments} noun="Cobro" onVoid={onVoid} />
    </>
  );
}

interface AppointmentDetailProps {
  appointmentId: string;
  onClose: () => void;
}

export function AppointmentDetail({ appointmentId, onClose }: AppointmentDetailProps) {
  const { appointment, service, customer, sale, canManage, isCompleted, complete, isCompleting,
          canCancel, cancel, isCancelling } = useAppointmentDetail(appointmentId);
  const pay = usePayWithReceipt('sales');
  const voidMovement = useVoidMovement();
  const [paying, setPaying] = useState<SalesOrderOut | null>(null);

  const handleVoidPayment = (payment: PaymentOut) => {
    if (window.confirm(`¿Anular este cobro de ${fmtCOP(payment.amount_cop)}? El saldo volverá a quedar pendiente.`)) {
      voidMovement.mutate(payment.id);
    }
  };
  const apt = appointment.data;
  const order = sale.data ?? null;

  const handleComplete = async (thenCollect: boolean) => {
    try {
      const created = await complete();
      if (thenCollect && created && created.status === 'open') setPaying(created);
    } catch {
      // El onError de la mutación ya mostró el toast.
    }
  };

  const handleCancel = async () => {
    const who = customer?.name ?? customer?.phone ?? 'el cliente';
    if (!window.confirm(`¿Cancelar la cita de ${who}? Se le avisará por WhatsApp y el horario quedará libre.`)) return;
    try {
      await cancel();
      onClose();
    } catch {
      // El onError de la mutación ya mostró el toast.
    }
  };

  const terms = useBusinessTerms();
  const staffName = order?.lines.map((l) => l.member_name).find(Boolean) ?? 'Sin asignar';
  const price = apt ? apt.price_cop + apt.home_service_price_cop : 0;

  return (
    <Modal title="Detalle de la cita" onClose={onClose}>
      <AsyncState isLoading={appointment.isLoading} isError={appointment.isError || !apt} isEmpty={false}
                  emptyText="" onRetry={appointment.refetch}>
        {apt && (
          <>
            <div className={styles.detail__header}>
              <div>
                <h3 className={styles.detail__client}>{customer?.name ?? customer?.phone ?? 'Cliente'}</h3>
                {customer?.name && customer.phone && <div className={styles.detail__phone}>{customer.phone}</div>}
              </div>
              <span className={styles.detail__label}>{STATUS_LABEL[apt.status] ?? apt.status}</span>
            </div>

            <div className={styles.detail__grid}>
              <Item label="Servicio" value={service?.name ?? '—'} />
              <Item label="Precio" value={fmtCOP(price)} />
              <Item label="Fecha" value={format(parseISO(apt.start_at), "EEEE d 'de' MMMM", { locale: es })} />
              <Item label="Hora" value={`${format(parseISO(apt.start_at), 'h:mm a')} – ${format(parseISO(apt.end_at), 'h:mm a')}`} />
              {service && <Item label="Duración" value={`${service.duration_minutes} min`} />}
              {canManage && isCompleted && <Item label={terms.Staff} value={staffName} />}
              {apt.is_home_service && <Item wide label="Domicilio" value={apt.home_address ?? 'Sin dirección'} />}
              {service?.description && <Item wide label="Descripción del servicio" value={service.description} />}
            </div>

            <div className={styles.detail__section}>
              <h4 className={styles['detail__section-title']}>Pago</h4>
              {!canManage && <p className={styles.detail__note}>Solo el dueño o un administrador puede completar y cobrar citas.</p>}
              {canManage && !isCompleted && (
                <>
                  <p className={styles.detail__note}>Al completarla se genera la venta y puedes cobrarla con su comprobante.</p>
                  <div className={styles.detail__actions}>
                    <Button variant="secondary" disabled={isCompleting} onClick={() => handleComplete(false)}>Marcar completada</Button>
                    <Button disabled={isCompleting} onClick={() => handleComplete(true)}>
                      {isCompleting ? 'Guardando…' : 'Completar y cobrar'}
                    </Button>
                  </div>
                </>
              )}
              {canManage && isCompleted && sale.isLoading && <p className={styles.detail__note}>Cargando cobro…</p>}
              {canManage && isCompleted && sale.isError && <p className={styles.detail__note}>No se pudo cargar el cobro. Intenta de nuevo.</p>}
              {canManage && isCompleted && !sale.isLoading && !sale.isError && !order && (
                <>
                  <p className={styles.detail__note}>La cita está completada, pero su venta aún no se generó.</p>
                  <div className={styles.detail__actions}>
                    <Button disabled={isCompleting} onClick={() => handleComplete(false)}>Generar venta</Button>
                  </div>
                </>
              )}
              {canManage && order && (
                <>
                  <SaleSummary sale={order} onVoid={handleVoidPayment} />
                  {order.status === 'open' && (
                    <div className={styles.detail__actions}>
                      <Button onClick={() => setPaying(order)}>
                        {order.paid_cop > 0 ? `Cobrar saldo (${fmtCOP(order.balance_cop)})` : 'Cobrar'}
                      </Button>
                    </div>
                  )}
                  {order.status === 'paid' && (
                    <p className={styles.detail__note}>Venta pagada por completo. Puedes ver o adjuntar comprobantes en cada cobro.</p>
                  )}
                </>
              )}
            </div>
          </>
        )}
      </AsyncState>
      <div className={styles.detail__actions}>
        {canCancel && (
          <Button variant="danger" disabled={isCancelling || isCompleting} onClick={handleCancel}>
            {isCancelling ? 'Cancelando…' : 'Cancelar cita'}
          </Button>
        )}
        <Button variant="ghost" onClick={onClose}>Cerrar</Button>
      </div>
      {paying && (
        <PaymentDialog title={`Cobrar venta #${paying.number}`} balanceCop={paying.balance_cop}
                       submitting={pay.isPending} onClose={() => setPaying(null)}
                       onSubmit={(body, receipt) => pay.submit(paying.id, body, receipt)} />
      )}
    </Modal>
  );
}
