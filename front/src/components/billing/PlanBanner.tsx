// Aviso de arriba del panel: prueba por vencer, pago vencido, asistente en pausa o citas por agotarse.
// Solo lo ve quien puede arreglarlo (el dueño). El resto del equipo no recibe nada que no pueda resolver.

import { Link } from '@tanstack/react-router';
import { useBillingSummary } from '@/hooks/use-billing';
import { planNotice } from '@/lib/billing-notices';
import styles from './Billing.module.css';

export function PlanBanner() {
  const { data } = useBillingSummary();
  const notice = planNotice(data);
  if (!notice) return null;
  const tone = notice.tone === 'info' ? '' : styles[`banner--${notice.tone}`];
  return (
    <div className={`${styles.banner} ${tone}`} role="status">
      <span>{notice.text}</span>
      <Link to="/settings" className={styles.banner__link}>Ver mi plan</Link>
    </div>
  );
}
