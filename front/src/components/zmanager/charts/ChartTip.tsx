// Tooltip de los gráficos: el valor manda y el nombre acompaña; cada fila lleva una línea corta del color de su serie.
// Los nombres vienen de datos (nombres de planes o de negocios): React los escapa, nunca se inserta HTML.

import type { ReactNode } from 'react';
import styles from './Charts.module.css';

interface TipEntry {
  name?: string | number;
  value?: number | string | null;
  dataKey?: string | number;
  color?: string;
  payload?: Record<string, unknown>;
}

export interface ChartTipProps {
  active?: boolean;
  payload?: TipEntry[];
  label?: string | number;
  /** Cómo se escribe un valor (por serie). */
  format?: (value: number, entry: TipEntry) => string;
  /** Color de la línea de cada fila. Por defecto: `payload.color` de la barra o el de la serie en `colors`. */
  colors?: Record<string, string>;
  title?: (label: string | number | undefined, entry: TipEntry | undefined) => ReactNode;
  /** Una nota debajo de las filas (por ejemplo, cuántos negocios son). */
  note?: (entry: TipEntry | undefined) => ReactNode;
  /** Oculta las series sin valor (por ejemplo, un estado con 0 negocios). */
  hideZero?: boolean;
}

export function ChartTip({ active, payload, label, format, colors, title, note, hideZero }: ChartTipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const rows = payload.filter((e) => e.value !== undefined && e.value !== null && !(hideZero && Number(e.value) === 0));
  if (rows.length === 0) return null;
  const first = rows[0];
  return (
    <div className={styles.tip} role="status">
      <div className={styles.tip__title}>{title ? title(label, first) : label}</div>
      {rows.map((entry, i) => {
        const key = (typeof entry.payload?.color === 'string' && entry.payload.color) || colors?.[String(entry.dataKey)] || entry.color;
        const value = typeof entry.value === 'number' ? (format ? format(entry.value, entry) : entry.value.toLocaleString('es-CO')) : String(entry.value);
        return (
          <div key={`${entry.dataKey}-${i}`} className={styles.tip__row}>
            <span className={styles.tip__name}>
              <span className={styles.tip__key} style={{ '--key': key } as React.CSSProperties} />
              {entry.name}
            </span>
            <span className={styles.tip__value}>{value}</span>
          </div>
        );
      })}
      {note && note(first) ? <p className={styles.tip__note}>{note(first)}</p> : null}
    </div>
  );
}
