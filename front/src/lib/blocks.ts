// Bloqueos de agenda: de la lista del backend a lo que dibujan el día y la semana.

import { addDays, differenceInMinutes, format, parseISO, startOfDay } from 'date-fns';
import type { AvailabilityBlockOut } from '@/lib/types/api';

/** Un bloqueo visto dentro de un día. Los de varios calendarios con el mismo tramo y motivo van juntos. */
export interface BlockSegment {
  key: string;
  /** Bloqueos que componen el tramo: quitarlo los borra todos. */
  ids: string[];
  calendarIds: string[];
  dayKey: string;     // yyyy-MM-dd, día local
  startMin: number;   // minutos desde las 00:00 de ese día
  endMin: number;     // hasta 1440
  reason: string | null;
  /** Límites reales del bloqueo (puede abarcar varios días). */
  start: Date;
  end: Date;
}

const DAY_MIN = 24 * 60;

/** Parte cada bloqueo por día local y junta los idénticos de distintos calendarios. */
export function blockSegments(blocks: AvailabilityBlockOut[]): BlockSegment[] {
  const grouped = new Map<string, BlockSegment>();
  for (const block of blocks) {
    const start = parseISO(block.start_at);
    const end = parseISO(block.end_at);
    for (let day = startOfDay(start); day < end; day = addDays(day, 1)) {
      const startMin = Math.max(0, differenceInMinutes(start, day));
      const endMin = Math.min(DAY_MIN, differenceInMinutes(end, day));
      if (endMin <= startMin) continue;
      const dayKey = format(day, 'yyyy-MM-dd');
      const key = `${dayKey}|${startMin}|${endMin}|${block.reason ?? ''}`;
      const found = grouped.get(key);
      if (found) {
        found.ids.push(block.id);
        found.calendarIds.push(block.calendar_id);
      } else {
        grouped.set(key, {
          key, ids: [block.id], calendarIds: [block.calendar_id], dayKey, startMin, endMin,
          reason: block.reason, start, end,
        });
      }
    }
  }
  return [...grouped.values()].sort((a, b) => a.dayKey.localeCompare(b.dayKey) || a.startMin - b.startMin);
}

const hhmm = (min: number) => `${String(Math.floor(min / 60) % 24).padStart(2, '0')}:${String(min % 60).padStart(2, '0')}`;

/** «Todo el día» o «14:00 – 16:00». */
export function rangeLabel(segment: Pick<BlockSegment, 'startMin' | 'endMin'>): string {
  if (segment.startMin === 0 && segment.endMin >= DAY_MIN - 1) return 'Todo el día';
  return `${hhmm(segment.startMin)} – ${hhmm(segment.endMin)}`;
}

/** Un tramo listo para dibujar: con el texto de quién queda sin recibir citas. */
export interface BlockView extends BlockSegment {
  who: string;
}

export function blockViews(
  blocks: AvailabilityBlockOut[],
  calendarNames: Map<string, string>,
  totalCalendars: number,
): BlockView[] {
  return blockSegments(blocks).map((s) => ({ ...s, who: blockWho(s, calendarNames, totalCalendars) }));
}

/** Quién queda sin recibir citas: «Todo el equipo» o los nombres de los calendarios bloqueados. */
export function blockWho(
  segment: Pick<BlockSegment, 'calendarIds'>,
  calendarNames: Map<string, string>,
  totalCalendars: number,
): string {
  const ids = [...new Set(segment.calendarIds)];
  if (ids.length > 1 && ids.length >= totalCalendars) return 'Todo el equipo';
  return ids.map((id) => calendarNames.get(id) ?? 'Calendario').join(', ');
}
