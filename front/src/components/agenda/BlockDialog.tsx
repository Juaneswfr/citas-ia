import { useEffect, useState } from 'react';
import { addDays, format, parseISO } from 'date-fns';
import { Button } from '@/components/hilo/primitives';
import { Modal } from '@/components/finanzas/ui';
import { useCreateBlocks } from '@/hooks/use-blocks';
import type { CalendarOut } from '@/lib/types/api';
import dialog from './AppointmentDialog.module.css';
import styles from './BlockDialog.module.css';

interface BlockDialogProps {
  open: boolean;
  onClose: () => void;
  initialDate?: string;
  /** Calendarios activos: cada uno es un profesional que puede quedar sin recibir citas. */
  calendars: CalendarOut[];
}

const ALL = 'all';
const calendarLabel = (c: CalendarOut) => c.member_name ?? c.name;

/** Bloquear un horario: mientras dure, ni el agente ni el panel agendan citas ahí. */
export function BlockDialog({ open, onClose, initialDate, calendars }: BlockDialogProps) {
  const today = format(new Date(), 'yyyy-MM-dd');
  const [who, setWho] = useState(ALL);
  const [startDate, setStartDate] = useState(initialDate ?? today);
  const [endDate, setEndDate] = useState(initialDate ?? today);
  const [allDay, setAllDay] = useState(false);
  const [startTime, setStartTime] = useState('09:00');
  const [endTime, setEndTime] = useState('18:00');
  const [reason, setReason] = useState('');
  const create = useCreateBlocks();

  useEffect(() => {
    if (!open) return;
    setWho(calendars.length === 1 ? calendars[0].id : ALL);
    setStartDate(initialDate ?? today);
    setEndDate(initialDate ?? today);
    setAllDay(false); setStartTime('09:00'); setEndTime('18:00'); setReason('');
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!open) return null;

  // «Todo el día» llega hasta la medianoche del último día elegido.
  const startLocal = `${startDate}T${allDay ? '00:00' : startTime}:00`;
  const endLocal = allDay
    ? `${format(addDays(parseISO(endDate), 1), 'yyyy-MM-dd')}T00:00:00`
    : `${endDate}T${endTime}:00`;
  const validRange = !!startDate && !!endDate && new Date(endLocal) > new Date(startLocal);
  const canSubmit = validRange && calendars.length > 0 && !create.isPending;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    create.mutate(
      {
        calendarIds: who === ALL ? calendars.map((c) => c.id) : [who],
        start_at: new Date(startLocal).toISOString(),
        end_at: new Date(endLocal).toISOString(),
        reason: reason.trim() || undefined,
      },
      { onSuccess: onClose },
    );
  };

  return (
    <Modal title="Bloquear horario" onClose={onClose}>
      <form onSubmit={submit} className={dialog['apt-dialog']}>
        {calendars.length === 0 && (
          <div className={dialog['apt-dialog__info']}>Conecta un Google Calendar en Ajustes para poder bloquear horarios.</div>
        )}

        <div className={dialog['apt-dialog__field']}>
          <label className={dialog['apt-dialog__label']} htmlFor="blk-who">Quién no recibe citas</label>
          <select id="blk-who" className={dialog['apt-dialog__input']} value={who} onChange={(e) => setWho(e.target.value)}>
            {calendars.length > 1 && <option value={ALL}>Todo el equipo</option>}
            {calendars.map((c) => <option key={c.id} value={c.id}>{calendarLabel(c)}</option>)}
          </select>
        </div>

        <label className={styles['block-dialog__check']}>
          <input type="checkbox" checked={allDay} onChange={(e) => setAllDay(e.target.checked)} />
          Todo el día
        </label>

        <div className={dialog['apt-dialog__grid']}>
          <div className={dialog['apt-dialog__field']}>
            <label className={dialog['apt-dialog__label']} htmlFor="blk-start-date">Desde</label>
            <input id="blk-start-date" type="date" className={dialog['apt-dialog__input']} value={startDate} required
                   onChange={(e) => { setStartDate(e.target.value); if (endDate < e.target.value) setEndDate(e.target.value); }} />
          </div>
          <div className={dialog['apt-dialog__field']}>
            <label className={dialog['apt-dialog__label']} htmlFor="blk-start-time">Hora</label>
            <input id="blk-start-time" type="time" className={dialog['apt-dialog__input']} value={startTime}
                   disabled={allDay} required={!allDay} onChange={(e) => setStartTime(e.target.value)} />
          </div>
          <div className={dialog['apt-dialog__field']}>
            <label className={dialog['apt-dialog__label']} htmlFor="blk-end-date">Hasta</label>
            <input id="blk-end-date" type="date" className={dialog['apt-dialog__input']} value={endDate} min={startDate} required
                   onChange={(e) => setEndDate(e.target.value)} />
          </div>
          <div className={dialog['apt-dialog__field']}>
            <label className={dialog['apt-dialog__label']} htmlFor="blk-end-time">Hora</label>
            <input id="blk-end-time" type="time" className={dialog['apt-dialog__input']} value={endTime}
                   disabled={allDay} required={!allDay} onChange={(e) => setEndTime(e.target.value)} />
          </div>
        </div>
        {!validRange && startDate && endDate && (
          <div className={dialog['apt-dialog__warning']}>El fin del bloqueo debe ser posterior al inicio.</div>
        )}

        <div className={dialog['apt-dialog__field']}>
          <label className={dialog['apt-dialog__label']} htmlFor="blk-reason">Motivo (solo lo ve el equipo)</label>
          <input id="blk-reason" type="text" className={dialog['apt-dialog__input']} value={reason} maxLength={500}
                 placeholder="Vacaciones, cita médica, capacitación…" onChange={(e) => setReason(e.target.value)} />
        </div>

        <div className={dialog['apt-dialog__info']}>
          Mientras esté bloqueado, el agente no ofrece ni agenda citas en ese horario y tampoco se pueden crear desde la agenda.
          Las citas que ya estén agendadas no se cancelan.
        </div>

        <div className={dialog['apt-dialog__footer']}>
          <Button variant="ghost" size="sm" type="button" onClick={onClose}>Cancelar</Button>
          <Button variant="primary" size="sm" disabled={!canSubmit}>
            {create.isPending ? 'Guardando…' : 'Bloquear horario'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
