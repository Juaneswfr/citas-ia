// Comprobantes de un cobro/pago: ver, adjuntar más y eliminar.

import { useState } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/hilo/primitives';
import { useAttachments, useDeleteAttachment, useOpenAttachment, useUploadAttachment } from '@/hooks/use-accounting';
import type { AttachmentOut } from '@/lib/types/accounting';
import { formatBytes } from '@/lib/receipts';
import { AsyncState, Modal } from './ui';
import { ReceiptPicker } from './ReceiptPicker';
import styles from './Finanzas.module.css';

interface AttachmentsDialogProps {
  movementId: string;
  title: string;
  onClose: () => void;
}

export function AttachmentsDialog({ movementId, title, onClose }: AttachmentsDialogProps) {
  const { data = [], isLoading, isError, refetch } = useAttachments(movementId);
  const upload = useUploadAttachment();
  const remove = useDeleteAttachment();
  const openAttachment = useOpenAttachment();
  const [file, setFile] = useState<File | null>(null);

  const handleUpload = async () => {
    if (!file) return;
    try {
      await upload.mutateAsync({ movementId, file });
      setFile(null);
    } catch {
      // onError de la mutación ya notificó.
    }
  };

  const handleDelete = (item: AttachmentOut) => {
    if (window.confirm(`¿Eliminar el comprobante «${item.original_name}»? No se puede deshacer.`)) {
      remove.mutate(item.id);
    }
  };

  return (
    <Modal title={title} onClose={onClose}>
      <AsyncState isLoading={isLoading} isError={isError} isEmpty={data.length === 0} onRetry={refetch}
                  emptyText="Este movimiento aún no tiene comprobantes.">
        <div className={styles.list}>
          {data.map((item) => (
            <div key={item.id} className={styles.row}>
              <div className={styles.row__main}>
                <div className={styles.row__title}>{item.original_name}</div>
                <div className={styles.row__meta}>
                  {formatBytes(item.size_bytes)} · {new Date(item.created_at).toLocaleDateString('es-CO')}
                </div>
              </div>
              <div className={styles.row__actions}>
                <Button size="sm" variant="secondary" onClick={() => openAttachment(item.id, item.original_name)}>Ver</Button>
                <Button size="sm" variant="ghost" onClick={() => handleDelete(item)}>Eliminar</Button>
              </div>
            </div>
          ))}
        </div>
      </AsyncState>
      <ReceiptPicker file={file} onChange={setFile} onInvalid={(message) => toast.error(message)} />
      <div className={styles.modal__actions}>
        <Button type="button" variant="ghost" onClick={onClose}>Cerrar</Button>
        <Button type="button" disabled={!file || upload.isPending} onClick={handleUpload}>
          {upload.isPending ? 'Subiendo…' : 'Guardar comprobante'}
        </Button>
      </div>
    </Modal>
  );
}
