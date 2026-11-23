// «Pedir más citas»: el dueño elige un bloque, las citas se acreditan de inmediato y queda un saldo pendiente de pago.

import { useState } from 'react';
import { format, parseISO } from 'date-fns';
import { Button } from '@/components/hilo/primitives';
import { Modal } from '@/components/finanzas/ui';
import { useAuth } from '@/lib/auth-context';
import { useRequestAppointments } from '@/hooks/use-billing';
import { fmtCOP } from '@/lib/hilo-data';
import styles from './RequestAppointments.module.css';

// Los mismos bloques y precio de la oferta (documento de planes §5); el servidor valida el bloque y fija el cobro.
const BLOCKS = [50, 100, 200, 300];
const PRICE_PER_APPOINTMENT = 500;

export function RequestAppointmentsDialog({ onClose, cycleEnd }: { onClose: () => void; cycleEnd?: string | null }) {
  const { me } = useAuth();
  const request = useRequestAppointments(me?.workspace_id ?? '');
  const [quantity, setQuantity] = useState(BLOCKS[0]);
  const price = quantity * PRICE_PER_APPOINTMENT;
  const until = cycleEnd ? format(parseISO(cycleEnd), 'd/MM') : 'el cierre del ciclo';

  return (
    <Modal title="Pedir más citas" onClose={onClose} maxWidth={460}>
      <div className={styles.body}>
        <p className={styles.lead}>
          Las citas se suman <strong>hoy mismo</strong> y valen hasta {until}. Queda un saldo pendiente
          que debes pagar; las que no uses no se acumulan.
        </p>
        <div className={styles.options} role="radiogroup" aria-label="Cantidad de citas">
          {BLOCKS.map((b) => (
            <button
              key={b} type="button" role="radio" aria-checked={quantity === b}
              className={`${styles.option} ${quantity === b ? styles['option--on'] : ''}`}
              onClick={() => setQuantity(b)}
            >
              <span className={styles.option__n}>{b}</span>
              <span className={styles.option__label}>citas</span>
              <span className={styles.option__price}>{fmtCOP(b * PRICE_PER_APPOINTMENT)}</span>
            </button>
          ))}
        </div>
        <p className={styles.total}>
          Saldo pendiente: <strong>{fmtCOP(price)}</strong> <span>({fmtCOP(PRICE_PER_APPOINTMENT)} por cita)</span>
        </p>
        <p className={styles.note}>Solo puedes tener una solicitud sin pagar a la vez. Te indicamos cómo pagar en la cuenta de cobro.</p>
        <div className={styles.actions}>
          <Button size="sm" variant="ghost" onClick={onClose} disabled={request.isPending}>Cancelar</Button>
          <Button size="sm" disabled={request.isPending} onClick={() => request.mutate(quantity, { onSuccess: onClose })}>
            {request.isPending ? 'Pidiendo…' : `Pedir ${quantity} citas`}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
