import { useCallback, useSyncExternalStore } from 'react';

/**
 * true cuando la ventana es más angosta que `breakpoint`.
 * Reacciona a cambios de tamaño y a girar el teléfono. En el servidor devuelve
 * false y se corrige al hidratar, sin errores de hidratación.
 */
export function useIsMobile(breakpoint = 880): boolean {
  const query = `(max-width: ${breakpoint - 1}px)`;

  const subscribe = useCallback(
    (onChange: () => void) => {
      const mql = window.matchMedia(query);
      mql.addEventListener('change', onChange);
      return () => mql.removeEventListener('change', onChange);
    },
    [query],
  );

  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(query).matches,
    () => false,
  );
}
