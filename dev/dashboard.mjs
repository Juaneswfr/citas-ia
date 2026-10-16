// Responsabilidad: dashboard de estado local, solo lectura.
//
// Justificación de ausencia de autenticación (Principio XI): el servidor hace
// bind exclusivamente a 127.0.0.1, solo admite GET/HEAD y expone únicamente
// nombre, puerto, estado y hora de comprobación (sin env, secretos, rutas,
// comandos ni logs).

import express from 'express';

const PAGE = `<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Estado del entorno de desarrollo</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }
  table { border-collapse: collapse; min-width: 24rem; }
  th, td { text-align: left; padding: .5rem 1rem; border-bottom: 1px solid #ddd; }
  .up { color: #0a7d32; } .down { color: #b00020; } .not-included { color: #777; }
</style>
</head>
<body>
<h1>Entorno de desarrollo</h1>
<table>
  <thead><tr><th>Servicio</th><th>Puerto</th><th>Estado</th></tr></thead>
  <tbody id="rows"></tbody>
</table>
<p id="meta"></p>
<script>
async function refresh() {
  const meta = document.getElementById('meta');
  try {
    const res = await fetch('/api/status', { cache: 'no-store' });
    const data = await res.json();
    const rows = document.getElementById('rows');
    rows.replaceChildren();
    for (const s of data.services) {
      const tr = document.createElement('tr');
      for (const text of [s.name, String(s.port), s.state]) {
        const td = document.createElement('td');
        td.textContent = text;
        tr.appendChild(td);
      }
      tr.lastChild.className = s.state;
      rows.appendChild(tr);
    }
    meta.textContent = 'Actualizado: ' + data.generatedAt;
  } catch {
    meta.textContent = 'No se pudo obtener el estado.';
  }
}
refresh();
setInterval(refresh, 2000);
</script>
</body>
</html>
`;

/**
 * Crea el dashboard.
 * @param {Object} options
 * @param {() => import('./health.mjs').ServiceStatus[]} options.getStatuses Lee la caché de estados.
 * @param {() => Date} [options.now]
 * @param {number} options.port Puerto de escucha (en 127.0.0.1).
 * @returns {{app: import('express').Express, listen: () => Promise<import('node:http').Server>}}
 */
export function createDashboard({ getStatuses, now = () => new Date(), port }) {
  const app = express();
  app.disable('x-powered-by');

  app.use((req, res, next) => {
    res.set('Cache-Control', 'no-store');
    res.set('X-Content-Type-Options', 'nosniff');
    next();
  });

  app.use((req, res, next) => {
    if (req.method === 'GET' || req.method === 'HEAD') return next();
    res.set('Allow', 'GET, HEAD');
    return res.status(405).json({ error: 'method not allowed' });
  });

  app.get('/', (req, res) => {
    res.type('html').send(PAGE);
  });

  app.get('/api/status', (req, res) => {
    const services = getStatuses().map(({ name, port: p, state, checkedAt }) => ({
      name,
      port: p,
      state,
      checkedAt,
    }));
    res.json({ services, generatedAt: now().toISOString() });
  });

  app.use((req, res) => {
    res.status(404).json({ error: 'not found' });
  });

  // eslint-disable-next-line no-unused-vars
  app.use((err, req, res, next) => {
    res.status(500).json({ error: 'internal error' });
  });

  return {
    app,
    listen() {
      return new Promise((resolve, reject) => {
        const server = app.listen(port, '127.0.0.1');
        server.once('listening', () => resolve(server));
        server.once('error', (err) =>
          reject(
            new Error(
              `No se pudo abrir el dashboard en 127.0.0.1:${port} (${err.code ?? err.message}).`,
            ),
          ),
        );
      });
    },
  };
}
