import { useState, useRef, useCallback } from 'react';
import { addDays, format, getDay } from 'date-fns';
import { es } from 'date-fns/locale';
import type { CalendarEvent } from '@/hooks/use-appointments';
import styles from './WeekCalendar.module.css';

const HOURS_START = 7;
const HOURS_END   = 21;
const HOURS       = Array.from({ length: HOURS_END - HOURS_START }, (_, i) => HOURS_START + i);
const PX_PER_HOUR = 68;
const TOTAL_H     = HOURS.length * PX_PER_HOUR;
const SNAP_MIN    = 15; // snap to 15-minute slots
const GHOST_DUR   = 60; // default ghost duration in minutes

interface WeekCalendarProps {
  weekStart: Date;
  cols?: number;         // 6 = Lun-Sáb, 7 = Lun-Dom
  events: CalendarEvent[];
  isLoading?: boolean;
  onSlotClick: (date: string, time: string) => void;
}

function yToTime(offsetY: number): { hour: number; min: number } {
  const rawH   = offsetY / PX_PER_HOUR;
  const h      = Math.floor(rawH) + HOURS_START;
  const rawMin = (rawH % 1) * 60;
  const min    = Math.round(rawMin / SNAP_MIN) * SNAP_MIN % 60;
  const hour   = h + (Math.round(rawMin / SNAP_MIN) * SNAP_MIN >= 60 ? 1 : 0);
  return { hour: Math.min(hour, HOURS_END - 1), min };
}

function timeToY(hour: number, min: number): number {
  return ((hour - HOURS_START) + min / 60) * PX_PER_HOUR;
}

function fmt12(hour: number, min: number): string {
  const h = hour > 12 ? hour - 12 : hour === 0 ? 12 : hour;
  const suffix = hour >= 12 ? 'pm' : 'am';
  return `${h}:${String(min).padStart(2, '0')} ${suffix}`;
}

export function WeekCalendar({ weekStart, cols = 6, events, isLoading = false, onSlotClick }: WeekCalendarProps) {
  const today = new Date();
  const todayStr = format(today, 'yyyy-MM-dd');

  const days = Array.from({ length: cols }, (_, i) => {
    const date = addDays(weekStart, i);
    const isToday = format(date, 'yyyy-MM-dd') === todayStr;
    // getDay: 0=Dom, convert to Mon-based index
    const dayOfWeek = getDay(date); // 0=Dom,1=Lun…6=Sáb
    const label = format(date, 'EEE', { locale: es }).replace(/^\w/, c => c.toUpperCase());
    return { date, isToday, label, num: format(date, 'd'), dateStr: format(date, 'yyyy-MM-dd'), dayOfWeek };
  });

  // Ghost hover state per column
  const [ghost, setGhost] = useState<{ col: number; y: number } | null>(null);
  const colRefs = useRef<(HTMLDivElement | null)[]>([]);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>, col: number) => {
    const rect = colRefs.current[col]?.getBoundingClientRect();
    if (!rect) return;
    const offsetY = Math.max(0, e.clientY - rect.top);
    setGhost({ col, y: offsetY });
  }, []);

  const handleClick = useCallback((e: React.MouseEvent<HTMLDivElement>, col: number) => {
    const rect = colRefs.current[col]?.getBoundingClientRect();
    if (!rect) return;
    const offsetY = Math.max(0, e.clientY - rect.top);
    const { hour, min } = yToTime(offsetY);
    const time = `${String(hour).padStart(2, '0')}:${String(min).padStart(2, '0')}`;
    onSlotClick(days[col].dateStr, time);
  }, [days, onSlotClick]);

  // Now indicator
  const nowH    = today.getHours();
  const nowM    = today.getMinutes();
  const nowY    = nowH >= HOURS_START && nowH < HOURS_END
    ? timeToY(nowH, nowM) : null;

  return (
    <div className={styles['week-calendar']} style={{ '--cols': cols } as React.CSSProperties}>

      {/* ── Header ── */}
      <div className={styles['week-calendar__header']}>
        <div className={styles['week-calendar__gutter-head']} />
        {days.map((d, i) => (
          <div
            key={i}
            className={`${styles['week-calendar__col-header']} ${d.isToday ? styles['week-calendar__col-header--today'] : ''}`}
          >
            <div className={styles['week-calendar__col-day']}>{d.label}</div>
            <div className={`tnum ${styles['week-calendar__col-num']}`}>{d.num}</div>
          </div>
        ))}
      </div>

      {/* ── Body ── */}
      <div className={styles['week-calendar__body']} style={{ height: TOTAL_H + 24 }}>

        {/* Hour gutter */}
        <div className={styles['week-calendar__gutter']} style={{ height: TOTAL_H }}>
          {HOURS.map(h => (
            <div
              key={h}
              className={styles['week-calendar__hour-label']}
              style={{ top: timeToY(h, 0) }}
            >
              {h}:00
            </div>
          ))}
        </div>

        {/* Day columns */}
        {days.map((d, col) => (
          <div
            key={col}
            ref={el => { colRefs.current[col] = el; }}
            className={`${styles['week-calendar__day']} ${d.isToday ? styles['week-calendar__day--today'] : ''}`}
            style={{ height: TOTAL_H }}
            onMouseMove={e => handleMouseMove(e, col)}
            onMouseLeave={() => setGhost(null)}
            onClick={e => handleClick(e, col)}
          >
            {/* Hour + half-hour lines */}
            {HOURS.map(h => (
              <div key={h}>
                <div
                  className={styles['week-calendar__hour-line']}
                  style={{ top: timeToY(h, 0) }}
                />
                <div
                  className={styles['week-calendar__half-line']}
                  style={{ top: timeToY(h, 30) }}
                />
              </div>
            ))}

            {/* Now indicator */}
            {d.isToday && nowY !== null && (
              <div className={styles['week-calendar__now-line']} style={{ top: nowY }}>
                <div className={styles['week-calendar__now-dot']} />
              </div>
            )}

            {/* Ghost hover preview */}
            {ghost?.col === col && (() => {
              const { hour, min } = yToTime(ghost.y);
              const snapY   = timeToY(hour, min);
              const ghostH  = (GHOST_DUR / 60) * PX_PER_HOUR;
              return (
                <div
                  className={styles['week-calendar__ghost']}
                  style={{ top: snapY, height: ghostH }}
                >
                  <span className={styles['week-calendar__ghost-label']}>
                    {fmt12(hour, min)}
                  </span>
                </div>
              );
            })()}

            {/* Skeleton while loading */}
            {isLoading && (
              <div
                className={styles['week-calendar__skeleton']}
                style={{ top: PX_PER_HOUR, height: PX_PER_HOUR * 0.75 }}
              />
            )}

            {/* Events */}
            {!isLoading && events
              .filter(ev => ev.d === col)
              .map((ev, i) => {
                const hue      = `var(--${ev.hue ?? 'wine'})`;
                const topPx    = (ev.s - HOURS_START) * PX_PER_HOUR;
                const heightPx = (ev.m / 60) * PX_PER_HOUR - 2;
                if (topPx < 0 || topPx > TOTAL_H) return null;
                const endH  = ev.s + Math.floor(ev.m / 60);
                const endM  = ev.m % 60;
                return (
                  <div
                    key={i}
                    className={styles['week-calendar__event']}
                    style={{
                      top: topPx,
                      height: heightPx,
                      borderLeftColor: hue,
                      background: `color-mix(in srgb, ${hue} 11%, var(--surface))`,
                    }}
                    title={`${ev.client} · ${ev.svc}`}
                    onClick={e => e.stopPropagation()}
                  >
                    <div className={styles['week-calendar__event-client']}>{ev.client}</div>
                    {ev.m >= 30 && (
                      <div className={styles['week-calendar__event-time']}>
                        {fmt12(ev.s, 0)} – {fmt12(endH, endM)}
                      </div>
                    )}
                    {ev.m >= 45 && (
                      <div className={styles['week-calendar__event-svc']} style={{ color: hue }}>
                        {ev.svc}
                      </div>
                    )}
                  </div>
                );
              })
            }
          </div>
        ))}
      </div>
    </div>
  );
}
