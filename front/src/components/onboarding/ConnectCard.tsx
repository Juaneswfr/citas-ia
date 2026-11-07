import { Icon } from '@/components/hilo/icons';
import { Button, Tag } from '@/components/hilo/primitives';
import s from './onboarding.module.css';

interface ConnectCardProps {
  icon: string;
  color: string;
  bg: string;
  title: string;
  sub: string;
  connected: boolean;
  onConnect: () => void;
  loading?: boolean;
  foot?: React.ReactNode;
}

export function ConnectCard({ icon, color, bg, title, sub, connected, onConnect, loading, foot }: ConnectCardProps) {
  return (
    <div className={`${s['connect-card']} ${connected ? s['connect-card--connected'] : ''}`}>
      <div className={s['connect-card__header']}>
        <span className={s['connect-card__icon']} style={{ background: bg, color }}>
          <Icon name={icon} size={26} />
        </span>
        <div className={s['connect-card__info']}>
          <div className={s['connect-card__title']}>{title}</div>
          <div className={s['connect-card__sub']}>{sub}</div>
        </div>
        {connected
          ? <Tag hue="sage"><Icon name="check" size={13} />Conectado</Tag>
          : loading
            ? <Button variant="primary" disabled>Conectando…</Button>
            : <Button variant="primary" onClick={onConnect}>Conectar</Button>
        }
      </div>
      {foot && <div className={s['connect-card__foot']}>{foot}</div>}
    </div>
  );
}
