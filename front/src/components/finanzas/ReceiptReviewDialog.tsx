// Revisión de un comprobante recibido por WhatsApp: la imagen a un lado y, al otro, los datos
// leídos (editables) y la venta a la que se aplica. Aprobar registra el cobro; rechazar lo descarta.

import { useEffect, useState } from 'react';
import { Button } from '@/components/hilo/primitives';
import { useApproveReceipt, useReceipt, useReceiptFile, useRejectReceipt } from '@/hooks/use-receipts';
import { fmtCOP } from '@/lib/hilo-data';
import type { PaymentMethod } from '@/lib/types/accounting';
import type { ReceiptDetailOut } from '@/lib/types/receipts';
import { AsyncState, Field, formatCOPInput, MethodChips, Modal, parseCOP, todayISO } from './ui';
import styles from './Finanzas.module.css';

interface ReceiptReviewDialogProps {
  receiptId: string;
  onClose: () => void;
}

export function ReceiptReviewDialog({ receiptId, onClose }: ReceiptReviewDialogProps) {
  const { data, isLoading, isError, refetch } = useReceipt(receiptId);
  return (
    <Modal title="Revisar comprobante" onClose={onClose} maxWidth={820}>
      <AsyncState isLoading={isLoading} isError={isError} isEmpty={!data} onRetry={refetch}
                  emptyText="No se encontró el comprobante.">
        {data && <ReviewBody receipt={data} onClose={onClose} />}
      </AsyncState>
    </Modal>
  );
}

function ReceiptPreview({ receipt }: { receipt: ReceiptDetailOut }) {
  const { url, isLoading, isError } = useReceiptFile(receipt.id);
  if (isLoading) return <div className={styles.state}>Cargando archivo…</div>;
  if (isError || !url) return <div className={styles.state}>No se pudo abrir el archivo.</div>;
  if (receipt.content_type === 'application/pdf') {
    return (
      <div className={styles.state}>
        Es un PDF y no se leyó automáticamente.
        <div className={styles.state__action}>
          <a className={styles.review__link} href={url} target="_blank" rel="noreferrer">Abrir PDF</a>
        </div>
      </div>
    );
  }
  return (
    <a href={url} target="_blank" rel="noreferrer" title="Abrir en tamaño completo">
      <img className={styles.review__image} src={url} alt="Comprobante enviado por el cliente" />
    </a>
  );
}

function ReviewBody({ receipt, onClose }: { receipt: ReceiptDetailOut; onClose: () => void }) {
  const approve = useApproveReceipt();
  const reject = useRejectReceipt();
  const [orderId, setOrderId] = useState(receipt.suggested_order_id ?? '');
  const [amount, setAmount] = useState(receipt.amount_cop ? formatCOPInput(String(receipt.amount_cop)) : '');
  const [method, setMethod] = useState<PaymentMethod>(receipt.method ?? 'transfer');
  const [date, setDate] = useState(receipt.paid_on ?? todayISO());
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState('');

  const order = receipt.orders.find((o) => o.id === orderId);
  // Sin monto leído, se propone el saldo de la venta elegida.
  useEffect(() => {
    if (order && !receipt.amount_cop) setAmount(formatCOPInput(String(order.balance_cop)));
  }, [order, receipt.amount_cop]);

  const amountCop = parseCOP(amount);
  const overBalance = !!order && amountCop > order.balance_cop;
  const pending = receipt.status === 'pending';
  const busy = approve.isPending || reject.isPending;
  const sender = receipt.customer_name || receipt.customer_phone || 'Cliente sin identificar';

  const handleApprove = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!order || amountCop <= 0 || overBalance) return;
    try {
      await approve.mutateAsync({
        id: receipt.id,
        body: { sales_order_id: order.id, amount_cop: amountCop, method, occurred_on: date },
      });
      onClose();
    } catch {
      // onError de la mutación ya notificó.
    }
  };

  const handleReject = async () => {
    try {
      await reject.mutateAsync({ id: receipt.id, reason: reason.trim() });
      onClose();
    } catch {
      // onError de la mutación ya notificó.
    }
  };

  return (
    <div className={styles.review}>
      <div className={styles.review__file}><ReceiptPreview receipt={receipt} /></div>

      <form className={styles.form} onSubmit={handleApprove}>
        <div>
          <div className={styles.row__title}>{sender}</div>
          <div className={styles.row__meta}>
            Recibido el {new Date(receipt.created_at).toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' })}
            {receipt.bank ? ` · ${receipt.bank}` : ''}
            {receipt.reference ? ` · Ref. ${receipt.reference}` : ''}
            {receipt.payer_name ? ` · Paga: ${receipt.payer_name}` : ''}
          </div>
        </div>

        {!pending && (
          <div className={styles.state}>
            {receipt.status === 'approved' ? 'Este comprobante ya fue aprobado y su cobro está registrado.'
              : `Este comprobante fue rechazado${receipt.reject_reason ? `: ${receipt.reject_reason}` : '.'}`}
          </div>
        )}

        {pending && receipt.orders.length === 0 && (
          <div className={styles.state}>
            No hay ventas con saldo pendiente. Marca la cita del cliente como completada y vuelve a este comprobante.
          </div>
        )}

        {pending && receipt.orders.length > 0 && !rejecting && (
          <>
            <Field label="Venta a la que se aplica"
                   hint={order ? `Saldo pendiente: ${fmtCOP(order.balance_cop)}` : 'Elige la venta que está pagando el cliente'}>
              <select className={styles.field__input} value={orderId} onChange={(e) => setOrderId(e.target.value)}>
                <option value="">Selecciona una venta…</option>
                {receipt.orders.map((o) => (
                  <option key={o.id} value={o.id}>
                    #{o.number} · {o.third_party_name ?? 'Sin cliente'} · {o.description ?? 'Venta'} · saldo {fmtCOP(o.balance_cop)}
                    {o.is_customer ? '' : ' (otro cliente)'}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Monto del pago"
                   hint={overBalance ? `No puede superar el saldo (${fmtCOP(order.balance_cop)})`
                     : receipt.amount_cop ? 'Leído del comprobante: verifícalo contra la imagen'
                       : 'No se pudo leer el monto: escríbelo según la imagen'}>
              <input className={styles.field__input} inputMode="numeric" value={amount}
                     onChange={(e) => setAmount(formatCOPInput(e.target.value))} />
            </Field>
            <div className={styles.field}>
              <span className={styles.field__label}>Método</span>
              <MethodChips value={method} onChange={setMethod} />
            </div>
            <Field label="Fecha del pago">
              <input className={styles.field__input} type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </Field>
          </>
        )}

        {pending && rejecting && (
          <Field label="Motivo del rechazo (opcional)" hint="Solo lo ve tu equipo; no se le envía al cliente.">
            <input className={styles.field__input} value={reason} maxLength={300}
                   onChange={(e) => setReason(e.target.value)} placeholder="Ej.: no es un pago a este negocio" />
          </Field>
        )}

        <div className={styles.modal__actions}>
          {!pending && <Button type="button" variant="ghost" onClick={onClose}>Cerrar</Button>}
          {pending && !rejecting && (
            <>
              <Button type="button" variant="ghost" disabled={busy} onClick={() => setRejecting(true)}>Rechazar</Button>
              <Button type="submit" disabled={busy || !order || amountCop <= 0 || overBalance}>
                {approve.isPending ? 'Registrando…' : `Aprobar y cobrar ${amountCop > 0 && !overBalance ? fmtCOP(amountCop) : ''}`.trim()}
              </Button>
            </>
          )}
          {pending && rejecting && (
            <>
              <Button type="button" variant="ghost" disabled={busy} onClick={() => setRejecting(false)}>Volver</Button>
              <Button type="button" disabled={busy} onClick={handleReject}>
                {reject.isPending ? 'Rechazando…' : 'Confirmar rechazo'}
              </Button>
            </>
          )}
        </div>
      </form>
    </div>
  );
}
