// Gráficas del dashboard en SVG propio: colores de la UI (tokens), animación de entrada y valores al pasar el cursor.
// Sin librerías: cada una es una función de sus datos, y el movimiento vive en Charts.module.css.

import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { format, parseISO } from 'date-fns';
import { es } from 'date-fns/locale';
import { CountUp } from '@/components/hilo/CountUp';
import { dayName, hourLabel } from '@/lib/dashboard-insights';
import type { DayPoint, HeatCell, TopService } from '@/lib/api/dashboard';
import styles from './Charts.module.css';

const css = (vars: Record<string, string | number>) => vars as CSSProperties;

/**
 * Ancho real del contenedor. El SVG se dibuja a ese ancho (viewBox = píxeles), así los textos de los ejes
 * no se encogen cuando la tarjeta es angosta o la pantalla es de teléfono.
 */
function useWidth(initial = 640) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(initial);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const apply = () => setWidth(Math.max(260, Math.round(el.clientWidth)));
    apply();
    const observer = new ResizeObserver(apply);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return [ref, width] as const;
}

/** El tooltip va al lado del cursor, no encima: la mitad izquierda lo abre a la derecha y al revés. */
const tipSide = (fraction: number) => (fraction > 0.55 ? styles.tipLeft : styles.tipRight);

/** Tope «redondo» para el eje: 7 → 8, 130 000 → 150 000. */
function niceCeil(peak: number): number {
  if (peak <= 0) return 1;
  const unit = Math.pow(10, Math.floor(Math.log10(peak)));
  const m = peak / unit;
  return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * unit;
}

// ── Barras apiladas: citas por día ────────────────────────────────────────────

export function StackedBars({ days, todayKey }: { days: DayPoint[]; todayKey: string }) {
  const [hover, setHover] = useState<number | null>(null);
  const [box, W] = useWidth();
  const H = 236, left = 30, right = 8, top = 14, bottom = 38;
  const pw = W - left - right, ph = H - top - bottom;
  const peak = Math.max(1, ...days.map((d) => d.completed + d.lost + d.open));
  const max = peak <= 4 ? 4 : Math.ceil(peak / 4) * 4; // 4 tramos de número entero
  const band = pw / days.length;
  const bw = Math.min(34, band * 0.62);
  const y = (v: number) => top + ph - (v / max) * ph;
  const hovered = hover === null ? null : days[hover];
  const narrow = band < 30; // en teléfono solo cabe la inicial del día

  return (
    <div className={styles.chart} ref={box}>
      <svg viewBox={`0 0 ${W} ${H}`} className={styles.svg} role="img" aria-label="Citas por día, últimos 14 días"
           onPointerLeave={() => setHover(null)}>
        {[0, 1, 2, 3, 4].map((i) => {
          const v = (max / 4) * i;
          return (
            <g key={i}>
              <line x1={left} x2={W - right} y1={y(v)} y2={y(v)} className={i === 0 ? styles.axis : styles.grid} />
              <text x={left - 8} y={y(v) + 4} className={styles.tick} textAnchor="end">{v}</text>
            </g>
          );
        })}

        {days.map((d, i) => {
          const x = left + band * i + (band - bw) / 2;
          let acc = 0;
          const segments = ([['completed', d.completed], ['open', d.open], ['lost', d.lost]] as const)
            .filter(([, v]) => v > 0)
            .map(([key, v]) => {
              const seg = { key, y: y(acc + v), h: y(acc) - y(acc + v) };
              acc += v;
              return seg;
            });
          const isToday = d.date === todayKey;
          const date = parseISO(d.date);
          return (
            <g key={d.date} tabIndex={0} aria-label={`${format(date, "EEEE d 'de' MMMM", { locale: es })}: ${d.completed} completadas, ${d.open} por atender, ${d.lost} perdidas`}
               onPointerEnter={() => setHover(i)} onFocus={() => setHover(i)} onBlur={() => setHover(null)}>
              <rect x={left + band * i} y={top} width={band} height={ph} className={styles.hit} opacity={hover === i ? 1 : 0} />
              <g className={styles.bar} style={css({ '--i': i })}>
                {segments.length === 0
                  ? <rect x={x} y={y(0) - 2} width={bw} height={2} rx={1} className={styles.empty} />
                  : segments.map((s) => <rect key={s.key} x={x} y={s.y} width={bw} height={Math.max(s.h, 1)} rx={2} className={styles[`seg_${s.key}`]} />)}
              </g>
              <text x={left + band * i + band / 2} y={H - 18} textAnchor="middle" className={isToday ? styles.labelToday : styles.label}>
                {narrow ? format(date, 'EEEEE', { locale: es }).toUpperCase() : format(date, 'EEE', { locale: es })}
              </text>
              <text x={left + band * i + band / 2} y={H - 5} textAnchor="middle" className={isToday ? styles.labelToday : styles.labelSoft}>
                {format(date, 'd')}
              </text>
            </g>
          );
        })}
      </svg>

      {hovered && hover !== null && (
        <div className={`${styles.tip} ${tipSide((left + band * hover + band / 2) / W)}`}
             style={css({ '--x': `${((left + band * hover + band / 2) / W) * 100}%` })} role="status">
          <strong>{format(parseISO(hovered.date), "EEEE d 'de' MMM", { locale: es })}</strong>
          <span><i className={styles.dot_completed} />Completadas <b>{hovered.completed}</b></span>
          <span><i className={styles.dot_open} />Por atender <b>{hovered.open}</b></span>
          <span><i className={styles.dot_lost} />Perdidas <b>{hovered.lost}</b></span>
        </div>
      )}

      <div className={styles.legend}>
        <span><i className={styles.dot_completed} />Completadas</span>
        <span><i className={styles.dot_open} />Por atender</span>
        <span><i className={styles.dot_lost} />Canceladas y no asistió</span>
      </div>
    </div>
  );
}

// ── Área: ingresos cobrados por día ───────────────────────────────────────────

/** Curva suave que pasa por los puntos (Catmull-Rom → Bézier), sin salirse de la zona de dibujo. */
function smoothPath(pts: Array<[number, number]>, minY: number, maxY: number): string {
  if (pts.length < 2) return '';
  const clamp = (v: number) => Math.min(maxY, Math.max(minY, v));
  let d = `M${pts[0][0]},${pts[0][1]}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] ?? p2;
    d += ` C${p1[0] + (p2[0] - p0[0]) / 6},${clamp(p1[1] + (p2[1] - p0[1]) / 6)} ${p2[0] - (p3[0] - p1[0]) / 6},${clamp(p2[1] - (p3[1] - p1[1]) / 6)} ${p2[0]},${p2[1]}`;
  }
  return d;
}

export function AreaChart({ points, money }: { points: Array<{ date: string; value: number }>; money: (n: number) => string }) {
  const [hover, setHover] = useState<number | null>(null);
  const [box, W] = useWidth();
  const H = 228, left = 58, right = 12, top = 14, bottom = 30;
  const pw = W - left - right, ph = H - top - bottom;
  const max = niceCeil(Math.max(...points.map((p) => p.value), 0));
  const x = (i: number) => left + (points.length > 1 ? (i / (points.length - 1)) * pw : pw / 2);
  const y = (v: number) => top + ph - (v / max) * ph;
  const coords = points.map((p, i): [number, number] => [x(i), y(p.value)]);
  const line = smoothPath(coords, top, top + ph);
  const area = coords.length > 1 ? `${line} L${x(points.length - 1)},${top + ph} L${x(0)},${top + ph} Z` : '';
  const last = coords[coords.length - 1];
  // En angosto, menos fechas para que no se pisen.
  const labelAt = new Set(pw < 420 ? [0, 10, 20, points.length - 1] : [0, 5, 10, 15, 20, 25, points.length - 1]);

  const move = (e: React.PointerEvent<SVGRectElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const rel = ((e.clientX - box.left) / box.width) * W;
    setHover(Math.min(points.length - 1, Math.max(0, Math.round(((rel - left) / pw) * (points.length - 1)))));
  };

  return (
    <div className={styles.chart} ref={box}>
      <svg viewBox={`0 0 ${W} ${H}`} className={styles.svg} role="img" aria-label="Ingresos cobrados por día, últimos 30 días">
        <defs>
          <linearGradient id="area-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--wine)" stopOpacity="0.32" />
            <stop offset="100%" stopColor="var(--wine)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, 1, 2, 3].map((i) => {
          const v = (max / 3) * i;
          return (
            <g key={i}>
              <line x1={left} x2={W - right} y1={y(v)} y2={y(v)} className={i === 0 ? styles.axis : styles.grid} />
              <text x={left - 8} y={y(v) + 4} className={styles.tick} textAnchor="end">{money(v)}</text>
            </g>
          );
        })}
        {points.map((p, i) => labelAt.has(i) && (
          <text key={p.date} x={x(i)} y={H - 9} textAnchor={i === 0 ? 'start' : i === points.length - 1 ? 'end' : 'middle'} className={styles.labelSoft}>
            {format(parseISO(p.date), 'd MMM', { locale: es })}
          </text>
        ))}

        {area && <path d={area} fill="url(#area-fill)" className={styles.areaFill} />}
        {line && <path d={line} pathLength={1} className={styles.areaLine} fill="none" />}
        {last && <circle cx={last[0]} cy={last[1]} r={4} className={styles.areaDot} />}

        {hover !== null && (
          <g pointerEvents="none">
            <line x1={x(hover)} x2={x(hover)} y1={top} y2={top + ph} className={styles.cross} />
            <circle cx={x(hover)} cy={y(points[hover].value)} r={5} className={styles.crossDot} />
          </g>
        )}
        <rect x={left} y={top} width={pw} height={ph} fill="transparent" onPointerMove={move} onPointerLeave={() => setHover(null)} />
      </svg>

      {hover !== null && (
        <div className={`${styles.tip} ${tipSide(x(hover) / W)}`} style={css({ '--x': `${(x(hover) / W) * 100}%` })} role="status">
          <strong>{format(parseISO(points[hover].date), "EEEE d 'de' MMM", { locale: es })}</strong>
          <span>Cobrado <b>{money(points[hover].value)}</b></span>
        </div>
      )}
    </div>
  );
}

// ── Dona: cómo terminaron las citas ───────────────────────────────────────────

export interface Slice { key: string; label: string; value: number; color: string }

export function Donut({ slices, centerValue, centerLabel }: { slices: Slice[]; centerValue: number; centerLabel: string }) {
  const R = 44, C = 2 * Math.PI * R;
  const total = slices.reduce((s, x) => s + x.value, 0);
  let offset = 0;

  return (
    <div className={styles.donut}>
      <div className={styles.donutRing}>
        <svg viewBox="0 0 120 120" role="img" aria-label={`Cómo terminaron las citas: ${slices.map((s) => `${s.value} ${s.label.toLowerCase()}`).join(', ')}`}>
          <circle cx="60" cy="60" r={R} className={styles.donutTrack} />
          {total > 0 && slices.filter((s) => s.value > 0).map((s, i) => {
            const len = (s.value / total) * C;
            const arc = (
              <circle key={s.key} cx="60" cy="60" r={R} className={styles.donutArc} stroke={s.color}
                      style={css({ '--c': C, '--len': len, '--gap': C - len, '--off': -offset, '--i': i })} />
            );
            offset += len;
            return arc;
          })}
        </svg>
        <div className={styles.donutCenter}>
          <b><CountUp value={centerValue} format={(n) => `${Math.round(n)} %`} /></b>
          <span>{centerLabel}</span>
        </div>
      </div>
      <ul className={styles.donutLegend}>
        {slices.map((s) => (
          <li key={s.key}>
            <i style={{ background: s.color }} />
            <span>{s.label}</span>
            <b className="tnum">{s.value}</b>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ── Barras horizontales: servicios más pedidos ────────────────────────────────

export function HBars({ items, money }: { items: TopService[]; money?: (n: number) => string }) {
  const max = Math.max(1, ...items.map((s) => s.count));
  return (
    <ul className={styles.hbars}>
      {items.map((s, i) => (
        <li key={s.id}>
          <div className={styles.hbarHead}>
            <span className={styles.hbarName} title={s.name}>{s.name}</span>
            <span className={styles.hbarNum}><b className="tnum">{s.count}</b> {s.count === 1 ? 'cita' : 'citas'}
              {money && s.revenue_cop != null && <em> · {money(s.revenue_cop)}</em>}</span>
          </div>
          <div className={styles.hbarTrack}>
            <span className={styles.hbarFill} style={css({ width: `${(s.count / max) * 100}%`, '--i': i })} />
          </div>
        </li>
      ))}
    </ul>
  );
}

// ── Mapa de calor: horas y días más llenos ────────────────────────────────────

export function Heatmap({ cells }: { cells: HeatCell[] }) {
  const [focus, setFocus] = useState<HeatCell | null>(null);
  const counts = new Map(cells.map((c) => [`${c.dow}-${c.hour}`, c.count]));
  const max = Math.max(1, ...cells.map((c) => c.count));
  const hours = cells.map((c) => c.hour);
  const first = Math.min(8, ...hours), last = Math.max(19, ...hours);
  const range = Array.from({ length: last - first + 1 }, (_, i) => first + i);

  return (
    <div className={styles.heat}>
      <div className={styles.heatGrid} style={css({ '--cols': range.length })} role="grid" aria-label="Citas por día de la semana y hora">
        <span />
        {range.map((h) => <span key={h} className={styles.heatHour}>{h % 2 === 0 ? hourLabel(h).replace(' ', '') : ''}</span>)}
        {Array.from({ length: 7 }, (_, dow) => (
          <div key={dow} role="row" className={styles.heatRow}>
            <span className={styles.heatDay}>{dayName(dow).slice(0, 3)}</span>
            {range.map((h, col) => {
              const n = counts.get(`${dow}-${h}`) ?? 0;
              const t = n / max;
              return (
                <button
                  key={h}
                  type="button"
                  role="gridcell"
                  className={`${styles.heatCell} ${n === max && n > 0 ? styles.heatMax : ''}`}
                  style={{
                    ...css({ '--i': dow * range.length + col }),
                    // Más oscuro, más citas; sin citas queda el fondo neutro de la hoja de estilos.
                    ...(n > 0 ? { background: `color-mix(in srgb, var(--wine) ${Math.round(14 + t * 78)}%, var(--surface-2))` } : {}),
                  }}
                  aria-label={`${dayName(dow)} ${hourLabel(h)}: ${n} ${n === 1 ? 'cita' : 'citas'}`}
                  onPointerEnter={() => setFocus({ dow, hour: h, count: n })}
                  onFocus={() => setFocus({ dow, hour: h, count: n })}
                  onPointerLeave={() => setFocus(null)}
                  onBlur={() => setFocus(null)}
                />
              );
            })}
          </div>
        ))}
      </div>
      <div className={styles.heatReadout} aria-live="polite">
        {focus
          ? <><b>{dayName(focus.dow)} · {hourLabel(focus.hour)}</b> — {focus.count} {focus.count === 1 ? 'cita' : 'citas'} en 60 días</>
          : <span className={styles.heatScale}>Menos <i /><i /><i /><i /> Más</span>}
      </div>
    </div>
  );
}
