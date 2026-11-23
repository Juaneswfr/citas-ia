// Los degradés de los gráficos de Zumit Manager, definidos una sola vez por pantalla.

import { COLOR, gradientId, mix, type ColorKey } from './palette';
import styles from './Charts.module.css';

/**
 * Los degradés, definidos UNA vez por pantalla en un SVG invisible. Todos los gráficos los referencian por id
 * (`url(#zg-plum-v)`), así no se repiten ni chocan los ids entre gráficos.
 */
export function GradientDefs() {
  return (
    <svg width="0" height="0" aria-hidden="true" focusable="false" className={styles.defs}>
      <defs>
        {(Object.keys(COLOR) as ColorKey[]).flatMap((key) => {
          const light = mix(COLOR[key], '#ffffff', 0.2);
          const dark = mix(COLOR[key], '#000000', 0.14);
          return [
            <linearGradient key={`${key}-v`} id={gradientId(key, 'v')} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={light} />
              <stop offset="100%" stopColor={dark} />
            </linearGradient>,
            <linearGradient key={`${key}-h`} id={gradientId(key, 'h')} x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor={dark} />
              <stop offset="100%" stopColor={light} />
            </linearGradient>,
          ];
        })}
      </defs>
    </svg>
  );
}
