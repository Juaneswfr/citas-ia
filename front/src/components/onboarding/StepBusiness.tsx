import { useState } from 'react';
import { Icon } from '@/components/hilo/icons';
import { BUSINESS_TYPES, type BusinessTypeId } from '@/lib/hilo-data';
import type { BusinessHoursOut } from '@/lib/types/api';
import s from './onboarding.module.css';

const DAY_LABELS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];

interface StepBusinessProps {
  businessType: BusinessTypeId | null;
  setBusinessType: (t: BusinessTypeId) => void;
  businessName: string;
  setBusinessName: (n: string) => void;
  city: string;
  setCity: (c: string) => void;
  businessHours: BusinessHoursOut[];
  onHoursChange: (hours: BusinessHoursOut[]) => void;
}

export function StepBusiness({
  businessType, setBusinessType, businessName, setBusinessName, city, setCity,
  businessHours, onHoursChange,
}: StepBusinessProps) {
  const [tone, setTone] = useState(0);

  function patchHour(dayOfWeek: number, patch: Partial<BusinessHoursOut>) {
    const next = businessHours.map(h =>
      h.day_of_week === dayOfWeek ? { ...h, ...patch } : h
    );
    onHoursChange(next);
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div className={s['business__fields']}>
        <label className={s['business__label']}>
          <span className={s['business__label-text']}>Nombre del negocio</span>
          <input
            className={s['business__input']}
            value={businessName}
            onChange={e => setBusinessName(e.target.value)}
            placeholder="ej: Barbería El Patrón"
          />
        </label>
        <label className={s['business__label']}>
          <span className={s['business__label-text']}>Ciudad / zona</span>
          <input
            className={s['business__input']}
            value={city}
            onChange={e => setCity(e.target.value)}
            placeholder="ej: Medellín · El Poblado"
          />
        </label>
      </div>

      <div>
        <span className={s['business__label-text']} style={{ display: 'block', marginBottom: 10 }}>
          Tipo de negocio <span className={s['business__label-required']}>*</span>
        </span>
        <div className={s['business__type-grid']}>
          {BUSINESS_TYPES.map(bt => {
            const sel = businessType === bt.id;
            return (
              <button
                key={bt.id}
                onClick={() => setBusinessType(bt.id)}
                className={`${s['business__type-btn']} ${sel ? s['business__type-btn--selected'] : ''}`}
              >
                <Icon name={bt.icon} size={22} strokeWidth={sel ? 2 : 1.6} />
                {bt.label}
              </button>
            );
          })}
        </div>
        {!businessType && (
          <p className={s['business__type-hint']}>Selecciona el tipo de negocio para continuar.</p>
        )}
      </div>

      <label className={s['business__label']}>
        <span className={s['business__label-text']}>Tono del agente</span>
        <div className={s['business__tone-row']}>
          {['Cercano', 'Neutral', 'Formal'].map((t, i) => (
            <span
              key={t}
              role="button"
              tabIndex={0}
              onClick={() => setTone(i)}
              onKeyDown={e => e.key === 'Enter' && setTone(i)}
              className={`${s['business__tone-btn']} ${i === tone ? s['business__tone-btn--selected'] : ''}`}
            >
              {t}
            </span>
          ))}
        </div>
      </label>

      {businessHours.length > 0 && (
        <div>
          <span className={s['business__label-text']} style={{ display: 'block', marginBottom: 10 }}>
            Horario de atención
          </span>
          <div className={s['business__hours-section']}>
            {businessHours.map(h => (
              <div
                key={h.day_of_week}
                className={`${s['business__hours-row']} ${!h.is_open ? s['business__hours-row--closed'] : ''}`}
              >
                <span className={s['business__hours-day']}>{DAY_LABELS[h.day_of_week]}</span>
                <input
                  type="checkbox"
                  className={s['business__hours-toggle']}
                  checked={h.is_open}
                  onChange={e => patchHour(h.day_of_week, { is_open: e.target.checked })}
                />
                {h.is_open ? (
                  <div className={s['business__hours-time']}>
                    <input
                      type="time"
                      className={s['business__hours-input']}
                      value={h.open_time}
                      onChange={e => patchHour(h.day_of_week, { open_time: e.target.value })}
                    />
                    <span className={s['business__hours-sep']}>—</span>
                    <input
                      type="time"
                      className={s['business__hours-input']}
                      value={h.close_time}
                      onChange={e => patchHour(h.day_of_week, { close_time: e.target.value })}
                    />
                  </div>
                ) : (
                  <span className={s['business__hours-closed-label']}>Cerrado</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
