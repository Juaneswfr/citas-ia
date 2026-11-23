// Fundadores y parámetros de la plataforma. El margen, los costos y las tarifas de Meta viven en Costos: aquí solo lo que
// gobierna cuándo se cobra, se avisa y se pausa.

import { useState } from 'react';
import { Link } from '@tanstack/react-router';
import { Button } from '@/components/hilo/primitives';
import { useBillingSettings } from '@/hooks/use-billing';
import type { BillingOverview } from '@/lib/types/billing';
import styles from './Admin.module.css';
import bill from './Billing.module.css';
import cartera from './Cartera.module.css';

const SETTING_LABEL: Record<string, string> = {
  trial_days: 'Días de prueba gratis',
  launch_discount_pct: 'Descuento de lanzamiento (%)',
  launch_discount_cycles: 'Ciclos con descuento',
  quota_warn_pct: 'Avisar al llegar a este % de las citas',
  quota_margin: 'Citas de margen al agotar el cupo',
  grace_days: 'Días sin pago antes de pausar',
  retention_days: 'Días que se conservan los datos',
  upcoming_notice_days: 'Días de aviso antes de cada cobro',
  low_usage_pct: 'Uso bajo (%) para proponer bajar de plan',
  founder_cap: 'Cupo de fundadores',
};

function SettingRow({ name, value }: { name: string; value: number }) {
  const { setting } = useBillingSettings();
  const [draft, setDraft] = useState(String(value));
  const changed = draft !== String(value) && draft.trim() !== '' && Number.isFinite(Number(draft));
  return (
    <div className={bill.rows__item}>
      <span className={bill.rows__name}>{SETTING_LABEL[name] ?? name}</span>
      <span className={bill.rows__value}>
        <input className={`${styles.input} ${bill['inline-form__input']}`} type="number" min={0} value={draft}
               aria-label={SETTING_LABEL[name] ?? name} onChange={(e) => setDraft(e.target.value)} />
        <Button size="sm" variant="secondary" disabled={!changed || setting.isPending}
                onClick={() => setting.mutate({ key: name, value: Number(draft) })}>Guardar</Button>
      </span>
    </div>
  );
}

export function BillingParams({ data, onOpen }: { data: BillingOverview; onOpen: (id: string, name: string) => void }) {
  return (
    <>
      <p className={bill.notice}>
        ¿Cuánto te cuesta cada negocio y cuánto ganas con él? Eso está en{' '}
        <Link to="/zmanager/costos" className={cartera.link}>Costos</Link>, junto con la tasa del dólar y las
        tarifas de Meta.
      </p>

      <div className={styles.cols}>
        <section className={styles.panel}>
          <h3 className={styles.panel__title}>Fundadores</h3>
          <p className={bill.bill__hint}>
            {data.founders.cap > 0 ? `${data.founders.taken} de ${data.founders.cap} cupos usados.` : 'Define el cupo en los parámetros para poder marcar fundadores.'}
          </p>
          {data.founders.items.length === 0 ? <p className={styles.panel__empty}>Aún no hay fundadores.</p> : (
            <div className={bill.rows}>
              {data.founders.items.map((f) => (
                <div key={f.workspace_id} className={bill.rows__item}>
                  <button type="button" className={`${bill.rows__name} ${bill['rows__name--link']}`}
                          onClick={() => onOpen(f.workspace_id, f.workspace)}>{f.workspace}</button>
                  <span className={bill.rows__value}>n.º {f.number}</span>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className={styles.panel}>
          <h3 className={styles.panel__title}>Parámetros</h3>
          <div className={bill.rows}>
            {Object.keys(SETTING_LABEL).map((key) => <SettingRow key={`${key}-${data.settings[key]}`} name={key} value={data.settings[key] ?? 0} />)}
          </div>
        </section>
      </div>
    </>
  );
}
