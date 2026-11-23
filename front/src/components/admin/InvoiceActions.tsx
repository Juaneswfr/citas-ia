// Acciones sobre una factura: generar la cuenta de cobro, descargarla, enviarla, marcarla pagada o anularla.
// Las usan la pantalla de Cobros y la ficha de cada negocio, así el comportamiento es el mismo en los dos sitios.

import { useState } from 'react';
import { Button } from '@/components/hilo/primitives';
import { Modal } from '@/components/finanzas/ui';
import { useInvoiceActions } from '@/hooks/use-billing';
import { fmtCOP } from '@/lib/hilo-data';
import styles from './Cartera.module.css';

const PAYMENT_METHODS = ['Transferencia', 'Nequi', 'Daviplata', 'Efectivo', 'Otro'];

export interface ActionableInvoice {
  id: string;
  status: string;
  amount_cop: number;
  document_number: string | null;
  last_sent_to?: string | null;
  /** Correo de cobro del negocio, si lo dio. */
  billing_email?: string | null;
}

function PaymentDialog({ invoice, onClose }: { invoice: ActionableInvoice; onClose: () => void }) {
  const { pay } = useInvoiceActions();
  const [method, setMethod] = useState(PAYMENT_METHODS[0]);
  const [reference, setReference] = useState('');
  return (
    <Modal title="Registrar pago" onClose={onClose} maxWidth={460}>
      <div className={styles.form}>
        <p className={styles.form__summary}>
          Vas a marcar como pagada la factura de <strong>{fmtCOP(invoice.amount_cop)}</strong>
          {invoice.document_number ? ` (${invoice.document_number})` : ''}. Si el negocio estaba en mora o pausado, el asistente vuelve a atender.
        </p>
        <label className={styles.form__field}>Medio de pago
          <select className={styles.form__input} value={method} onChange={(e) => setMethod(e.target.value)}>
            {PAYMENT_METHODS.map((m) => <option key={m}>{m}</option>)}
          </select>
        </label>
        <label className={styles.form__field}>Referencia o comprobante (opcional)
          <input className={styles.form__input} value={reference} maxLength={120} onChange={(e) => setReference(e.target.value)} />
        </label>
        <div className={styles.form__actions}>
          <Button variant="secondary" size="sm" onClick={onClose}>Cancelar</Button>
          <Button size="sm" disabled={pay.isPending}
                  onClick={() => pay.mutate({ invoiceId: invoice.id, method, reference: reference.trim() || undefined }, { onSuccess: onClose })}>
            Registrar pago
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function SendDialog({ invoice, onClose }: { invoice: ActionableInvoice; onClose: () => void }) {
  const { send } = useInvoiceActions();
  const [to, setTo] = useState(invoice.last_sent_to || invoice.billing_email || '');
  const valid = /^\S+@\S+\.\S+$/.test(to.trim());
  return (
    <Modal title={invoice.last_sent_to ? 'Reenviar cuenta de cobro' : 'Enviar cuenta de cobro'} onClose={onClose} maxWidth={460}>
      <div className={styles.form}>
        <p className={styles.form__summary}>
          Se envía el PDF{invoice.document_number ? ` de ${invoice.document_number}` : ' (se genera ahora con el siguiente consecutivo)'} por{' '}
          <strong>{fmtCOP(invoice.amount_cop)}</strong>.
        </p>
        <label className={styles.form__field}>Correo de destino
          <input className={styles.form__input} type="email" value={to} autoFocus onChange={(e) => setTo(e.target.value)} />
        </label>
        {!invoice.billing_email && (
          <p className={styles.form__hint}>El negocio no ha dado un correo de cobro: escríbelo a mano o complétalo en su ficha.</p>
        )}
        <div className={styles.form__actions}>
          <Button variant="secondary" size="sm" onClick={onClose}>Cancelar</Button>
          <Button size="sm" disabled={!valid || send.isPending}
                  onClick={() => send.mutate({ invoiceId: invoice.id, to: to.trim() }, { onSuccess: onClose })}>
            {send.isPending ? 'Enviando…' : 'Enviar'}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export function InvoiceActions({ invoice }: { invoice: ActionableInvoice }) {
  const { generate, download, voidInvoice } = useInvoiceActions();
  const [dialog, setDialog] = useState<'pay' | 'send' | null>(null);
  const open = invoice.status === 'pending' || invoice.status === 'overdue';
  const hasDoc = !!invoice.document_number;

  return (
    <>
      <div className={styles.actions}>
        {open && !hasDoc && (
          <Button size="sm" variant="secondary" disabled={generate.isPending} onClick={() => generate.mutate(invoice.id)}>
            Generar cuenta de cobro
          </Button>
        )}
        {hasDoc && (
          <Button size="sm" variant="secondary" disabled={download.isPending}
                  onClick={() => download.mutate({ invoiceId: invoice.id, filename: `${invoice.document_number}.pdf` })}>
            Descargar PDF
          </Button>
        )}
        {open && (
          <Button size="sm" variant="secondary" onClick={() => setDialog('send')}>
            {invoice.last_sent_to ? 'Reenviar' : 'Enviar'}
          </Button>
        )}
        {open && <Button size="sm" onClick={() => setDialog('pay')}>Marcar pagada</Button>}
        {open && (
          <Button size="sm" variant="ghost" disabled={voidInvoice.isPending}
                  onClick={() => window.confirm('¿Anular esta factura? Deja de contar como saldo. El consecutivo de su cuenta de cobro no se reutiliza.')
                    && voidInvoice.mutate({ invoiceId: invoice.id })}>
            Anular
          </Button>
        )}
      </div>
      {dialog === 'pay' && <PaymentDialog invoice={invoice} onClose={() => setDialog(null)} />}
      {dialog === 'send' && <SendDialog invoice={invoice} onClose={() => setDialog(null)} />}
    </>
  );
}
