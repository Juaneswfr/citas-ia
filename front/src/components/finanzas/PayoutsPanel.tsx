// Liquidaciones de barberos: vista previa del periodo, creación en borrador, pago y cancelación.

import { useState } from 'react';
import { Button } from '@/components/hilo/primitives';
import { fmtCOP } from '@/lib/hilo-data';
import {
  useCancelPayout, useCompensation, useCreatePayout, usePayPayout, usePayoutPreview, usePayouts,
} from '@/hooks/use-accounting';
import type { PaymentMethod, PayoutOut } from '@/lib/types/accounting';
import { AsyncState, Field, MethodSelect, Modal, StatusTag, todayISO } from './ui';
import styles from './Finanzas.module.css';

function PayPayoutDialog({ payout, onClose }: { payout: PayoutOut; onClose: () => void }) {
  const pay = usePayPayout();
  const [method, setMethod] = useState<PaymentMethod>('cash');

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      await pay.mutateAsync({ id: payout.id as string, method });
      onClose();
    } catch {
      // onError de la mutación ya notificó.
    }
  };

  return (
    <Modal title={`Pagar a ${payout.member_name ?? 'barbero'}`} onClose={onClose}>
      <form className={styles.form} onSubmit={handleSubmit}>
        <div className={`${styles['summary-line']} ${styles['summary-line--total']}`}>
          <span>Entregar</span><span>{fmtCOP(payout.net_cop)}</span>
        </div>
        <Field label="Método de pago"><MethodSelect value={method} onChange={setMethod} /></Field>
        <div className={styles.modal__actions}>
          <Button type="button" variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button type="submit" disabled={pay.isPending}>Confirmar pago</Button>
        </div>
      </form>
    </Modal>
  );
}

function PayoutBreakdown({ payout }: { payout: PayoutOut }) {
  return (
    <div>
      <div className={styles['summary-line']}><span>Comisión ({payout.lines_count} ventas)</span><span>{fmtCOP(payout.commission_cop)}</span></div>
      {payout.base_cop > 0 && <div className={styles['summary-line']}><span>Sueldo base</span><span>{fmtCOP(payout.base_cop)}</span></div>}
      {payout.tips_cop > 0 && <div className={styles['summary-line']}><span>Propinas</span><span>{fmtCOP(payout.tips_cop)}</span></div>}
      {payout.rent_deduction_cop > 0 && <div className={styles['summary-line']}><span>Alquiler de silla</span><span>−{fmtCOP(payout.rent_deduction_cop)}</span></div>}
      <div className={`${styles['summary-line']} ${styles['summary-line--total']}`}><span>Neto a pagar</span><span>{fmtCOP(payout.net_cop)}</span></div>
    </div>
  );
}

function monthStartISO(): string {
  return `${todayISO().slice(0, 7)}-01`;
}

export function PayoutsPanel() {
  const { data: members = [] } = useCompensation();
  const payouts = usePayouts();
  const create = useCreatePayout();
  const cancel = useCancelPayout();
  const [memberId, setMemberId] = useState('');
  const [start, setStart] = useState(monthStartISO());
  const [end, setEnd] = useState(todayISO());
  const [paying, setPaying] = useState<PayoutOut | null>(null);
  const preview = usePayoutPreview(memberId, start, end);
  const nothingToPay = !!preview.data && preview.data.net_cop === 0 && preview.data.lines_count === 0;

  const handleCreate = () => create.mutate({ memberId, start, end });
  const handleCancel = (payout: PayoutOut) => {
    if (window.confirm('¿Cancelar esta liquidación? Sus ventas quedarán libres para liquidarse otra vez.')) {
      cancel.mutate(payout.id as string);
    }
  };

  return (
    <section className={styles.panel}>
      <h3 className={styles.panel__title}>Liquidar a un barbero</h3>
      <div className={styles.form}>
        <div className={styles.form__grid}>
          <Field label="Barbero">
            <select className={styles.field__input} value={memberId} onChange={(e) => setMemberId(e.target.value)}>
              <option value="">Elige un barbero</option>
              {members.map((m) => <option key={m.member_id} value={m.member_id}>{m.member_name ?? 'Sin nombre'}</option>)}
            </select>
          </Field>
          <div className={styles.form__grid}>
            <Field label="Desde"><input className={styles.field__input} type="date" value={start} onChange={(e) => setStart(e.target.value)} /></Field>
            <Field label="Hasta"><input className={styles.field__input} type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></Field>
          </div>
        </div>
        {preview.isError && <div className={styles.state}>No se pudo calcular el periodo.</div>}
        {preview.data && <PayoutBreakdown payout={preview.data} />}
        <div className={styles.modal__actions}>
          <Button onClick={handleCreate} disabled={!memberId || !preview.data || nothingToPay || create.isPending}>
            Crear liquidación
          </Button>
        </div>
      </div>

      <h3 className={styles.panel__title}>Historial</h3>
      <AsyncState isLoading={payouts.isLoading} isError={payouts.isError} isEmpty={(payouts.data ?? []).length === 0}
                  emptyText="Aún no hay liquidaciones." onRetry={payouts.refetch}>
        <div className={styles.list}>
          {(payouts.data ?? []).map((p) => (
            <div key={p.id} className={`${styles.row} ${p.status === 'cancelled' ? styles['row--void'] : ''}`}>
              <div className={styles.row__main}>
                <div className={styles.row__title}>{p.member_name ?? 'Barbero'}</div>
                <div className={styles.row__meta}>{p.period_start} → {p.period_end} · {p.lines_count} ventas</div>
              </div>
              <StatusTag status={p.status} />
              <div className={styles.row__amount}>{fmtCOP(p.net_cop)}</div>
              <div className={styles.row__actions}>
                {p.status === 'draft' && <Button size="sm" onClick={() => setPaying(p)}>Pagar</Button>}
                {p.status === 'draft' && <Button size="sm" variant="ghost" onClick={() => handleCancel(p)}>Cancelar</Button>}
              </div>
            </div>
          ))}
        </div>
      </AsyncState>
      {paying && <PayPayoutDialog payout={paying} onClose={() => setPaying(null)} />}
    </section>
  );
}
