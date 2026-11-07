import { useState, useEffect } from 'react';
import { format, addMinutes, parseISO } from 'date-fns';
import { es } from 'date-fns/locale';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/lib/auth-context';
import { useCreateAppointment } from '@/hooks/use-appointments';
import { useServices } from '@/hooks/use-services';
import { listCalendars, listChannels } from '@/lib/api/channels';
import { Button } from '@/components/hilo/primitives';
import { fmtCOP } from '@/lib/hilo-data';
import { CustomerSearch } from './CustomerSearch';
import type { CustomerOut } from '@/lib/types/api';
import styles from './AppointmentDialog.module.css';

interface AppointmentDialogProps {
  open: boolean;
  onClose: () => void;
  initialDate?: string;
  initialTime?: string;
}

export function AppointmentDialog({ open, onClose, initialDate, initialTime }: AppointmentDialogProps) {
  const { workspaceId } = useAuth();

  const { data: services = [] } = useServices(true);
  const { data: calendars = [] } = useQuery({
    queryKey: ['calendars', workspaceId],
    queryFn: () => listCalendars(workspaceId!),
    enabled: !!workspaceId,
    staleTime: 60_000,
  });
  const { data: channels = [] } = useQuery({
    queryKey: ['channels', workspaceId],
    queryFn: () => listChannels(workspaceId!),
    enabled: !!workspaceId,
    staleTime: 60_000,
  });

  const [customer, setCustomer] = useState<CustomerOut | null>(null);
  const [serviceId, setServiceId] = useState('');
  const [date, setDate] = useState(initialDate ?? format(new Date(), 'yyyy-MM-dd'));
  const [time, setTime] = useState(initialTime ?? '09:00');

  useEffect(() => { if (open && initialDate) setDate(initialDate); }, [open, initialDate]);
  useEffect(() => { if (open && initialTime) setTime(initialTime); }, [open, initialTime]);
  useEffect(() => {
    if (!open) { setCustomer(null); setServiceId(''); }
  }, [open]);

  const createMutation  = useCreateAppointment();
  const activeCalendar  = calendars.find(c => c.sync_status === 'active');
  const activeChannel   = channels.find(c => c.status === 'active');
  const selectedService = services.find(s => s.id === serviceId);

  const endTime = selectedService && time
    ? format(addMinutes(parseISO(`${date}T${time}`), selectedService.dur), 'HH:mm')
    : null;

  const dateLabel = date
    ? format(parseISO(date), "EEEE d 'de' MMMM", { locale: es })
    : '';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customer) return;
    try {
      await createMutation.mutateAsync({
        customer_id: customer.id,
        service_id:  serviceId,
        ...(activeChannel  ? { channel_id:  activeChannel.id  } : {}),
        ...(activeCalendar ? { calendar_id: activeCalendar.id } : {}),
        start_at:  new Date(`${date}T${time}:00`).toISOString(),
        price_cop: selectedService?.price ?? 0,
      });
      onClose();
    } catch {
      // onError del mutation ya mostró el toast
    }
  };

  const canSubmit = !!customer && !!serviceId && !!date && !!time && !createMutation.isPending;

  if (!open) return null;

  return (
    <div className={styles['apt-dialog-overlay']} onClick={onClose}>
      <div
        className={styles['apt-dialog-panel']}
        onClick={e => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Nueva cita"
      >
        <div className={styles['apt-dialog-header']}>
          <h2 className={styles['apt-dialog-title']}>Nueva cita</h2>
          <button className={styles['apt-dialog-close']} type="button" onClick={onClose} aria-label="Cerrar">✕</button>
        </div>

        <form onSubmit={handleSubmit} className={styles['apt-dialog']}>

          {!activeCalendar && (
            <div className={styles['apt-dialog__info']}>
              Sin Google Calendar — la cita se guardará sin sincronizar al calendario
            </div>
          )}

          {/* Cliente */}
          <div className={styles['apt-dialog__field']}>
            <label className={styles['apt-dialog__label']}>Cliente</label>
            <CustomerSearch value={customer} onChange={setCustomer} />
          </div>

          {/* Servicio */}
          <div className={styles['apt-dialog__field']}>
            <label className={styles['apt-dialog__label']}>Servicio</label>
            <div className={styles['svc-list']}>
              {services.map(s => (
                <button
                  key={s.id}
                  type="button"
                  className={`${styles['svc-item']} ${serviceId === s.id ? styles['svc-item--sel'] : ''}`}
                  onClick={() => setServiceId(s.id)}
                >
                  <span className={styles['svc-item-name']}>{s.name}</span>
                  <span className={styles['svc-item-meta']}>
                    <span className={styles['svc-item-dur']}>{s.dur} min</span>
                    <span className={styles['svc-item-price']}>{fmtCOP(s.price)}</span>
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Fecha y hora */}
          <div className={styles['apt-dialog__grid']}>
            <div className={styles['apt-dialog__field']}>
              <label className={styles['apt-dialog__label']} htmlFor="apt-date">Fecha</label>
              <input
                id="apt-date"
                type="date"
                className={styles['apt-dialog__input']}
                value={date}
                onChange={e => setDate(e.target.value)}
                required
              />
            </div>
            <div className={styles['apt-dialog__field']}>
              <label className={styles['apt-dialog__label']} htmlFor="apt-time">Hora</label>
              <input
                id="apt-time"
                type="time"
                className={styles['apt-dialog__input']}
                value={time}
                onChange={e => setTime(e.target.value)}
                required
              />
            </div>
          </div>

          {/* Preview */}
          {selectedService && endTime && (
            <div className={styles['apt-dialog__preview']}>
              <div className={styles['apt-dialog__preview-body']}>
                <div className={styles['apt-dialog__preview-svc']}>{selectedService.name}</div>
                <div className={styles['apt-dialog__preview-detail']}>
                  {dateLabel} · {time} – {endTime} · {selectedService.dur} min
                </div>
              </div>
              <div className={styles['apt-dialog__preview-price']}>
                {fmtCOP(selectedService.price)}
              </div>
            </div>
          )}

          <div className={styles['apt-dialog__footer']}>
            <Button variant="ghost" size="sm" type="button" onClick={onClose}>Cancelar</Button>
            <Button variant="primary" size="sm" disabled={!canSubmit}>
              {createMutation.isPending ? 'Guardando…' : 'Crear cita'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
