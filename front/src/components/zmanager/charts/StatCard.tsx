// Tarjeta de métrica: el valor se cuenta hacia arriba al cargar, con un mini gráfico opcional y una pastilla de degradé.

import { useId } from 'react';
import { Area, AreaChart, ResponsiveContainer } from 'recharts';
import { COLOR, type ColorKey } from './palette';
import { useCountUp, usePrefersReducedMotion } from './motion';
import styles from './Charts.module.css';

interface StatCardProps {
  label: string;
  value: number;
  /** Cómo se escribe el valor (pesos, porcentaje, entero…). */
  format: (n: number) => string;
  hint?: string;
  /** Serie corta para el mini gráfico (por ejemplo, las últimas semanas). Con menos de 2 puntos no se dibuja. */
  spark?: number[];
  color?: ColorKey;
  /** true = el valor se pinta en rojo (algo que atender). */
  alert?: boolean;
}

export function Sparkline({ data, color }: { data: number[]; color: ColorKey }) {
  const gradient = `spark-${useId().replace(/[^a-zA-Z0-9]/g, '')}`;
  const animate = !usePrefersReducedMotion();
  const rows = data.map((v, i) => ({ v, i }));
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={rows} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id={gradient} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={COLOR[color]} stopOpacity={0.32} />
            <stop offset="100%" stopColor={COLOR[color]} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <Area type="monotone" dataKey="v" stroke={COLOR[color]} strokeWidth={2} fill={`url(#${gradient})`} dot={false}
              isAnimationActive={animate} animationDuration={900} animationEasing="ease-out" />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function StatCard({ label, value, format, hint, spark, color = 'plum', alert }: StatCardProps) {
  const shown = useCountUp(value);
  return (
    <div className={styles.stat}>
      <div className={styles.stat__label}>{label}</div>
      <div className={`${styles.stat__value} ${alert ? styles['stat__value--alert'] : ''}`} aria-label={`${label}: ${format(value)}`}>
        <span aria-hidden="true">{format(shown)}</span>
      </div>
      {hint && <div className={styles.stat__hint}>{hint}</div>}
      {spark && spark.length >= 2 && <div className={styles.stat__spark} aria-hidden="true"><Sparkline data={spark} color={color} /></div>}
      <div className={styles.stat__accent} style={{ '--key': COLOR[color] } as React.CSSProperties} />
    </div>
  );
}
