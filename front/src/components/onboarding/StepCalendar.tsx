import { useState } from 'react';
import { toast } from 'sonner';
import { getGoogleCalendarUrl } from '@/lib/api/auth';
import type { CalendarOut } from '@/lib/types/api';
import { ConnectCard } from './ConnectCard';

interface StepCalendarProps {
  calendars: CalendarOut[];
  workspaceId: string | null;
}

export function StepCalendar({ calendars, workspaceId }: StepCalendarProps) {
  const [loading, setLoading] = useState(false);
  const connected = calendars.some(c => c.sync_status === 'active');
  const activeCalendar = calendars.find(c => c.sync_status === 'active');

  const handleConnect = async () => {
    if (!workspaceId) { toast.error('No se encontró el workspace. Recarga la página.'); return; }
    setLoading(true);
    try {
      const { url } = await getGoogleCalendarUrl(workspaceId, 'onboarding');
      window.location.href = url;
    } catch {
      toast.error('No se pudo iniciar la conexión con Google. Intenta de nuevo.');
      setLoading(false);
    }
  };

  return (
    <ConnectCard
      icon="calendar" color="var(--steel)" bg="color-mix(in srgb, var(--steel) 14%, var(--surface))"
      title="Google Calendar"
      sub={connected && activeCalendar ? activeCalendar.name : 'Fuente principal de disponibilidad'}
      connected={connected} onConnect={handleConnect} loading={loading}
      foot="El agente lee tu calendario para no agendar sobre citas existentes y escribe las nuevas reservas ahí mismo."
    />
  );
}
