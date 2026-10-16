import test from 'node:test';
import assert from 'node:assert/strict';
import { loadServices } from '../services.mjs';

test('valores por defecto', () => {
  const { services, dashboardPort } = loadServices({});
  const ports = Object.fromEntries(services.map((s) => [s.name, s.port]));
  assert.deepEqual(ports, { frontend: 5173, backend: 8000, agent: 8123 });
  assert.equal(dashboardPort, 4300);
});

test('override por env', () => {
  const { services, dashboardPort } = loadServices({
    DEV_FRONTEND_PORT: '3000',
    DEV_BACKEND_PORT: '9000',
    DEV_AGENT_PORT: '9100',
    DEV_DASHBOARD_PORT: '9200',
  });
  assert.deepEqual(services.map((s) => s.port), [3000, 9000, 9100]);
  assert.equal(dashboardPort, 9200);
  assert.ok(services[0].args.includes('3000'));
});

test('rechaza puertos inválidos mencionando la variable', () => {
  for (const bad of ['abc', '1.5', '0', '70000', '-1']) {
    assert.throws(() => loadServices({ DEV_BACKEND_PORT: bad }), /DEV_BACKEND_PORT/);
  }
});

test('rechaza puertos duplicados mencionando las variables', () => {
  assert.throws(
    () => loadServices({ DEV_FRONTEND_PORT: '8000' }),
    /DEV_FRONTEND_PORT.*DEV_BACKEND_PORT|DEV_BACKEND_PORT.*DEV_FRONTEND_PORT/,
  );
  assert.throws(() => loadServices({ DEV_DASHBOARD_PORT: '5173' }), /DEV_DASHBOARD_PORT/);
});

test('colores distintos y solo agent es opcional', () => {
  const { services } = loadServices({});
  assert.equal(new Set(services.map((s) => s.color)).size, services.length);
  assert.deepEqual(services.filter((s) => s.optional).map((s) => s.name), ['agent']);
});
