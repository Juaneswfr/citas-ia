// Responsabilidad: comprobar si cada servicio acepta conexiones TCP y mantener
// una caché del último estado. Un check lento o fallido nunca rechaza ni
// bloquea la lectura de estados.

import net from 'node:net';

/**
 * @typedef {Object} ServiceStatus
 * @property {string} name
 * @property {number} port
 * @property {'up'|'down'|'not-included'} state
 * @property {string} checkedAt ISO-8601.
 */

/**
 * Intenta una conexión TCP a 127.0.0.1:port.
 * @param {number} port
 * @param {{timeoutMs?: number, connect?: typeof net.connect}} [options]
 * @returns {Promise<boolean>} `true` si conectó; `false` en error o timeout.
 */
export function checkPort(port, { timeoutMs = 1000, connect = net.connect } = {}) {
  return new Promise((resolve) => {
    let settled = false;
    let socket;
    let timer;
    const finish = (ok) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      try {
        socket?.destroy?.();
      } catch {
        /* ignorar */
      }
      resolve(ok);
    };
    timer = setTimeout(() => finish(false), timeoutMs);
    try {
      socket = connect({ port, host: '127.0.0.1' });
      socket.once('connect', () => finish(true));
      socket.once('error', () => finish(false));
    } catch {
      finish(false);
    }
  });
}

/**
 * Monitor periódico de salud.
 * @param {Object} options
 * @param {{name: string, port: number}[]} options.services Todos los servicios.
 * @param {string[]} options.included Nombres de los servicios lanzados.
 * @param {number} [options.intervalMs=2000]
 * @param {() => Date} [options.now]
 * @param {typeof checkPort} [options.checkPort]
 * @returns {{start: () => void, stop: () => void, getStatuses: () => ServiceStatus[]}}
 */
export function createHealthMonitor({
  services,
  included,
  intervalMs = 2000,
  now = () => new Date(),
  checkPort: check = checkPort,
}) {
  const includedSet = new Set(included);
  /** @type {Map<string, ServiceStatus>} */
  const cache = new Map();
  for (const s of services) {
    cache.set(s.name, {
      name: s.name,
      port: s.port,
      state: includedSet.has(s.name) ? 'down' : 'not-included',
      checkedAt: now().toISOString(),
    });
  }

  let timer = null;
  let polling = false;

  async function poll() {
    if (polling) return;
    polling = true;
    try {
      await Promise.all(
        services
          .filter((s) => includedSet.has(s.name))
          .map(async (s) => {
            let up = false;
            try {
              up = await check(s.port);
            } catch {
              up = false;
            }
            cache.set(s.name, {
              name: s.name,
              port: s.port,
              state: up ? 'up' : 'down',
              checkedAt: now().toISOString(),
            });
          }),
      );
    } finally {
      polling = false;
    }
  }

  return {
    start() {
      if (timer) return;
      poll();
      timer = setInterval(poll, intervalMs);
      timer.unref?.();
    },
    stop() {
      if (timer) clearInterval(timer);
      timer = null;
    },
    getStatuses() {
      return [...cache.values()].map((s) => ({ ...s }));
    },
  };
}
