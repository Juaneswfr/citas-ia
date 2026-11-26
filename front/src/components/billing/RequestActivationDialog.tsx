// «Confirmar pago»: instrucciones para pagar a Zumit y un botón que abre WhatsApp con el mensaje ya escrito
// (negocio, cliente, número y valor). Si el negocio aún no tiene plan (prueba o pausa) también avisa a Zumit
// (`request-activation`) para que aparezca en Zumit Manager › Cobros. No activa nada: Zumit lo hace al ver el pago.

import { useState } from 'react';
import { Button } from '@/components/hilo/primitives';
import { Modal } from '@/components/finanzas/ui';
import { useAuth } from '@/lib/auth-context';
import { usePaymentInfo, usePlans, useRequestActivation } from '@/hooks/use-billing';
import { useWorkspace } from '@/hooks/use-workspace';
import { fmtCOP } from '@/lib/hilo-data';
import styles from './RequestAppointments.module.css';
import bill from './Billing.module.css';

type PlanCode = 'emprendedor' | 'equipo';

/** wa.me pide solo dígitos con el indicativo; un celular colombiano de 10 dígitos recibe el 57. */
export function whatsappLink(phone: string, text: string): string {
  let digits = phone.replace(/\D/g, '');
  if (digits.length === 10 && digits.startsWith('3')) digits = `57${digits}`;
  return `https://wa.me/${digits}?text=${encodeURIComponent(text)}`;
}

interface Props {
  onClose: () => void;
  /** Sin plan pagado (prueba o pausa): elige plan y avisa a Zumit. Si no, solo confirma lo pendiente. */
  needsPlan: boolean;
  /** Lo que se debe hoy (facturas pendientes o vencidas); 0 si no hay. */
  pendingCop?: number;
}

export function RequestActivationDialog({ onClose, needsPlan, pendingCop = 0 }: Props) {
  const { me } = useAuth();
  const workspaceId = me?.workspace_id ?? '';
  const { data: workspace } = useWorkspace();
  const { data: info } = usePaymentInfo(workspaceId);
  const { data: plans } = usePlans();
  const request = useRequestActivation(workspaceId);
  const [plan, setPlan] = useState<PlanCode>('emprendedor');
  const [phone, setPhone] = useState(workspace?.primary_phone ?? '');
  const options = (plans ?? []).filter((p): p is typeof p & { code: PlanCode } => p.code === 'emprendedor' || p.code === 'equipo');
  const chosen = options.find((p) => p.code === plan);
  const amount = needsPlan ? (chosen ? (chosen.launch_price_cop ?? chosen.price_cop) : 0) : pendingCop;
  const business = workspace?.name ?? 'mi negocio';
  const customer = me?.name || me?.email || '';
  const valid = phone.replace(/\D/g, '').length >= 7;
  const reference = `${business} · ${phone.trim() || 'tu número'}`;

  const message = [
    'Hola, realicé un pago de Zumit.',
    `Negocio: ${business}`,
    `Cliente: ${customer}`,
    `Mi número: ${phone.trim()}`,
    needsPlan && chosen ? `Plan: ${chosen.name}` : null,
    amount ? `Valor: ${fmtCOP(amount)}` : null,
    'Adjunto el comprobante.',
  ].filter(Boolean).join('\n');

  const confirm = () => {
    // Se abre WhatsApp en el mismo clic (si no, el navegador bloquea la ventana) y luego se avisa a Zumit.
    if (info?.phone) window.open(whatsappLink(info.phone, message), '_blank', 'noopener');
    if (needsPlan) request.mutate({ plan, whatsapp_phone: phone.trim() }, { onSuccess: onClose });
    else onClose();
  };

  return (
    <Modal title="Confirmar pago" onClose={onClose} maxWidth={480}>
      <div className={styles.body}>
        {needsPlan && (
          <div className={styles.options} role="radiogroup" aria-label="Plan">
            {options.map((p) => (
              <button
                key={p.code} type="button" role="radio" aria-checked={plan === p.code}
                className={`${styles.option} ${plan === p.code ? styles['option--on'] : ''}`}
                onClick={() => setPlan(p.code)}
              >
                <span className={styles.option__label}>{p.name}</span>
                <span className={styles.option__price}>{fmtCOP(p.launch_price_cop ?? p.price_cop)}</span>
              </button>
            ))}
          </div>
        )}
        {amount > 0 && <p className={styles.total}>Valor a pagar: <strong>{fmtCOP(amount)}</strong></p>}

        <p className={styles.lead}><strong>1. Haz el pago</strong></p>
        <p className={`${styles.note} ${styles.instructions}`}>
          {info?.payment_instructions || 'Escríbenos por WhatsApp y te damos los datos para pagar.'}
        </p>
        <p className={styles.note}>
          Como referencia o concepto pon el nombre de tu negocio y tu número: <strong>{reference}</strong>
        </p>

        <label className={bill.profile__field}>Tu número de WhatsApp
          <input className={bill.profile__input} value={phone} onChange={(e) => setPhone(e.target.value)}
                 inputMode="tel" autoComplete="tel" placeholder="300 123 4567" />
        </label>

        <p className={styles.lead}><strong>2. Avísanos</strong></p>
        <p className={styles.note}>
          Pulsa el botón: se abre WhatsApp con el mensaje ya escrito. Solo adjunta el comprobante y envíalo.
          Activamos tu plan apenas veamos el pago.
        </p>
        <div className={styles.actions}>
          <Button size="sm" variant="ghost" onClick={onClose} disabled={request.isPending}>Cerrar</Button>
          <Button size="sm" disabled={!valid || request.isPending} onClick={confirm}>
            {request.isPending ? 'Enviando…' : info?.phone ? 'Ya pagué: enviar por WhatsApp' : 'Ya pagué: avisar a Zumit'}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
