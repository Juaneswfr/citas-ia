import { useState, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/lib/auth-context';
import { listCustomers, createCustomer } from '@/lib/api/conversations';
import { Avatar } from '@/components/hilo/primitives';
import { Icon } from '@/components/hilo/icons';
import type { CustomerOut } from '@/lib/types/api';
import s from './AppointmentDialog.module.css';

interface CustomerSearchProps {
  value: CustomerOut | null;
  onChange: (c: CustomerOut | null) => void;
}

export function CustomerSearch({ value, onChange }: CustomerSearchProps) {
  const { workspaceId } = useAuth();
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery]           = useState('');
  const [open, setOpen]             = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [newPhone, setNewPhone]     = useState('');
  const [newName, setNewName]       = useState('');

  const { data: customers = [] } = useQuery({
    queryKey: ['customers-raw', workspaceId],
    queryFn: () => listCustomers(workspaceId!),
    enabled: !!workspaceId,
    staleTime: 60_000,
  });

  const createMut = useMutation({
    mutationFn: (body: { phone: string; name: string }) => createCustomer(workspaceId!, body),
    onSuccess: (created) => {
      qc.invalidateQueries({ queryKey: ['customers-raw', workspaceId] });
      qc.invalidateQueries({ queryKey: ['customers', workspaceId] });
      qc.invalidateQueries({ queryKey: ['customers-list', workspaceId] });
      onChange(created);
      setShowCreate(false);
      setOpen(false);
      setQuery('');
    },
  });

  const q = query.toLowerCase();
  const filtered = customers.filter(c =>
    (c.name ?? '').toLowerCase().includes(q) || c.phone.includes(q),
  ).slice(0, 8);

  // ── Token (cliente seleccionado) ─────────────────────────────────────────
  if (value) {
    return (
      <div className={s['cs-token']}>
        <Avatar name={value.name ?? value.phone} size={26} hue="wine" />
        <div className={s['cs-token-info']}>
          <span className={s['cs-token-name']}>{value.name ?? value.phone}</span>
          {value.name && <span className={s['cs-token-phone']}>{value.phone}</span>}
        </div>
        <button
          type="button"
          className={s['cs-token-clear']}
          onClick={() => { onChange(null); setQuery(''); }}
          aria-label="Quitar cliente"
        >
          <Icon name="x" size={13} />
        </button>
      </div>
    );
  }

  // ── Buscador ─────────────────────────────────────────────────────────────
  return (
    <div className={s['cs-wrap']}>
      <div className={`${s['cs-input-wrap']} ${open ? s['cs-input-wrap--open'] : ''}`}>
        <Icon name="search" size={14} className={s['cs-search-icon']} />
        <input
          ref={inputRef}
          className={s['cs-input']}
          placeholder="Buscar por nombre o teléfono…"
          value={query}
          onChange={e => { setQuery(e.target.value); setOpen(true); setShowCreate(false); }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => { setOpen(false); setShowCreate(false); }, 180)}
          autoComplete="off"
        />
      </div>

      {open && (
        <div className={s['cs-dropdown']}>
          {!showCreate && (
            <>
              {filtered.map(c => (
                <button
                  key={c.id}
                  type="button"
                  className={s['cs-option']}
                  onMouseDown={() => { onChange(c); setOpen(false); setQuery(''); }}
                >
                  <Avatar name={c.name ?? c.phone} size={28} hue="wine" />
                  <div className={s['cs-option-info']}>
                    <span className={s['cs-option-name']}>{c.name ?? '—'}</span>
                    <span className={s['cs-option-phone']}>{c.phone}</span>
                  </div>
                </button>
              ))}

              {filtered.length === 0 && !query && (
                <div className={s['cs-empty']}>Escribe para buscar…</div>
              )}

              <button
                type="button"
                className={s['cs-create-row']}
                onMouseDown={() => {
                  setShowCreate(true);
                  // pre-fill si parece teléfono
                  if (/^[\d+\s()-]{4,}$/.test(query)) {
                    setNewPhone(query); setNewName('');
                  } else {
                    setNewName(query); setNewPhone('');
                  }
                }}
              >
                <Icon name="plus" size={14} />
                <span>Nuevo cliente</span>
              </button>
            </>
          )}

          {showCreate && (
            <div className={s['cs-create-form']}>
              <div className={s['cs-create-title']}>Nuevo cliente</div>
              <input
                className={s['cs-create-input']}
                placeholder="Teléfono *"
                value={newPhone}
                onChange={e => setNewPhone(e.target.value)}
                autoFocus
              />
              <input
                className={s['cs-create-input']}
                placeholder="Nombre *"
                value={newName}
                onChange={e => setNewName(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && newPhone.trim() && newName.trim()) {
                    createMut.mutate({ phone: newPhone.trim(), name: newName.trim() });
                  }
                }}
              />
              <div className={s['cs-create-actions']}>
                <button
                  type="button"
                  className={s['cs-create-cancel']}
                  onMouseDown={() => setShowCreate(false)}
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  className={s['cs-create-btn']}
                  disabled={!newPhone.trim() || !newName.trim() || createMut.isPending}
                  onMouseDown={() => createMut.mutate({ phone: newPhone.trim(), name: newName.trim() })}
                >
                  {createMut.isPending ? 'Creando…' : 'Crear'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
