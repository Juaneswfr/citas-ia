// Responsabilidad: comprobar antes de arrancar que existen las herramientas y
// dependencias necesarias, con mensajes accionables. No lee ni imprime `.env`.

import fs from 'node:fs';
import path from 'node:path';

/** @typedef {import('./services.mjs').ServiceDefinition} ServiceDefinition */

/** Dependencias instaladas esperadas por servicio y cómo instalarlas. */
const DEPENDENCIES = {
  frontend: { dir: 'node_modules', install: 'npm install' },
  backend: { dir: '.venv', install: 'uv sync' },
  agent: { dir: '.venv', install: 'uv sync' },
};

const TOOL_HINTS = {
  uv: 'Instálalo con: curl -LsSf https://astral.sh/uv/install.sh | sh',
  npm: 'Instala Node.js >= 20 (incluye npm).',
};

/**
 * Busca un ejecutable en el PATH.
 * @param {string} command
 * @param {(p: string) => boolean} [exists]
 * @returns {boolean}
 */
export function whichInPath(command, exists = fs.existsSync) {
  const dirs = (process.env.PATH ?? '').split(path.delimiter).filter(Boolean);
  return dirs.some((dir) => exists(path.join(dir, command)));
}

/**
 * Comprueba requisitos de los servicios incluidos.
 * @param {Object} options
 * @param {ServiceDefinition[]} options.services Servicios que se van a lanzar.
 * @param {(p: string) => boolean} [options.exists]
 * @param {(command: string) => boolean} [options.which]
 * @returns {string[]} Lista de problemas (vacía si todo está bien).
 */
export function runPreflight({
  services,
  exists = fs.existsSync,
  which = (command) => whichInPath(command, exists),
}) {
  const problems = [];
  const checkedTools = new Set();

  for (const service of services) {
    if (!checkedTools.has(service.command)) {
      checkedTools.add(service.command);
      if (!which(service.command)) {
        const hint = TOOL_HINTS[service.command] ?? '';
        problems.push(`"${service.command}" no está en el PATH. ${hint}`.trim());
      }
    }
    const dep = DEPENDENCIES[service.name];
    if (dep && !exists(path.join(service.cwd, dep.dir))) {
      const folder = path.basename(service.cwd);
      problems.push(
        `Faltan las dependencias de ${service.name}: ejecuta "cd ${folder} && ${dep.install}".`,
      );
    }
  }
  return problems;
}
