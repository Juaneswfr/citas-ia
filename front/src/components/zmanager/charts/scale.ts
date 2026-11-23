// Formato de los ejes y de los valores de los gráficos. Todo puro (sin React) para poder probarlo aparte.

/** 1.250.000 → «1,3 M»; 125.000 → «125 K»; por debajo de 10.000 va completo (una sola forma por eje). */
export function compact(n: number): string {
  const abs = Math.abs(n);
  if (abs < 10_000) return n.toLocaleString('es-CO', { maximumFractionDigits: 1 });
  if (abs < 1_000_000) return `${Math.round(n / 1_000).toLocaleString('es-CO')} K`;
  return `${(n / 1_000_000).toLocaleString('es-CO', { maximumFractionDigits: 1 })} M`;
}

/** Pesos para un eje: «$125 K». */
export const compactCop = (n: number): string => `${n < 0 ? '-' : ''}$${compact(Math.abs(n))}`;

/** Pesos completos: «$1.250.000». */
export const fullCop = (n: number): string => `${n < 0 ? '-' : ''}$${Math.abs(Math.round(n)).toLocaleString('es-CO')}`;

export const percent = (n: number): string => `${n.toLocaleString('es-CO', { maximumFractionDigits: 1 })}%`;

/** Un número entero con separador de miles. */
export const integer = (n: number): string => Math.round(n).toLocaleString('es-CO');

/** Dónde está el máximo (índice del primer máximo), o -1 si no hay nada o todo es cero. */
export function indexOfMax(values: number[]): number {
  let best = -1;
  let bestValue = 0;
  values.forEach((v, i) => {
    if (v > bestValue) {
      bestValue = v;
      best = i;
    }
  });
  return best;
}

/** De 0 a 1: cuánto del recorrido de una animación ya pasó (salida suave: arranca rápido y frena). */
export function easeOutCubic(t: number): number {
  const c = Math.min(1, Math.max(0, t));
  return 1 - Math.pow(1 - c, 3);
}
