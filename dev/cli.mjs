#!/usr/bin/env node
// Responsabilidad: punto de entrada y única composición del orquestador.
// Parsea --all, valida configuración y preflight, arranca servicios, monitor de
// salud y dashboard, gestiona señales y fija el código de salida.

import { loadServices } from './services.mjs';
import { runPreflight } from './preflight.mjs';
import { createSupervisor } from './supervisor.mjs';
import { createHealthMonitor } from './health.mjs';
import { createDashboard } from './dashboard.mjs';
import { createLineLogger, createSystemLogger, setPrefixWidth } from './logger.mjs';

const all = process.argv.includes('--all');
const write = (line) => process.stdout.write(line);
const sys = createSystemLogger(write);

let config;
try {
  config = loadServices(process.env);
} catch (err) {
  sys(`Configuración inválida: ${err.message}`);
  process.exit(1);
}

setPrefixWidth(config.services.map((s) => s.name));

/** Primer evento de salida inesperado (fallo de un servicio). */
let failure = null;

const supervisor = createSupervisor({
  services: config.services,
  all,
  logger: (service) => createLineLogger({ name: service.name, color: service.color, write }),
  onExit: (event) => {
    sys(event.message);
    if (!event.expected && !failure) failure = event;
  },
});

const problems = runPreflight({ services: supervisor.included });
if (problems.length > 0) {
  for (const problem of problems) sys(`✗ ${problem}`);
  process.exit(1);
}

const monitor = createHealthMonitor({
  services: config.services,
  included: supervisor.included.map((s) => s.name),
});
const dashboard = createDashboard({
  getStatuses: monitor.getStatuses,
  port: config.dashboardPort,
});
let dashboardServer = null;

sys(
  `Iniciando: ${supervisor.included.map((s) => `${s.name}:${s.port}`).join(', ')} ` +
    `(dashboard http://127.0.0.1:${config.dashboardPort})`,
);
supervisor.start();
monitor.start();
dashboard
  .listen()
  .then((server) => {
    dashboardServer = server;
    if (supervisor.getState() === 'exited') server.close();
  })
  .catch((err) => sys(`Dashboard no disponible: ${err.message} Los servicios siguen en marcha.`));

let interrupts = 0;
for (const signal of ['SIGINT', 'SIGTERM', 'SIGHUP']) {
  process.on(signal, () => {
    interrupts += 1;
    if (signal === 'SIGINT' && interrupts > 1) {
      sys('Segunda interrupción: forzando salida (SIGKILL).');
      supervisor.shutdown({ force: true });
      return;
    }
    if (interrupts === 1) sys(`Recibido ${signal}: deteniendo servicios…`);
    supervisor.shutdown();
  });
}

supervisor.done.then(async () => {
  monitor.stop();
  if (dashboardServer) {
    dashboardServer.closeAllConnections?.();
    await new Promise((resolve) => dashboardServer.close(resolve));
  }
  // 0 solo si el apagado lo pidió el usuario; si no, código del servicio o 1.
  const code = failure ? (failure.code !== null && failure.code !== 0 ? failure.code : 1) : 0;
  process.exit(code);
});
