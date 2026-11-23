// Movimiento de los gráficos: respeta «reducir movimiento» del sistema y cuenta los números hacia arriba al cargar.

import { useEffect, useRef, useState } from 'react';
import { easeOutCubic } from './scale';

const QUERY = '(prefers-reduced-motion: reduce)';

/** true si la persona pidió menos movimiento. En el servidor (sin ventana) no hay animación. */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() => (typeof window === 'undefined' ? true : window.matchMedia(QUERY).matches));
  useEffect(() => {
    const media = window.matchMedia(QUERY);
    const onChange = () => setReduced(media.matches);
    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  }, []);
  return reduced;
}

/**
 * El valor que se dibuja mientras `target` se cuenta desde el valor anterior (o desde 0 la primera vez).
 * Con «reducir movimiento» salta directo al valor final.
 */
export function useCountUp(target: number, durationMs = 900): number {
  const reduced = usePrefersReducedMotion();
  const [value, setValue] = useState(reduced ? target : 0);
  const from = useRef(reduced ? target : 0);

  useEffect(() => {
    if (reduced || !Number.isFinite(target)) {
      setValue(target);
      from.current = target;
      return;
    }
    const start = performance.now();
    const origin = from.current;
    let frame = 0;
    const tick = (now: number) => {
      const t = (now - start) / durationMs;
      const next = origin + (target - origin) * easeOutCubic(t);
      setValue(next);
      if (t < 1) frame = requestAnimationFrame(tick);
      else from.current = target;
    };
    frame = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(frame);
      from.current = target; // si se interrumpe, el siguiente conteo parte del valor nuevo, no salta hacia atrás
    };
  }, [target, durationMs, reduced]);

  return value;
}
