// Responsabilidad: dar formato a los logs de los servicios: una línea completa
// por emisión, con prefijo [nombre] con padding y color ANSI opcional.

const RESET = '\x1b[0m';
const SYSTEM_NAME = 'dev';
/** Ancho de prefijo mínimo (nombre más largo de servicio). */
let prefixWidth = 'frontend'.length;

/**
 * Indica si se debe usar color por defecto.
 * @returns {boolean}
 */
export function defaultUseColor() {
  return !process.env.NO_COLOR && Boolean(process.stdout.isTTY);
}

/**
 * Ajusta el ancho del prefijo al nombre más largo.
 * @param {string[]} names
 */
export function setPrefixWidth(names) {
  prefixWidth = Math.max(SYSTEM_NAME.length, ...names.map((n) => n.length));
}

/**
 * @param {string} name
 * @param {number|undefined} color
 * @param {boolean} useColor
 * @returns {string}
 */
function formatPrefix(name, color, useColor) {
  const text = `[${name}]`.padEnd(prefixWidth + 2);
  return useColor && color !== undefined ? `\x1b[${color}m${text}${RESET}` : text;
}

/**
 * Crea un logger de líneas para un stream de un servicio.
 * @param {{name: string, color?: number, write: (line: string) => void, useColor?: boolean}} options
 * @returns {{push: (chunk: string|Buffer) => void, flush: () => void}}
 */
export function createLineLogger({ name, color, write, useColor = defaultUseColor() }) {
  let buffer = '';
  const emit = (line) => write(`${formatPrefix(name, color, useColor)} ${line}\n`);

  return {
    push(chunk) {
      buffer += chunk.toString();
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';
      for (const line of lines) emit(line.replace(/\r$/, ''));
    },
    flush() {
      if (buffer.length > 0) emit(buffer);
      buffer = '';
    },
  };
}

/**
 * Logger para mensajes del propio orquestador (prefijo [dev]).
 * @param {(line: string) => void} write
 * @param {boolean} [useColor]
 * @returns {(message: string) => void}
 */
export function createSystemLogger(write, useColor = defaultUseColor()) {
  return (message) => {
    for (const line of String(message).split('\n')) {
      write(`${formatPrefix(SYSTEM_NAME, 90, useColor)} ${line}\n`);
    }
  };
}
