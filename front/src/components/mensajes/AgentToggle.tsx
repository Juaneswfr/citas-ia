import { useUpdateCustomer } from '@/hooks/use-customers';
import styles from './AgentToggle.module.css';

interface AgentToggleProps {
  customerId: string;
  /** Valor guardado en el cliente (`customers.agent_enabled`). */
  enabled: boolean;
}

/**
 * Pausa o reactiva el agente con este cliente desde la conversación.
 * Es el mismo interruptor de la ficha del cliente: apagado, el agente deja de responderle,
 * pero el equipo puede seguir escribiéndole desde aquí.
 */
export function AgentToggle({ customerId, enabled }: AgentToggleProps) {
  const update = useUpdateCustomer(customerId);
  // Mientras guarda se ve lo que se pidió, no el valor anterior del servidor.
  const pending = update.isPending ? update.variables?.agent_enabled : undefined;
  const on = pending ?? enabled;

  return (
    <div className={styles['agent-toggle']}>
      <span className={styles['agent-toggle__text']}>
        <span className={styles['agent-toggle__title']}>Agente</span>
        <span className={`${styles['agent-toggle__state']} ${on ? '' : styles['agent-toggle__state--off']}`}>
          {on ? 'Activo' : 'En pausa'}
        </span>
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={on}
        aria-label={on ? 'Pausar el agente con este cliente' : 'Reactivar el agente con este cliente'}
        title={on ? 'El agente responde solo a este cliente' : 'El agente no responde a este cliente'}
        disabled={update.isPending}
        className={`${styles.switch} ${on ? styles['switch--on'] : ''}`}
        onClick={() => update.mutate({ agent_enabled: !on })}
      >
        <span className={styles.switch__knob} />
      </button>
    </div>
  );
}
