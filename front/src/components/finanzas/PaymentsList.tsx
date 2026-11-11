// Cobros/pagos ya registrados de una orden, cada uno con acceso a sus comprobantes.

import { useState } from 'react';
import { format, parseISO } from 'date-fns';
import { es } from 'date-fns/locale';
import { Button } from '@/components/hilo/primitives';
import { fmtCOP } from '@/lib/hilo-data';
import type { PaymentOut } from '@/lib/types/accounting';
import { AttachmentsDialog } from './AttachmentsDialog';
import { METHOD_LABEL } from './ui';
import styles from './Finanzas.module.css';

interface PaymentsListProps {
  payments: PaymentOut[];
  /** "Cobro" para ventas, "Pago" para compras. */
  noun: string;
  /** Si se pasa, cada pago muestra "Anular" (la confirmación la hace quien llama). */
  onVoid?: (payment: PaymentOut) => void;
}

function formatDate(iso: string): string {
  try {
    return format(parseISO(iso), "d 'de' MMM yyyy", { locale: es });
  } catch {
    return iso;
  }
}

export function PaymentsList({ payments, noun, onVoid }: PaymentsListProps) {
  const [selected, setSelected] = useState<PaymentOut | null>(null);
  if (payments.length === 0) return null;

  return (
    <div className={styles.payments}>
      {payments.map((payment) => (
        <div key={payment.id} className={styles.payments__item}>
          <div className={styles.payments__main}>
            <span className={styles.payments__amount}>{fmtCOP(payment.amount_cop)}</span>
            <span className={styles.payments__meta}>
              {noun} · {METHOD_LABEL[payment.method]} · {formatDate(payment.occurred_on)}
            </span>
          </div>
          <div className={styles.payments__actions}>
            <Button size="sm" variant="ghost" icon="link" onClick={() => setSelected(payment)}>
              {payment.attachments_count > 0 ? `Comprobantes (${payment.attachments_count})` : 'Adjuntar comprobante'}
            </Button>
            {onVoid && <Button size="sm" variant="ghost" onClick={() => onVoid(payment)}>Anular</Button>}
          </div>
        </div>
      ))}
      {selected && (
        <AttachmentsDialog movementId={selected.id}
                           title={`Comprobantes · ${noun.toLowerCase()} de ${fmtCOP(selected.amount_cop)}`}
                           onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
