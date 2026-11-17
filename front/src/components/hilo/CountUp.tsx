import { useEffect, useRef, useState } from 'react';

interface CountUpProps {
  value: number;
  /** Cómo se escribe el número mientras cuenta (por defecto, entero). */
  format?: (n: number) => string;
  duration?: number;
}

const whole = (n: number) => String(Math.round(n));

/** Número que sube hasta su valor con un frenado suave. Si cambia, parte desde donde estaba. */
export function CountUp({ value, format = whole, duration = 700 }: CountUpProps) {
  const [shown, setShown] = useState(0);
  const from = useRef(0);

  useEffect(() => {
    // Con «reducir movimiento» se muestra el valor final de una vez.
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      from.current = value;
      setShown(value);
      return;
    }
    const origin = from.current;
    const start = performance.now();
    let frame = 0;
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / duration);
      const current = origin + (value - origin) * (1 - Math.pow(1 - progress, 3));
      from.current = current;
      setShown(current);
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value, duration]);

  return <span className="tnum">{format(shown)}</span>;
}
