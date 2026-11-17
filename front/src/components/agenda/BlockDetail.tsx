import { format, isSameDay } from 'date-fns';
import { es } from 'date-fns/locale';
import { Button } from '@/components/hilo/primitives';
import { Modal } from '@/components/finanzas/ui';
import { useDeleteBlocks } from '@/hooks/use-blocks';
import { rangeLabel, type BlockView } from '@/lib/blocks';
import styles from './BlockDialog.module.css';

interface BlockDetailProps {
  block: BlockView;
  /** Solo el dueño o un administrador pueden quitar bloqueos. */
  canManage: boolean;
  onClose: () => void;
}

function Fact({ label, value, plain }: { label: string; value: string; plain?: boolean }) {
  return (
    <div>
      <div className={styles['block-detail__label']}>{label}</div>
      <div className={`${styles['block-detail__value']} ${plain ? styles['block-detail__value--plain'] : ''}`}>{value}</div>
    </div>
  );
}

/** Ficha de un horario bloqueado, con la opción de quitarlo. */
export function BlockDetail({ block, canManage, onClose }: BlockDetailProps) {
  const remove = useDeleteBlocks();
  const day = (d: Date) => format(d, "EEEE d 'de' MMMM", { locale: es });
  // El bloqueo real puede abarcar varios días aunque aquí se vea el de un solo día.
  const multiDay = !isSameDay(block.start, new Date(block.end.getTime() - 1));

  return (
    <Modal title="Horario bloqueado" onClose={onClose}>
      <div className={styles['block-detail']}>
        <div className={styles['block-detail__facts']}>
          <Fact label={multiDay ? 'Desde' : 'Día'} value={day(multiDay ? block.start : new Date(`${block.dayKey}T00:00:00`))} />
          {multiDay && <Fact label="Hasta" value={day(new Date(block.end.getTime() - 1))} />}
          <Fact label="Horario" value={rangeLabel(block)} plain />
          <Fact label="Sin recibir citas" value={block.who} plain />
          {block.reason && <Fact label="Motivo" value={block.reason} plain />}
        </div>

        <p className={styles['block-detail__note']}>
          Mientras esté bloqueado, el agente no ofrece ni agenda citas en este horario.
          {multiDay && ' Quitar el bloqueo libera todos los días.'}
          {!canManage && ' Solo el dueño o un administrador puede quitarlo.'}
        </p>

        <div className={styles['block-detail__footer']}>
          <Button variant="ghost" size="sm" type="button" onClick={onClose}>Cerrar</Button>
          {canManage && (
            <Button variant="danger" size="sm" type="button" disabled={remove.isPending}
                    onClick={() => remove.mutate(block.ids, { onSuccess: onClose })}>
              {remove.isPending ? 'Quitando…' : 'Quitar bloqueo'}
            </Button>
          )}
        </div>
      </div>
    </Modal>
  );
}
