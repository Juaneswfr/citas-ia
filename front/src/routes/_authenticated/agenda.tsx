import { createFileRoute } from '@tanstack/react-router';
import { useState, useMemo, useEffect } from 'react';
import { toast } from 'sonner';
import { startOfWeek, endOfWeek, addDays, addWeeks, addMonths, format, isSameMonth, isSameWeek } from 'date-fns';
import { es } from 'date-fns/locale';
import { useAuth } from '@/lib/auth-context';
import { useQuery } from '@tanstack/react-query';
import { Button, Avatar, Segmented } from '@/components/hilo/primitives';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useWeekAppointments } from '@/hooks/use-appointments';
import { useTeamMembers } from '@/hooks/use-team';
import { listCalendars, listChannels } from '@/lib/api/channels';
import { WeekCalendar } from '@/components/agenda/WeekCalendar';
import { DayView } from '@/components/agenda/DayView';
import { MonthView } from '@/components/agenda/MonthView';
import { AppointmentDialog } from '@/components/agenda/AppointmentDialog';
import { AppointmentDetail } from '@/components/agenda/AppointmentDetail';
import styles from './agenda.module.css';

export const Route = createFileRoute('/_authenticated/agenda')({
  head: () => ({ meta: [{ title: 'Agenda · Hilo' }] }),
  component: AgendaPage,
});

const HUES = ['clay', 'wine', 'mustard', 'steel', 'sage', 'plum', 'teal'];
const memberHue = (id: string) => HUES[id.charCodeAt(0) % HUES.length];

function AgendaPage() {
  const { workspaceId } = useAuth();
  const isMobile = useIsMobile();

  const [view,       setView]       = useState<'day' | 'week' | 'month'>('week');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [slotDate,   setSlotDate]   = useState<string | undefined>();
  const [slotTime,   setSlotTime]   = useState<string | undefined>();
  const [anchor,     setAnchor]     = useState(() => new Date());
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data: team = [] } = useTeamMembers();

  const { data: calendars = [] } = useQuery({
    queryKey: ['calendars', workspaceId],
    queryFn:  () => listCalendars(workspaceId!),
    enabled:  !!workspaceId,
    staleTime: 60_000,
  });
  const { data: channels = [] } = useQuery({
    queryKey: ['channels', workspaceId],
    queryFn:  () => listChannels(workspaceId!),
    enabled:  !!workspaceId,
    staleTime: 60_000,
  });

  const anchorKey = format(anchor, 'yyyy-MM-dd');

  const weekStart = useMemo(() => startOfWeek(anchor, { weekStartsOn: 1 }), [anchorKey]); // eslint-disable-line react-hooks/exhaustive-deps
  const weekEnd   = useMemo(() => endOfWeek(weekStart, { weekStartsOn: 1 }), [weekStart]);

  // Título y navegación según la vista: ◀ ▶ mueven un día, una semana o un mes.
  const title = useMemo(() => {
    if (view === 'day')   return format(anchor, "EEEE d 'de' MMMM", { locale: es });
    if (view === 'month') return format(anchor, 'MMMM yyyy', { locale: es });
    return `${format(weekStart, 'd MMM', { locale: es })} – ${format(weekEnd, 'd MMM', { locale: es })}`;
  }, [view, anchorKey, weekStart, weekEnd]); // eslint-disable-line react-hooks/exhaustive-deps

  const shift = (dir: 1 | -1) =>
    setAnchor(a => (view === 'day' ? addDays(a, dir) : view === 'week' ? addWeeks(a, dir) : addMonths(a, dir)));

  const now = new Date();
  const isCurrent = view === 'day'
    ? anchorKey === format(now, 'yyyy-MM-dd')
    : view === 'week' ? isSameWeek(anchor, now, { weekStartsOn: 1 }) : isSameMonth(anchor, now);

  const openDay = (date: Date) => { setAnchor(date); setView('day'); };

  const { data: weekEvents = [], isLoading: weekLoading, isError: weekError } =
    useWeekAppointments({ weekStart, weekEnd });

  useEffect(() => {
    if (weekError) toast.error('No se pudo cargar la agenda semanal.');
  }, [weekError]);

  const hasCalendar = calendars.some(c => c.sync_status === 'active');
  const hasChannel  = channels.some(c => c.status === 'active');

  const openNewCita = (date?: string, time?: string) => {
    setSlotDate(date);
    setSlotTime(time);
    setDialogOpen(true);
  };

  return (
    <div className={styles['agenda-page']}>

      <AppointmentDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        initialDate={slotDate}
        initialTime={slotTime}
      />

      {selectedId && <AppointmentDetail appointmentId={selectedId} onClose={() => setSelectedId(null)} />}

      {/* ── Toolbar ── */}
      <div className={styles['agenda-page__toolbar']}>
        <div className={styles['agenda-page__nav']}>
          <Button variant="secondary" size="sm" icon="chevL" aria-label="Anterior" onClick={() => shift(-1)} />
          <h2 className={styles['agenda-page__title']}>{title}</h2>
          <Button variant="secondary" size="sm" icon="chev" aria-label="Siguiente" onClick={() => shift(1)} />
          <Button variant="ghost" size="sm" disabled={isCurrent} onClick={() => setAnchor(new Date())}>Hoy</Button>
        </div>
        <div className={styles['agenda-page__controls']}>
          <Segmented
            options={[{ value: 'day', label: 'Día' }, { value: 'week', label: 'Semana' }, { value: 'month', label: 'Mes' }]}
            value={view}
            onChange={v => setView(v as 'day' | 'week' | 'month')}
          />
          {!isMobile && (
            <Button variant="secondary" size="sm" icon="block">Bloquear</Button>
          )}
          <Button variant="primary" size="sm" icon="plus" onClick={() => openNewCita()}>
            {isMobile ? '' : 'Nueva cita'}
          </Button>
        </div>
      </div>

      {/* ── Config alert ── */}
      {!hasCalendar && (
        <div className={styles['agenda-page__alert']}>
          Conecta Google Calendar en Ajustes para crear citas.
        </div>
      )}
      {hasCalendar && !hasChannel && (
        <div className={styles['agenda-page__alert']}>
          Sin WhatsApp conectado — las citas se crean pero el bot no enviará confirmaciones.
        </div>
      )}

      {/* ── Team filter ── */}
      {team.length > 0 && (
        <div className={styles['agenda-page__team-filter']}>
          <span className="eyebrow">Equipo</span>
          {team.map(m => (
            <span key={m.id} className={styles['agenda-page__team-member']}>
              <Avatar name={m.name ?? m.email ?? '?'} hue={memberHue(m.id)} size={22} />
              <span className={styles['agenda-page__team-name']}>
                {(m.name ?? m.email ?? '?').split(' ')[0]}
              </span>
            </span>
          ))}
        </div>
      )}

      {/* ── Views ── */}
      {view === 'day' && (
        <DayView date={anchor} onNewCita={(date) => openNewCita(date)} onEventClick={setSelectedId} />
      )}
      {view === 'week' && (
        <div className={styles['agenda-page__scroll']}>
          <WeekCalendar
            weekStart={weekStart}
            cols={7}
            events={weekEvents}
            isLoading={weekLoading}
            onSlotClick={(date, time) => openNewCita(date, time)}
            onEventClick={setSelectedId}
          />
        </div>
      )}
      {view === 'month' && <MonthView month={anchor} onDayClick={openDay} />}
    </div>
  );
}
