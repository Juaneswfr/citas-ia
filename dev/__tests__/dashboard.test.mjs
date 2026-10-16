import test from 'node:test';
import assert from 'node:assert/strict';
import net from 'node:net';
import { createDashboard } from '../dashboard.mjs';

const STATUSES = [
  { name: 'frontend', port: 5173, state: 'up', checkedAt: '2026-10-16T12:00:00.000Z', extra: 'x' },
  { name: 'agent', port: 8123, state: 'not-included', checkedAt: '2026-10-16T12:00:00.000Z' },
];

async function withServer(getStatuses, fn) {
  const dash = createDashboard({
    getStatuses,
    now: () => new Date('2026-10-16T12:00:01.000Z'),
    port: 0,
  });
  const server = await dash.listen();
  const { address, port } = server.address();
  try {
    await fn(`http://127.0.0.1:${port}`, address);
  } finally {
    server.closeAllConnections?.();
    await new Promise((r) => server.close(r));
  }
}

test('GET /api/status devuelve solo los campos del contrato', async () => {
  await withServer(() => STATUSES, async (base) => {
    const res = await fetch(`${base}/api/status`);
    assert.equal(res.status, 200);
    assert.match(res.headers.get('content-type'), /application\/json/);
    const body = await res.json();
    assert.deepEqual(Object.keys(body).sort(), ['generatedAt', 'services']);
    assert.equal(body.generatedAt, '2026-10-16T12:00:01.000Z');
    for (const s of body.services) {
      assert.deepEqual(Object.keys(s).sort(), ['checkedAt', 'name', 'port', 'state']);
    }
  });
});

test('GET / → 200 text/html', async () => {
  await withServer(() => STATUSES, async (base) => {
    const res = await fetch(`${base}/`);
    assert.equal(res.status, 200);
    assert.match(res.headers.get('content-type'), /text\/html/);
  });
});

test('métodos de escritura y OPTIONS → 405 con Allow; HEAD permitido', async () => {
  await withServer(() => STATUSES, async (base) => {
    for (const method of ['POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']) {
      const res = await fetch(`${base}/api/status`, { method });
      assert.equal(res.status, 405, method);
      assert.equal(res.headers.get('allow'), 'GET, HEAD');
    }
    assert.equal((await fetch(`${base}/api/status`, { method: 'HEAD' })).status, 200);
  });
});

test('ruta desconocida → 404 JSON', async () => {
  await withServer(() => STATUSES, async (base) => {
    const res = await fetch(`${base}/nope`);
    assert.equal(res.status, 404);
    assert.deepEqual(await res.json(), { error: 'not found' });
  });
});

test('cabeceras de seguridad y sin X-Powered-By', async () => {
  await withServer(() => STATUSES, async (base) => {
    const res = await fetch(`${base}/api/status`);
    assert.equal(res.headers.get('cache-control'), 'no-store');
    assert.equal(res.headers.get('x-content-type-options'), 'nosniff');
    assert.equal(res.headers.get('x-powered-by'), null);
  });
});

test('escucha solo en 127.0.0.1', async () => {
  await withServer(() => STATUSES, async (base, address) => {
    assert.equal(address, '127.0.0.1');
  });
});

test('error en getStatuses → 500 sin stack', async () => {
  await withServer(
    () => {
      throw new Error('secreto interno');
    },
    async (base) => {
      const res = await fetch(`${base}/api/status`);
      assert.equal(res.status, 500);
      const text = await res.text();
      assert.deepEqual(JSON.parse(text), { error: 'internal error' });
      assert.ok(!text.includes('secreto'));
    },
  );
});

test('conflicto de puerto → error claro', async () => {
  const blocker = net.createServer();
  await new Promise((r) => blocker.listen(0, '127.0.0.1', r));
  const { port } = blocker.address();
  try {
    const dash = createDashboard({ getStatuses: () => [], port });
    await assert.rejects(dash.listen(), /127\.0\.0\.1:\d+.*EADDRINUSE/);
  } finally {
    await new Promise((r) => blocker.close(r));
  }
});
