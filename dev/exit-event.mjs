// Responsabilidad: lógica pura que convierte la salida de un proceso hijo
// (código o señal) en un evento de salida estructurado y legible.

/**
 * @typedef {Object} ExitEvent
 * @property {string} service
 * @property {number|null} code
 * @property {string|null} signal Exactamente uno de code/signal no es nulo.
 * @property {boolean} expected `true` si ocurrió durante un apagado solicitado.
 * @property {string} message Descripción en español.
 */

/**
 * Crea un evento de salida.
 * @param {{service: string, code: number|null, signal: string|null, shuttingDown: boolean}} input
 * @returns {ExitEvent}
 */
export function createExitEvent({ service, code, signal, shuttingDown }) {
  const bySignal = signal !== null && signal !== undefined;
  return {
    service,
    code: bySignal ? null : code,
    signal: bySignal ? signal : null,
    expected: Boolean(shuttingDown),
    message: bySignal
      ? `${service} terminó por señal ${signal}`
      : `${service} terminó con código ${code}`,
  };
}
