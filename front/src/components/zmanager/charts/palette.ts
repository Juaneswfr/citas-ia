// Colores de los gráficos de Zumit Manager. Todos pasaron `validate_palette` (banda de luminosidad, piso de cromaticidad,
// separación para daltonismo y contraste sobre superficie blanca); la app no tiene modo oscuro.
//
//   Planes (identidad)   ciruela #9A3A63 · turquesa profundo #00959E   (la marca: borgoña y turquesa; separación daltonismo ΔE 11,6)
//   Estados              activa #2E9B63 · en prueba #3A6FD6 · en mora #C48A12 · pausada #CC4B37
//   Lo bueno / lo malo   verde de «activa» · rojo de «pausada» (margen que gana / pierde)
//
// Notas de la validación: el ámbar de «en mora» queda a 2,93:1 del fondo (< 3:1): la guía exige relevo, que es el
// tooltip, la leyenda con nombre y la vista en tabla de cada gráfico. «Cancelada» no es un segmento (no es un negocio
// vivo): se muestra como número. El color sigue a la entidad, nunca a su posición.
//
// El degradé es siempre de UN solo tono (más claro → más oscuro): nunca mezcla dos colores.

export type ColorKey = 'plum' | 'teal' | 'good' | 'info' | 'warn' | 'bad' | 'muted';

export const COLOR: Record<ColorKey, string> = {
  plum: '#9A3A63',
  teal: '#00959E',
  good: '#2E9B63',
  info: '#3A6FD6',
  warn: '#C48A12',
  bad: '#CC4B37',
  muted: '#8E929C',
};

/** Estado de suscripción → color. */
export const STATUS_COLOR = { active: 'good', trial: 'info', past_due: 'warn', paused: 'bad' } as const;

export const STATUS_LABEL = { active: 'Activa', trial: 'En prueba', past_due: 'En mora', paused: 'Pausada' } as const;

/** El color de un plan sale de su código: no cambia si otro plan se filtra o se reordena. */
export function planColor(code: string | null | undefined): ColorKey {
  if (code === 'emprendedor') return 'plum';
  if (code === 'equipo') return 'teal';
  return 'muted';
}

/** Mezcla un color con blanco o negro (t de 0 a 1), conservando el tono. */
export function mix(hex: string, target: '#ffffff' | '#000000', t: number): string {
  const n = (h: string, i: number) => parseInt(h.slice(1 + i * 2, 3 + i * 2), 16);
  const to = target === '#ffffff' ? 255 : 0;
  const channel = (i: number) => Math.round(n(hex, i) + (to - n(hex, i)) * t).toString(16).padStart(2, '0');
  return `#${channel(0)}${channel(1)}${channel(2)}`;
}

/** Id del degradé de un color. `v` = de arriba a abajo (columnas), `h` = de izquierda a derecha (barras horizontales). */
export const gradientId = (key: ColorKey, dir: 'v' | 'h' = 'v') => `zg-${key}-${dir}`;
export const gradientFill = (key: ColorKey, dir: 'v' | 'h' = 'v') => `url(#${gradientId(key, dir)})`;

/** Tinta de texto y cuadrícula de los ejes (los mismos valores que --ink-* y --line de la app). */
export const INK = { strong: '#1C1D22', mid: '#565A64', soft: '#8E929C' } as const;
export const GRID = '#E9EAEE';
/** El fondo de las tarjetas: el «espacio» de 2 px que separa segmentos apilados. */
export const SURFACE = '#FFFFFF';
