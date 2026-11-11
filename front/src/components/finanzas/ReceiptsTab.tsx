// Comprobantes de pago que los clientes envían por WhatsApp. Nada se cobra solo:
// cada uno espera aquí a que el negocio lo apruebe (registra el cobro) o lo rechace.

import { useState } from 'react';
import { Button } from '@/components/hilo/primitives';
import { useReceipts } from '@/hooks/use-receipts';
import { fmtCOP } from '@/lib/hilo-data';
import type { ReceiptOut, ReceiptStatus } from '@/lib/types/receipts';
import { AsyncState, METHOD_LABEL } from './ui';
import { ReceiptReviewDialog } from './ReceiptReviewDialog';
import styles from './Finanzas.module.css';

const FILTERS: { id: ReceiptStatus; label: string; empty: string }[] = [
  { id: 'pending', label: 'Por revisar', empty: 'No hay comprobantes por revisar. Cuando un cliente envíe uno por WhatsApp aparecerá aquí.' },
  { id: 'approved', label: 'Aprobados', empty: 'Aún no has aprobado comprobantes.' },
  { id: 'rejected', label: 'Rechazados', empty: 'No hay comprobantes rechazados.' },
];
const STATUS_TAG: Record<ReceiptStatus, { label: string; className: string }> = {
  pending: { label: 'Por revisar', className: styles['tag--open'] },
  approved: { label: 'Aprobado', className: styles['tag--paid'] },
  rejected: { label: 'Rechazado', className: styles['tag--void'] },
};

function describe(receipt: ReceiptOut): string {
  const parts = [
    new Date(receipt.created_at).toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' }),
    receipt.method ? METHOD_LABEL[receipt.method] : null,
    receipt.bank,
    receipt.reference ? `Ref. ${receipt.reference}` : null,
  ];
  return parts.filter(Boolean).join(' · ');
}

export function ReceiptsTab() {
  const [status, setStatus] = useState<ReceiptStatus>('pending');
  const [openId, setOpenId] = useState<string | null>(null);
  const { data = [], isLoading, isError, refetch } = useReceipts(status);
  const filter = FILTERS.find((f) => f.id === status) ?? FILTERS[0];

  return (
    <>
      <div className={styles.toolbar}>
        <h2 className={styles.toolbar__title}>Comprobantes recibidos por WhatsApp</h2>
        <div className={styles.chips} role="radiogroup" aria-label="Estado del comprobante">
          {FILTERS.map((f) => (
            <button key={f.id} type="button" role="radio" aria-checked={status === f.id}
                    className={`${styles.chip} ${status === f.id ? styles['chip--active'] : ''}`}
                    onClick={() => setStatus(f.id)}>
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <AsyncState isLoading={isLoading} isError={isError} isEmpty={data.length === 0} onRetry={refetch}
                  emptyText={filter.empty}>
        <div className={styles.list}>
          {data.map((receipt) => (
            <div key={receipt.id} className={styles.row}>
              <div className={styles.row__main}>
                <div className={styles.row__title}>
                  {receipt.customer_name || receipt.customer_phone || 'Cliente sin identificar'}
                </div>
                <div className={styles.row__meta}>{describe(receipt)}</div>
              </div>
              <span className={`${styles.tag} ${STATUS_TAG[receipt.status].className}`}>
                {STATUS_TAG[receipt.status].label}
              </span>
              <div className={styles.row__amount}>
                {receipt.amount_cop ? fmtCOP(receipt.amount_cop) : 'Sin monto'}
              </div>
              <div className={styles.row__actions}>
                <Button size="sm" variant={receipt.status === 'pending' ? 'primary' : 'secondary'}
                        onClick={() => setOpenId(receipt.id)}>
                  {receipt.status === 'pending' ? 'Revisar' : 'Ver'}
                </Button>
              </div>
            </div>
          ))}
        </div>
      </AsyncState>

      {openId && <ReceiptReviewDialog receiptId={openId} onClose={() => setOpenId(null)} />}
    </>
  );
}
