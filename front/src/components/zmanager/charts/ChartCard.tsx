// La tarjeta de un gráfico: título, leyenda (siempre con dos o más series), y el cambio entre el gráfico y su tabla.
// La tabla es el equivalente accesible: todo valor que un tooltip o una etiqueta muestre está también ahí.

import { useState, type ReactNode } from 'react';
import { Segmented } from '@/components/hilo/primitives';
import styles from './Charts.module.css';

export interface LegendItem {
  label: string;
  color: string;
}

export interface ChartTable {
  caption: string;
  columns: string[];
  rows: (string | number)[][];
}

interface ChartCardProps {
  title: string;
  sub?: string;
  legend?: LegendItem[];
  table?: ChartTable;
  /** Controles propios del gráfico (por ejemplo, los chips de métrica). */
  tools?: ReactNode;
  /** true mientras se recarga: se conserva el gráfico anterior a la vista, más tenue. */
  stale?: boolean;
  /** Si hay texto, no se dibuja el gráfico sino este aviso. */
  empty?: string | null;
  children: ReactNode;
}

const VIEWS = [{ value: 'chart', label: 'Gráfico' }, { value: 'table', label: 'Tabla' }];

export function ChartCard({ title, sub, legend, table, tools, stale, empty, children }: ChartCardProps) {
  const [view, setView] = useState<'chart' | 'table'>('chart');
  const showTable = view === 'table' && !!table;
  return (
    <section className={`${styles.card} ${stale ? styles['card--stale'] : ''}`} aria-busy={stale || undefined}>
      <div className={styles.card__head}>
        <div>
          <h3 className={styles.card__title}>{title}</h3>
          {sub && <p className={styles.card__sub}>{sub}</p>}
        </div>
        <div className={styles.card__tools}>
          {tools}
          {table && !empty && <Segmented size="sm" options={VIEWS} value={view} onChange={(v) => setView(v as 'chart' | 'table')} />}
        </div>
      </div>

      {legend && legend.length >= 2 && !showTable && (
        <ul className={styles.legend} aria-label="Leyenda">
          {legend.map((item) => (
            <li key={item.label} className={styles.legend__item}>
              <span className={styles.legend__key} style={{ '--key': item.color } as React.CSSProperties} />
              {item.label}
            </li>
          ))}
        </ul>
      )}

      <div className={styles.card__body}>
        {empty ? <div className={styles.empty}>{empty}</div> : showTable ? (
          <div className={styles.table__scroll}>
            <table className={styles.table}>
              <caption>{table.caption}</caption>
              <thead><tr>{table.columns.map((c) => <th key={c} scope="col">{c}</th>)}</tr></thead>
              <tbody>
                {table.rows.map((row, i) => (
                  <tr key={i}>{row.map((cell, j) => <td key={j}>{cell}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : children}
      </div>
    </section>
  );
}
