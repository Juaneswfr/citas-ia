// Piezas presentacionales del panel de plataforma.

import type { ReactNode } from 'react';
import { Button } from '@/components/hilo/primitives';
import { ADMIN_PAGE_SIZE } from '@/lib/api/admin';
import styles from './Admin.module.css';

type Tone = 'ok' | 'warn' | 'bad' | 'brand' | 'neutral';

export function ToneTag({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  const toneClass = tone === 'neutral' ? '' : styles[`tag--${tone}`];
  return <span className={`${styles.tag} ${toneClass}`}>{children}</span>;
}

interface BarListProps {
  items: { key: string; label: string; count: number }[];
  emptyText: string;
}

/** Barras horizontales proporcionales al mayor valor. El ancho es un valor dinámico de runtime. */
export function BarList({ items, emptyText }: BarListProps) {
  const max = Math.max(1, ...items.map((item) => item.count));
  if (items.length === 0) return <p className={styles.panel__empty}>{emptyText}</p>;
  return (
    <div className={styles.bars}>
      {items.map((item) => (
        <div key={item.key} className={styles.bar}>
          <span className={styles.bar__label} title={item.label}>{item.label}</span>
          <div className={styles.bar__track}>
            <div className={styles.bar__fill} style={{ width: `${Math.round((item.count / max) * 100)}%` }} />
          </div>
          <span className={`tnum ${styles.bar__value}`}>{item.count}</span>
        </div>
      ))}
    </div>
  );
}

interface PagerProps {
  page: number;
  total: number;
  onPage: (page: number) => void;
}

/** Paginación simple; no se muestra si todo cabe en una página. */
export function Pager({ page, total, onPage }: PagerProps) {
  const pages = Math.ceil(total / ADMIN_PAGE_SIZE);
  if (pages <= 1) return null;
  return (
    <div className={styles.pager}>
      <Button size="sm" variant="secondary" disabled={page === 0} onClick={() => onPage(page - 1)}>Anterior</Button>
      <span>Página {page + 1} de {pages}</span>
      <Button size="sm" variant="secondary" disabled={page + 1 >= pages} onClick={() => onPage(page + 1)}>Siguiente</Button>
    </div>
  );
}
