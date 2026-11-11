// Terceros: clientes (se crean solos desde las citas), proveedores, empleados y otros.

import { useState } from 'react';
import { Button } from '@/components/hilo/primitives';
import { useCreateThirdParty, useThirdParties } from '@/hooks/use-accounting';
import type { ThirdPartyKind } from '@/lib/types/accounting';
import { AsyncState, Field, Modal } from './ui';
import styles from './Finanzas.module.css';

const KIND_LABEL: Record<ThirdPartyKind, string> = {
  customer: 'Cliente', supplier: 'Proveedor', employee: 'Empleado', other: 'Otro',
};

function NewThirdPartyDialog({ onClose }: { onClose: () => void }) {
  const create = useCreateThirdParty();
  const [kind, setKind] = useState<ThirdPartyKind>('supplier');
  const [name, setName] = useState('');
  const [documentId, setDocumentId] = useState('');
  const [phone, setPhone] = useState('');

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      await create.mutateAsync({
        kind, name: name.trim(), document_id: documentId.trim() || null, phone: phone.trim() || null,
      });
      onClose();
    } catch {
      // onError de la mutación ya notificó.
    }
  };

  return (
    <Modal title="Nuevo tercero" onClose={onClose}>
      <form className={styles.form} onSubmit={handleSubmit}>
        <Field label="Tipo">
          <select className={styles.field__input} value={kind} onChange={(e) => setKind(e.target.value as ThirdPartyKind)}>
            {(Object.keys(KIND_LABEL) as ThirdPartyKind[]).map((k) => <option key={k} value={k}>{KIND_LABEL[k]}</option>)}
          </select>
        </Field>
        <Field label="Nombre"><input className={styles.field__input} value={name} onChange={(e) => setName(e.target.value)} /></Field>
        <div className={styles.form__grid}>
          <Field label="NIT / Cédula"><input className={styles.field__input} value={documentId} onChange={(e) => setDocumentId(e.target.value)} /></Field>
          <Field label="Teléfono"><input className={styles.field__input} value={phone} onChange={(e) => setPhone(e.target.value)} /></Field>
        </div>
        <div className={styles.modal__actions}>
          <Button type="button" variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button type="submit" disabled={!name.trim() || create.isPending}>Guardar</Button>
        </div>
      </form>
    </Modal>
  );
}

export function ThirdPartiesTab() {
  const [creating, setCreating] = useState(false);
  const { data = [], isLoading, isError, refetch } = useThirdParties();

  return (
    <>
      <div className={styles.toolbar}>
        <h2 className={styles.toolbar__title}>Terceros</h2>
        <Button icon="plus" onClick={() => setCreating(true)}>Nuevo tercero</Button>
      </div>
      <AsyncState isLoading={isLoading} isError={isError} isEmpty={data.length === 0} onRetry={refetch}
                  emptyText="Aún no hay terceros. Los clientes se agregan solos al completar citas.">
        <div className={styles.list}>
          {data.map((party) => (
            <div key={party.id} className={styles.row}>
              <div className={styles.row__main}>
                <div className={styles.row__title}>{party.name}</div>
                <div className={styles.row__meta}>
                  {[party.document_id, party.phone, party.email].filter(Boolean).join(' · ') || 'Sin datos de contacto'}
                </div>
              </div>
              <span className={styles.tag}>{KIND_LABEL[party.kind]}</span>
            </div>
          ))}
        </div>
      </AsyncState>
      {creating && <NewThirdPartyDialog onClose={() => setCreating(false)} />}
    </>
  );
}
