// Configuración de la cuenta de cobro: quién cobra y qué dice el documento.
// Sin estos datos no se puede generar ninguna cuenta de cobro (el backend se lo dice a quien lo intente).

import { useState } from 'react';
import { Button } from '@/components/hilo/primitives';
import { AsyncState } from '@/components/finanzas/ui';
import { useIssuer, useSaveIssuer } from '@/hooks/use-billing';
import type { Issuer } from '@/lib/types/billing';
import styles from './Admin.module.css';
import bill from './Billing.module.css';
import cartera from './Cartera.module.css';

const EMPTY: Issuer = {
  legal_name: '', id_type: 'CC', id_number: '', city: '', address: '', email: '', phone: '',
  payment_instructions: '', legal_note: '',
};

function Form({ saved }: { saved: Issuer | null }) {
  const save = useSaveIssuer();
  const [draft, setDraft] = useState<Issuer>({ ...EMPTY, ...(saved ?? {}) });
  const text = (key: keyof Issuer) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setDraft({ ...draft, [key]: e.target.value });
  const emailOk = !draft.email?.trim() || /^\S+@\S+\.\S+$/.test(draft.email.trim());
  const valid = draft.legal_name.trim().length >= 2 && draft.id_number.trim().length >= 5 && emailOk;
  const clean = (v: string | null) => (v ?? '').trim() || null;

  return (
    <div className={styles.admin__view}>
      {!saved && (
        <p className={bill.notice}>
          Aún no hay datos de quien cobra. Mientras no los guardes no se puede generar ninguna cuenta de cobro.
        </p>
      )}

      <section className={styles.panel}>
        <h3 className={styles.panel__title}>Quién cobra</h3>
        <p className={cartera.hint}>Aparece arriba de cada cuenta de cobro («Debe a») y en la firma.</p>
        <div className={cartera.form}>
          <div className={cartera.form__grid}>
            <label className={cartera.form__field}>Nombre o razón social
              <input className={cartera.form__input} value={draft.legal_name} onChange={text('legal_name')} maxLength={200} />
            </label>
            <label className={cartera.form__field}>Tipo de documento
              <select className={cartera.form__input} value={draft.id_type} onChange={text('id_type')}>
                <option value="CC">Cédula de ciudadanía</option>
                <option value="NIT">NIT</option>
                <option value="CE">Cédula de extranjería</option>
                <option value="PASAPORTE">Pasaporte</option>
              </select>
            </label>
            <label className={cartera.form__field}>Número de documento
              <input className={cartera.form__input} value={draft.id_number} onChange={text('id_number')} maxLength={30} inputMode="text" />
            </label>
            <label className={cartera.form__field}>Ciudad
              <input className={cartera.form__input} value={draft.city ?? ''} onChange={text('city')} maxLength={80} />
            </label>
            <label className={cartera.form__field}>Dirección
              <input className={cartera.form__input} value={draft.address ?? ''} onChange={text('address')} maxLength={200} />
            </label>
            <label className={cartera.form__field}>Teléfono
              <input className={cartera.form__input} value={draft.phone ?? ''} onChange={text('phone')} maxLength={30} inputMode="tel" />
            </label>
            <label className={cartera.form__field}>Correo
              <input className={cartera.form__input} type="email" value={draft.email ?? ''} onChange={text('email')} />
            </label>
          </div>
          {!emailOk && <p className={cartera.form__hint}>Ese correo no parece válido.</p>}
        </div>
      </section>

      <section className={styles.panel}>
        <h3 className={styles.panel__title}>Qué dice el documento</h3>
        <div className={cartera.form}>
          <label className={cartera.form__field}>Forma de pago
            <textarea className={cartera.form__input} rows={4} value={draft.payment_instructions ?? ''} maxLength={1000}
                      onChange={text('payment_instructions')}
                      placeholder="Aún no hay un medio de pago definido. Cuando lo haya: banco, tipo y número de cuenta, o Nequi." />
          </label>
          <p className={cartera.form__hint}>Sale en el PDF y en el correo. Si lo dejas vacío, esa sección no aparece.</p>
          <label className={cartera.form__field}>Nota legal al pie
            <textarea className={cartera.form__input} rows={3} value={draft.legal_note ?? ''} maxLength={600}
                      onChange={text('legal_note')} placeholder="Por ejemplo, lo que indique la contadora sobre el IVA." />
          </label>
          <p className={cartera.form__hint}>
            La define la contadora: el sistema no asume si cobras IVA o no. Si lo dejas vacío, no se imprime nada.
          </p>
          <div className={cartera.form__actions}>
            <Button disabled={!valid || save.isPending}
                    onClick={() => save.mutate({
                      ...draft, legal_name: draft.legal_name.trim(), id_number: draft.id_number.trim(),
                      city: clean(draft.city), address: clean(draft.address), phone: clean(draft.phone),
                      email: clean(draft.email), payment_instructions: clean(draft.payment_instructions),
                      legal_note: clean(draft.legal_note),
                    })}>
              Guardar
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}

export function IssuerTab() {
  const issuer = useIssuer();
  return (
    <AsyncState isLoading={issuer.isLoading} isError={issuer.isError} isEmpty={false} emptyText="" onRetry={issuer.refetch}>
      {/* key: al guardar o recargar, el formulario vuelve a partir de lo guardado */}
      {!issuer.isLoading && <Form key={issuer.data?.legal_name ?? 'nuevo'} saved={issuer.data ?? null} />}
    </AsyncState>
  );
}
