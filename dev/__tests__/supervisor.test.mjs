import test from 'node:test';
import assert from 'node:assert/strict';
import { createSupervisor } from '../supervisor.mjs';

const svc = (name, script, extra = {}) => ({
  name,
  port: 1,
  color: 36,
  command: process.execPath,
  args: ['-e', script],
  cwd: process.cwd(),
  optional: false,
  ...extra,
});

/** Logger de prueba: acumula líneas por servicio. */
function makeLogger() {
  const lines = [];
  const logger = (service) => {
    let buf = '';
    return {
      push(chunk) {
        buf += chunk;
        const parts = buf.split('\n');
        buf = parts.pop();
        for (const l of parts) lines.push(`[${service.name}] ${l}`);
      },
      flush() {
        if (buf) lines.push(`[${service.name}] ${buf}`);
        buf = '';
      },
    };
  };
  return { lines, logger };
}

const alive = (pid) => {
  try {
    process.kill(pid, 0);
    return true;
  } catch (err) {
    return err.code !== 'ESRCH';
  }
};

async function waitFor(fn, ms = 5000) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    if (await fn()) return true;
    await new Promise((r) => setTimeout(r, 25));
  }
  return false;
}

test('start: servicios en paralelo con salida prefijada (incluye chunk partido)', async () => {
  const { lines, logger } = makeLogger();
  const sup = createSupervisor({
    services: [
      svc('frontend', "process.stdout.write('hola '); setTimeout(()=>process.stdout.write('mundo\\n'),50)"),
      svc('backend', "console.log('listo')"),
    ],
    logger,
  });
  sup.start();
  await sup.done;
  assert.ok(lines.includes('[frontend] hola mundo'));
  assert.ok(lines.includes('[backend] listo'));
});

test('start: el servicio opcional no se lanza si no se incluye', async () => {
  const { lines, logger } = makeLogger();
  const services = [
    svc('backend', "console.log('b')"),
    svc('agent', "console.log('a')", { optional: true }),
  ];
  const sup = createSupervisor({ services, logger });
  sup.start();
  await sup.done;
  assert.deepEqual(sup.included.map((s) => s.name), ['backend']);
  assert.ok(!lines.some((l) => l.startsWith('[agent]')));

  const sup2 = createSupervisor({ services, all: true, logger: makeLogger().logger });
  assert.deepEqual(sup2.included.map((s) => s.name), ['backend', 'agent']);
});

test('cascada: un hijo sale con código 1 → evento y parada de los demás', async () => {
  const events = [];
  const sup = createSupervisor({
    services: [
      svc('backend', 'setTimeout(()=>process.exit(1),100)'),
      svc('frontend', 'setInterval(()=>{},1000)'),
    ],
    logger: makeLogger().logger,
    onExit: (e) => events.push(e),
  });
  sup.start();
  await sup.done;
  const first = events[0];
  assert.equal(first.service, 'backend');
  assert.equal(first.code, 1);
  assert.equal(first.expected, false);
  const other = events.find((e) => e.service === 'frontend');
  assert.equal(other.expected, true);
});

test('salida por señal → mensaje con la señal', async () => {
  const events = [];
  const sup = createSupervisor({
    services: [svc('agent', "process.kill(process.pid,'SIGKILL')")],
    logger: makeLogger().logger,
    onExit: (e) => events.push(e),
  });
  sup.start();
  await sup.done;
  assert.equal(events[0].signal, 'SIGKILL');
  assert.match(events[0].message, /agent terminó por señal SIGKILL/);
});

test('salida con código 0 inesperada también es un fallo', async () => {
  const events = [];
  const sup = createSupervisor({
    services: [svc('backend', 'process.exit(0)'), svc('frontend', 'setInterval(()=>{},1000)')],
    logger: makeLogger().logger,
    onExit: (e) => events.push(e),
  });
  sup.start();
  await sup.done;
  assert.equal(events[0].service, 'backend');
  assert.equal(events[0].expected, false);
});

test('dos salidas simultáneas → un solo apagado (idempotencia)', async () => {
  const kills = [];
  const events = [];
  const sup = createSupervisor({
    services: [
      svc('a', 'setTimeout(()=>process.exit(2),100)'),
      svc('b', 'setTimeout(()=>process.exit(3),100)'),
      svc('c', 'setInterval(()=>{},1000)'),
    ],
    logger: makeLogger().logger,
    kill: (pid, sig) => {
      kills.push([pid, sig]);
      process.kill(-pid, sig);
    },
    onExit: (e) => events.push(e),
  });
  sup.start();
  await sup.done;
  const unexpected = events.filter((e) => !e.expected);
  assert.ok(unexpected.length >= 1);
  // Cada hijo recibe SIGTERM de apagado como mucho una vez desde shutdown().
  const termsToC = kills.filter(([, sig]) => sig === 'SIGTERM');
  assert.ok(termsToC.length <= 6); // shutdown (≤3) + limpieza por salida (≤3)
  assert.equal(sup.getState(), 'exited');
});

test('shutdown mata hijo y nieto (kill de grupo)', async () => {
  const grandchildScript =
    "const {spawn}=require('node:child_process');" +
    "const g=spawn(process.execPath,['-e','setInterval(()=>{},1000)'],{stdio:'ignore'});" +
    'console.log(g.pid); setInterval(()=>{},1000)';
  const { lines, logger } = makeLogger();
  const sup = createSupervisor({ services: [svc('svc', grandchildScript)], logger });
  sup.start();
  assert.ok(await waitFor(() => lines.length > 0));
  const grandchildPid = Number(lines[0].split(' ')[1]);
  assert.ok(alive(grandchildPid));
  await sup.shutdown();
  assert.ok(await waitFor(() => !alive(grandchildPid), 3000));
});

test('un hijo que ignora SIGTERM es matado con SIGKILL tras la gracia', async () => {
  const events = [];
  const sup = createSupervisor({
    services: [svc('stubborn', "process.on('SIGTERM',()=>{}); setInterval(()=>{},1000)")],
    logger: makeLogger().logger,
    graceMs: 300,
    onExit: (e) => events.push(e),
  });
  sup.start();
  await new Promise((r) => setTimeout(r, 400));
  const t0 = Date.now();
  await sup.shutdown();
  assert.ok(Date.now() - t0 >= 250);
  assert.equal(events[0].signal, 'SIGKILL');
});

test('shutdown({force:true}) mata de inmediato', async () => {
  const events = [];
  const sup = createSupervisor({
    services: [svc('stubborn', "process.on('SIGTERM',()=>{}); setInterval(()=>{},1000)")],
    logger: makeLogger().logger,
    graceMs: 60000,
    onExit: (e) => events.push(e),
  });
  sup.start();
  await new Promise((r) => setTimeout(r, 400));
  const t0 = Date.now();
  await sup.shutdown({ force: true });
  assert.ok(Date.now() - t0 < 3000);
  assert.equal(events[0].signal, 'SIGKILL');
});

test('llamar shutdown() dos veces no duplica kills', async () => {
  const kills = [];
  const sup = createSupervisor({
    services: [svc('a', 'setInterval(()=>{},1000)')],
    logger: makeLogger().logger,
    kill: (pid, sig) => {
      kills.push(sig);
      process.kill(-pid, sig);
    },
  });
  sup.start();
  await new Promise((r) => setTimeout(r, 300));
  const p1 = sup.shutdown();
  const termsAfterFirst = kills.filter((s) => s === 'SIGTERM').length;
  const p2 = sup.shutdown();
  assert.equal(kills.filter((s) => s === 'SIGTERM').length, termsAfterFirst);
  await Promise.all([p1, p2]);
});
