import { useState } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/hilo/primitives';
import { getBusinessPreset, getBusinessType, type BusinessTypeId } from '@/lib/business-types';
import { createService } from '@/lib/api/services';
import type { ServiceOut } from '@/lib/types/api';
import s from './onboarding.module.css';

interface StepServicesProps {
  businessType: BusinessTypeId | null;
  services: ServiceOut[];
  workspaceId: string | null;
  onCreated: () => void;
}

export function StepServices({ businessType, services, workspaceId, onCreated }: StepServicesProps) {
  const typeId: BusinessTypeId = businessType ?? 'otro';
  const preset = getBusinessPreset(typeId);
  const typeLabel = businessType ? getBusinessType(typeId).label.toLowerCase() : 'tu negocio';
  const [creating, setCreating] = useState(false);

  const handleCreatePreset = async () => {
    if (!workspaceId) return;
    setCreating(true);
    try {
      await Promise.all(
        preset.services.map(svc =>
          createService(workspaceId, {
            name: svc.name,
            duration_minutes: svc.dur,
            price_cop: svc.price,
          })
        )
      );
      toast.success('Servicios creados correctamente.');
      onCreated();
    } catch {
      toast.error('Error creando servicios. Intenta de nuevo.');
    } finally {
      setCreating(false);
    }
  };

  if (services.length > 0) {
    return (
      <div className={s['services__list']}>
        <div style={{ font: '400 13.5px/1.5 var(--font-sans)', color: 'var(--ink-2)', marginBottom: 4 }}>
          Tienes <strong style={{ color: 'var(--ink-1)' }}>{services.length} servicio{services.length !== 1 ? 's' : ''}</strong> configurados.
          Puedes editarlos en detalle desde la sección Servicios.
        </div>
        {services.slice(0, 6).map(svc => (
          <div key={svc.id} className={s['services__item']}>
            <span className={s['services__item-dot']} />
            <span className={s['services__item-name']}>{svc.name}</span>
            <span className={s['services__item-dur']}>{svc.duration_minutes} min</span>
            <span className={`tnum ${s['services__item-price']}`}>${svc.price_cop.toLocaleString('es-CO')}</span>
          </div>
        ))}
        {services.length > 6 && (
          <div className={s['services__more']}>+{services.length - 6} más</div>
        )}
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <div style={{ font: '400 13.5px/1.5 var(--font-sans)', color: 'var(--ink-2)', marginBottom: 12 }}>
          Servicios típicos de {typeLabel}. Confirma y los crearemos automáticamente.
        </div>
        <div className={s['services__list']}>
          {preset.services.map((svc, i) => (
            <div key={i} className={s['services__item']}>
              <span className={s['services__item-dot']} />
              <span className={s['services__item-name']}>{svc.name}</span>
              <span className={s['services__item-dur']}>{svc.dur} min</span>
              <span className={`tnum ${s['services__item-price']}`}>${svc.price.toLocaleString('es-CO')}</span>
            </div>
          ))}
        </div>
        <Button
          variant="primary" icon="check" style={{ alignSelf: 'flex-start', marginTop: 12 }}
          onClick={handleCreatePreset} disabled={creating}
        >
          {creating ? 'Creando…' : 'Crear estos servicios'}
        </Button>
      </div>

      <div>
        <div style={{ font: '500 12.5px/1 var(--font-sans)', color: 'var(--ink-2)', marginBottom: 12 }}>
          Horarios de atención sugeridos
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {preset.hours.map(h => (
            <div key={h.day} style={{
              display: 'flex', alignItems: 'center', gap: 12, padding: '9px 14px',
              background: h.active ? 'var(--surface)' : 'var(--surface-2)',
              border: '1px solid var(--line)', borderRadius: 'var(--r-md)',
              opacity: h.active ? 1 : 0.5,
            }}>
              <span style={{ width: 80, font: '500 13px/1 var(--font-sans)', color: 'var(--ink-2)' }}>{h.day}</span>
              {h.active
                ? <span style={{ font: '400 13px/1 var(--font-sans)', color: 'var(--ink-1)' }}>{h.open} — {h.close}</span>
                : <span style={{ font: '400 13px/1 var(--font-sans)', color: 'var(--ink-4)' }}>Cerrado</span>
              }
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
