// Órdenes de venta: lista, cobro, anulación y venta manual (con quien atendió y propina).

import { useState } from 'react';
import { Button } from '@/components/hilo/primitives';
import { fmtCOP } from '@/lib/hilo-data';
import {
  useCompensation, useCreateSalesOrder, usePayWithReceipt, useSalesOrders, useThirdParties, useVoidSalesOrder,
} from '@/hooks/use-accounting';
import { useBusinessTerms } from '@/hooks/use-workspace';
import type { SalesOrderOut } from '@/lib/types/accounting';
import { PaymentDialog } from './PaymentDialog';
import { PaymentsList } from './PaymentsList';
import { AsyncState, Field, Modal, StatusTag, parseCOP } from './ui';
import styles from './Finanzas.module.css';

function NewSaleDialog({ onClose }: { onClose: () => void }) {
  const create = useCreateSalesOrder();
  const terms = useBusinessTerms();
  const { data: members = [] } = useCompensation();
  const { data: parties = [] } = useThirdParties();
  const [description, setDescription] = useState('');
  const [price, setPrice] = useState('');
  const [tip, setTip] = useState('');
  const [memberId, setMemberId] = useState('');
  const [thirdPartyId, setThirdPartyId] = useState('');
  const invalid = !description.trim() || parseCOP(price) <= 0;

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      await create.mutateAsync({
        third_party_id: thirdPartyId || null,
        lines: [{ description: description.trim(), qty: 1, unit_price_cop: parseCOP(price),
                  member_id: memberId || null, tip_cop: parseCOP(tip) }],
      });
      onClose();
    } catch {
      // onError de la mutación ya notificó.
    }
  };

  return (
    <Modal title="Nueva venta" onClose={onClose}>
      <form className={styles.form} onSubmit={handleSubmit}>
        <Field label="Servicio o producto">
          <input className={styles.field__input} value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>
        <div className={styles.form__grid}>
          <Field label="Precio"><input className={styles.field__input} inputMode="numeric" value={price} onChange={(e) => setPrice(e.target.value)} /></Field>
          <Field label="Propina" hint={`Va al ${terms.staff}, no es ingreso del negocio`}>
            <input className={styles.field__input} inputMode="numeric" value={tip} onChange={(e) => setTip(e.target.value)} />
          </Field>
        </div>
        <Field label={terms.Staff}>
          <select className={styles.field__input} value={memberId} onChange={(e) => setMemberId(e.target.value)}>
            <option value="">Sin asignar</option>
            {members.map((m) => <option key={m.member_id} value={m.member_id}>{m.member_name ?? 'Sin nombre'}</option>)}
          </select>
        </Field>
        <Field label="Cliente">
          <select className={styles.field__input} value={thirdPartyId} onChange={(e) => setThirdPartyId(e.target.value)}>
            <option value="">Mostrador / sin cliente</option>
            {parties.filter((p) => p.kind === 'customer').map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </Field>
        <div className={styles.modal__actions}>
          <Button type="button" variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button type="submit" disabled={invalid || create.isPending}>Guardar venta</Button>
        </div>
      </form>
    </Modal>
  );
}

function orderMeta(order: SalesOrderOut): string {
  const staffNames = [...new Set(order.lines.map((l) => l.member_name).filter(Boolean))].join(', ');
  const commission = order.lines.reduce((sum, l) => sum + l.commission_cop, 0);
  const parts = [new Date(order.issued_at).toLocaleDateString('es-CO'), order.third_party_name ?? 'Sin cliente'];
  if (staffNames) parts.push(staffNames);
  if (commission > 0) parts.push(`comisión ${fmtCOP(commission)}`);
  return parts.join(' · ');
}

export function SalesTab() {
  const [filter, setFilter] = useState('');
  const [creating, setCreating] = useState(false);
  const [paying, setPaying] = useState<SalesOrderOut | null>(null);
  const { data = [], isLoading, isError, refetch } = useSalesOrders(filter || undefined);
  const pay = usePayWithReceipt('sales');
  const voidOrder = useVoidSalesOrder();

  const handleVoid = (order: SalesOrderOut) => {
    if (window.confirm(`¿Anular la venta #${order.number}? También se anularán sus cobros.`)) {
      voidOrder.mutate(order.id);
    }
  };

  return (
    <>
      <div className={styles.toolbar}>
        <h2 className={styles.toolbar__title}>Ventas</h2>
        <div className={styles.toolbar__actions}>
          <select className={styles.field__input} aria-label="Filtrar por estado" value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="">Todas</option>
            <option value="open">Por cobrar</option>
            <option value="paid">Cobradas</option>
            <option value="void">Anuladas</option>
          </select>
          <Button icon="plus" onClick={() => setCreating(true)}>Nueva venta</Button>
        </div>
      </div>
      <AsyncState isLoading={isLoading} isError={isError} isEmpty={data.length === 0} onRetry={refetch}
                  emptyText="Aún no hay ventas. Se crean solas cuando completas una cita.">
        <div className={styles.list}>
          {data.map((order) => (
            <div key={order.id} className={`${styles.row} ${order.status === 'void' ? styles['row--void'] : ''}`}>
              <div className={styles.row__main}>
                <div className={styles.row__title}>#{order.number} · {order.lines.map((l) => l.description).join(', ')}</div>
                <div className={styles.row__meta}>{orderMeta(order)}</div>
              </div>
              <StatusTag status={order.status} />
              <div className={styles.row__amount}>
                {fmtCOP(order.total_cop)}
                {order.status === 'open' && order.paid_cop > 0 && <div className={styles.row__meta}>Falta {fmtCOP(order.balance_cop)}</div>}
              </div>
              <div className={styles.row__actions}>
                {order.status === 'open' && <Button size="sm" onClick={() => setPaying(order)}>Cobrar</Button>}
                {order.status !== 'void' && <Button size="sm" variant="ghost" onClick={() => handleVoid(order)}>Anular</Button>}
              </div>
              <PaymentsList payments={order.payments} noun="Cobro" />
            </div>
          ))}
        </div>
      </AsyncState>
      {creating && <NewSaleDialog onClose={() => setCreating(false)} />}
      {paying && (
        <PaymentDialog title={`Cobrar venta #${paying.number}`} balanceCop={paying.balance_cop}
                       submitting={pay.isPending} onClose={() => setPaying(null)}
                       onSubmit={(body, receipt) => pay.submit(paying.id, body, receipt)} />
      )}
    </>
  );
}
