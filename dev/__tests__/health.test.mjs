import test from 'node:test';
import assert from 'node:assert/strict';
import net from 'node:net';
import { EventEmitter } from 'node:events';
import { checkPort, createHealthMonitor } from '../health.mjs';

function listen() {
  return new Promise((resolve) => {
    const server = net.createServer((s) => s.destroy());
    server.listen(0, '127.0.0.1', () => resolve(server));
  });
}

test('checkPort: up con servidor y down tras cerrarlo', async () => {
  const server = await listen();
  const { port } = server.address();
  assert.equal(await checkPort(port), true);
  await new Promise((r) => server.close(r));
  assert.equal(await checkPort(port), false);
});

test('checkPort: respeta el timeout con connect que nunca responde', async () => {
  const connect = () => Object.assign(new EventEmitter(), { destroy() {} });
  const t0 = Date.now();
  assert.equal(await checkPort(1, { timeoutMs: 100, connect }), false);
  assert.ok(Date.now() - t0 < 1000);
});

test('monitor: not-included para el servicio excluido; up/down para los incluidos', async () => {
  const server = await listen();
  const { port } = server.address();
  const monitor = createHealthMonitor({
    services: [
      { name: 'frontend', port },
      { name: 'agent', port: port + 1 },
    ],
    included: ['frontend'],
    intervalMs: 50,
  });
  monitor.start();
  await new Promise((r) => setTimeout(r, 300));
  const byName = Object.fromEntries(monitor.getStatuses().map((s) => [s.name, s]));
  assert.equal(byName.frontend.state, 'up');
  assert.equal(byName.agent.state, 'not-included');
  assert.ok(!Number.isNaN(Date.parse(byName.frontend.checkedAt)));

  await new Promise((r) => server.close(r));
  await new Promise((r) => setTimeout(r, 300));
  assert.equal(monitor.getStatuses().find((s) => s.name === 'frontend').state, 'down');
  monitor.stop();
});

test('monitor: getStatuses no espera a un check lento ni rechaza ante fallos', async () => {
  const monitor = createHealthMonitor({
    services: [
      { name: 'frontend', port: 1 },
      { name: 'backend', port: 2 },
    ],
    included: ['frontend', 'backend'],
    intervalMs: 50,
    checkPort: (port) =>
      port === 1 ? new Promise(() => {}) : Promise.reject(new Error('boom')),
  });
  monitor.start();
  const t0 = Date.now();
  const statuses = monitor.getStatuses();
  assert.ok(Date.now() - t0 < 50);
  assert.equal(statuses.length, 2);
  await new Promise((r) => setTimeout(r, 150));
  assert.equal(monitor.getStatuses().find((s) => s.name === 'backend').state, 'down');
  monitor.stop();
});
