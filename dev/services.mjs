// Responsabilidad: definir los servicios locales (frontend, backend, agente) y
// leer su configuración de puertos desde el entorno, validándola.
//
// Flags de arranque: basados en specs/003-dev-orchestrator/research.md §4.
// NOTA (T003): no se pudieron ejecutar `npm run dev -- --help` ni
// `uv run ... --help` en la sesión de implementación (los comandos npm/uv
// requerían aprobación interactiva). Los flags NO están verificados con --help;
// verificar manualmente (`--port`, `--strictPort`, `--app-dir`, `--no-browser`)
// antes del primer uso y ajustar aquí si hay discrepancias.

import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

/**
 * @typedef {Object} ServiceDefinition
 * @property {'frontend'|'backend'|'agent'} name Nombre único; prefijo de log.
 * @property {number} port Puerto (1–65535).
 * @property {number} color Código ANSI de color (SGR).
 * @property {string} command Ejecutable.
 * @property {string[]} args Argumentos.
 * @property {string} cwd Directorio de trabajo absoluto.
 * @property {boolean} optional `true` si solo se incluye con `--all`.
 */

/**
 * @typedef {Object} DevConfig
 * @property {ServiceDefinition[]} services
 * @property {number} dashboardPort
 */

/**
 * Lee y valida un puerto desde el entorno.
 * @param {Record<string,string|undefined>} env
 * @param {string} variable
 * @param {number} fallback
 * @returns {number}
 */
function readPort(env, variable, fallback) {
  const raw = env[variable];
  if (raw === undefined || raw === '') return fallback;
  const value = Number(raw);
  if (!/^\d+$/.test(raw) || !Number.isInteger(value) || value < 1 || value > 65535) {
    throw new Error(
      `${variable}="${raw}" no es válido: debe ser un entero entre 1 y 65535.`,
    );
  }
  return value;
}

/**
 * Devuelve la definición de los servicios y el puerto del dashboard.
 * @param {Record<string,string|undefined>} [env]
 * @returns {DevConfig}
 * @throws {Error} Si un puerto es inválido o está duplicado.
 */
export function loadServices(env = process.env) {
  const ports = {
    frontend: readPort(env, 'DEV_FRONTEND_PORT', 5173),
    backend: readPort(env, 'DEV_BACKEND_PORT', 8000),
    agent: readPort(env, 'DEV_AGENT_PORT', 8123),
    dashboard: readPort(env, 'DEV_DASHBOARD_PORT', 4300),
  };
  const variables = {
    frontend: 'DEV_FRONTEND_PORT',
    backend: 'DEV_BACKEND_PORT',
    agent: 'DEV_AGENT_PORT',
    dashboard: 'DEV_DASHBOARD_PORT',
  };

  const seen = new Map();
  for (const [key, port] of Object.entries(ports)) {
    if (seen.has(port)) {
      throw new Error(
        `Puerto duplicado ${port}: ${variables[seen.get(port)]} y ${variables[key]} deben ser distintos.`,
      );
    }
    seen.set(port, key);
  }

  /** @type {ServiceDefinition[]} */
  const services = [
    {
      name: 'frontend',
      port: ports.frontend,
      color: 36, // cian
      command: 'npm',
      args: ['run', 'dev', '--', '--port', String(ports.frontend), '--strictPort'],
      cwd: path.join(ROOT, 'front-app'),
      optional: false,
    },
    {
      name: 'backend',
      port: ports.backend,
      color: 32, // verde
      command: 'uv',
      args: [
        'run', 'uvicorn', 'api.main:app', '--reload',
        '--port', String(ports.backend), '--app-dir', 'src',
      ],
      cwd: path.join(ROOT, 'backend-lang'),
      optional: false,
    },
    {
      name: 'agent',
      port: ports.agent,
      color: 35, // magenta
      command: 'uv',
      args: ['run', 'langgraph', 'dev', '--port', String(ports.agent), '--no-browser'],
      cwd: path.join(ROOT, 'backend-lang'),
      optional: true,
    },
  ];

  return { services, dashboardPort: ports.dashboard };
}
