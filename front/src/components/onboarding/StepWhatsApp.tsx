import { useState } from 'react';
import { useAuth } from '@/lib/auth-context';
import { createKapsoOnboardingLink } from '@/lib/api/channels';
import type { ChannelOut } from '@/lib/types/api';
import { ConnectCard } from './ConnectCard';

interface StepWhatsAppProps {
  channels: ChannelOut[];
  onConnected: () => void;
}

export function StepWhatsApp({ channels, onConnected }: StepWhatsAppProps) {
  const { workspaceId } = useAuth();
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const connected = channels.some(c => c.status === 'active');
  const activeChannel = channels.find(c => c.status === 'active');

  const connectViaKapso = async () => {
    if (!workspaceId) return;
    setLoading(true);
    setErrorMsg('');
    try {
      const { url } = await createKapsoOnboardingLink(workspaceId);
      window.open(url, '_blank');
      onConnected();
    } catch (err: any) {
      setErrorMsg(err?.detail ?? err?.message ?? 'Error generando enlace de conexión.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <ConnectCard
      icon="whatsapp" color="var(--wa-ink)" bg="var(--wa-bg)"
      title="WhatsApp Business · Coexistencia"
      sub={connected && activeChannel ? (activeChannel.display_name ?? activeChannel.phone_number) : 'Vincula tu número actual'}
      connected={connected} onConnect={connectViaKapso} loading={loading}
      foot={
        <span>
          <strong style={{ fontWeight: 500, color: 'var(--ink-1)' }}>Coexistencia</strong>{' '}
          deja que sigas usando WhatsApp en tu celular mientras el agente responde en paralelo.
          {errorMsg && <span style={{ display: 'block', marginTop: 8, color: 'var(--error, #c0392b)', fontSize: 12.5 }}>{errorMsg}</span>}
        </span>
      }
    />
  );
}
