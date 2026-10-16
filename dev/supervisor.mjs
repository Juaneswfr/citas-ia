// Responsabilidad: lanzar los servicios como grupos de procesos independientes,
// reenviar su salida al logger, detectar su caída (cascada) y apagarlos de
// forma limpia (SIGTERM al grupo, gracia, luego SIGKILL).
//
// Las dependencias (spawn, kill, logger, onExit, gracia) se inyectan para poder
// probarlo con procesos triviales sin tocar los servicios reales.

import { spawn as nodeSpawn } from 'node:child_process';
import { createExitEvent } from './exit-event.mjs';

/** @typedef {import('./services.mjs').ServiceDefinition} ServiceDefinition */
/** @typedef {import('./exit-event.mjs').ExitEvent} ExitEvent */
/** @typedef {'starting'|'running'|'shutting-down'|'exited'} SupervisorState */

/** Envía una señal al grupo de procesos cuyo líder es `pid`. */
const killGroup = (pid, signal) => process.kill(-pid, signal);

/** Espera máxima a que los streams de un hijo terminen tras su 'exit'. */
const DRAIN_TIMEOUT_MS = 300;

/**
 * Crea el supervisor.
 * @param {Object} options
 * @param {ServiceDefinition[]} options.services Todos los servicios conocidos.
 * @param {boolean} [options.all=false] Incluir también los servicios opcionales.
 * @param {typeof nodeSpawn} [options.spawn]
 * @param {(pid: number, signal: string) => void} [options.kill] Mata el grupo de `pid`.
 * @param {(service: ServiceDefinition) => {push: (chunk: string) => void, flush: () => void}} options.logger
 *   Fábrica de loggers de línea; se invoca una vez por stream (stdout/stderr).
 * @param {(event: ExitEvent) => void} [options.onExit] Notificado en cada salida de un servicio.
 * @param {number} [options.graceMs=5000] Gracia entre SIGTERM y SIGKILL.
 * @returns {{
 *   start: () => void,
 *   shutdown: (opts?: {force?: boolean}) => Promise<void>,
 *   done: Promise<void>,
 *   included: ServiceDefinition[],
 *   getState: () => SupervisorState,
 * }}
 */
export function createSupervisor({
  services,
  all = false,
  spawn = nodeSpawn,
  kill = killGroup,
  logger,
  onExit = () => {},
  graceMs = 5000,
}) {
  const included = services.filter((s) => all || !s.optional);
  /** @type {Map<string, {pid: number|undefined, exited: boolean}>} */
  const children = new Map();
  /** @type {SupervisorState} */
  let state = 'starting';
  let graceTimer = null;
  let termTimer = null;
  let resolveDone;
  const done = new Promise((resolve) => {
    resolveDone = resolve;
  });

  /** Envía la señal al grupo ignorando "ya no existe" (ESRCH). */
  function safeKill(pid, signal) {
    if (pid === undefined) return;
    try {
      kill(pid, signal);
    } catch (err) {
      if (err?.code !== 'ESRCH') throw err;
    }
  }

  function signalLive(signal) {
    for (const entry of children.values()) {
      if (!entry.exited) safeKill(entry.pid, signal);
    }
  }

  function checkAllExited() {
    if (state === 'exited') return;
    for (const entry of children.values()) if (!entry.exited) return;
    if (children.size === 0 && state === 'starting') return;
    state = 'exited';
    if (graceTimer) clearTimeout(graceTimer);
    if (termTimer) clearTimeout(termTimer);
    resolveDone();
  }

  /**
   * @param {ServiceDefinition} service
   * @param {number|null} code
   * @param {string|null} signal
   */
  function handleExit(service, code, signal) {
    const entry = children.get(service.name);
    if (!entry || entry.exited) return;
    entry.exited = true;
    // Limpia posibles nietos solo si la salida no fue limpia o ya se está
    // apagando; una salida normal no necesita matar el grupo.
    if (state === 'shutting-down' || code !== 0 || signal) safeKill(entry.pid, 'SIGTERM');

    const event = createExitEvent({
      service: service.name,
      code,
      signal,
      shuttingDown: state === 'shutting-down',
    });
    onExit(event);
    // El primer evento inesperado gana: inicia el apagado de los demás.
    // La cascada espera un poco antes de señalar, para que los demás servicios
    // terminen de emitir su salida pendiente.
    if (!event.expected && state !== 'shutting-down') shutdown({ delayMs: DRAIN_TIMEOUT_MS });
    checkAllExited();
  }

  function launch(service) {
    const child = spawn(service.command, service.args, {
      cwd: service.cwd,
      detached: true,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: process.env,
    });
    children.set(service.name, { pid: child.pid, exited: false });

    // 'exit' puede llegar antes de drenar stdout/stderr: se espera a que los
    // streams terminen (con tope) para no perder el último chunk de salida.
    let pendingStreams = 0;
    let onDrained = null;
    for (const stream of [child.stdout, child.stderr]) {
      if (!stream) continue;
      const lineLogger = logger(service);
      pendingStreams++;
      stream.setEncoding?.('utf8');
      stream.on('data', (chunk) => lineLogger.push(chunk));
      stream.on('end', () => {
        lineLogger.flush();
        if (--pendingStreams === 0) onDrained?.();
      });
    }
    child.on('error', () => handleExit(service, 127, null)); // p. ej. ENOENT
    child.on('exit', (code, signal) => {
      if (pendingStreams === 0) return handleExit(service, code, signal);
      let finished = false;
      const finish = () => {
        if (finished) return;
        finished = true;
        clearTimeout(timer);
        handleExit(service, code, signal);
      };
      const timer = setTimeout(finish, DRAIN_TIMEOUT_MS);
      onDrained = finish;
    });
  }

  function start() {
    if (state !== 'starting') return;
    for (const service of included) launch(service);
    state = 'running';
    checkAllExited();
  }

  /**
   * Apaga todos los servicios. Idempotente; `force` escala a SIGKILL inmediato.
   * `delayMs` retrasa el SIGTERM (paradas en cascada) para que drene la salida.
   * @param {{force?: boolean, delayMs?: number}} [opts]
   * @returns {Promise<void>} Resuelve cuando todos los hijos han salido.
   */
  function shutdown({ force = false, delayMs = 0 } = {}) {
    if (state === 'exited') return done;
    const sendTerm = () => {
      termTimer = null;
      signalLive('SIGTERM');
      graceTimer = setTimeout(() => signalLive('SIGKILL'), graceMs);
      graceTimer.unref?.();
    };
    if (state !== 'shutting-down') {
      state = 'shutting-down';
      if (force) {
        signalLive('SIGKILL');
      } else if (delayMs > 0) {
        termTimer = setTimeout(sendTerm, delayMs);
      } else {
        sendTerm();
      }
    } else if (force) {
      if (termTimer) clearTimeout(termTimer);
      termTimer = null;
      signalLive('SIGKILL');
    }
    checkAllExited();
    return done;
  }

  return { start, shutdown, done, included, getState: () => state };
}
