import { Icon } from '@/components/hilo/icons';
import s from './onboarding.module.css';

export function StepTest() {
  return (
    <div className={s['test__chat']}>
      <div className={`${s['test__bubble']} ${s['test__bubble--incoming']}`}>
        Hola! Quiero un corte para mañana
      </div>
      <div className={`${s['test__bubble']} ${s['test__bubble--outgoing']}`}>
        Para mañana tengo con Andrés a las 10:00, 11:30 o 4:00 pm. ¿Cuál prefieres?
      </div>
      <div className={`${s['test__bubble']} ${s['test__bubble--outgoing']}`}>
        <Icon name="checkCircle" size={16} /> Cita creada en Google Calendar.
      </div>
    </div>
  );
}
