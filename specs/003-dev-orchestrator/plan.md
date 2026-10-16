# Implementation Plan: Orquestador de Desarrollo Local

**Branch**: `003-dev-orchestrator` | **Date**: 2026-10-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-dev-orchestrator/spec.md`

## Summary

Un comando `npm run dev` / `npm run dev:all` en la raíz levanta frontend (5173), backend (8000) y opcionalmente el agente langgraph (8123) con logs prefijados y coloreados, detención en cascada, apagado limpio del árbol de procesos y un dashboard de estado solo lectura en `127.0.0.1:4300`. Enfoque: Node.js ESM con `child_process.spawn` escrito a mano (procesos `detached` + `process.kill(-pid)`), express únicamente para el dashboard, health checks TCP con timeout corto, módulos de responsabilidad única bajo `dev/`.

## Technical Context

**Language/Version**: Node.js ≥ 20 (ESM, archivos `.mjs`); entorno local con Node 26

**Primary Dependencies**: `express` (única dependencia de runtime; solo dashboard). Sin librerías de orquestación ni de color (ANSI manual)

**Storage**: N/A (estado en memoria)

**Testing**: `node:test` nativo (`node --test dev/`); sin dependencias de test

**Target Platform**: Linux/macOS (POSIX); Windows nativo fuera de alcance

**Project Type**: Herramienta CLI de desarrollo local + servidor HTTP de estado

**Performance Goals**: Dashboard refleja cambios en < 5 s (sondeo cada 2 s); cascada de cierre < 10 s; gracia SIGTERM 5 s antes de SIGKILL

**Constraints**: Bind exclusivo a `127.0.0.1`; solo GET/HEAD; health check con timeout 1 s por servicio, en paralelo; no tocar `docker-compose.yml`, `nginx/`, `front-app/`, `backend-lang/`

**Scale/Scope**: 3 servicios, 1 desarrollador local, ~8 módulos pequeños

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Aplicación | Estado |
|-----------|-----------|--------|
| I WhatsApp-First | Herramienta de dev, no altera el producto | N/A |
| II Backend centro | No toca lógica de negocio | N/A |
| III Agente determinístico | Solo arranca el servidor langgraph; no cambia el agente | N/A |
| IV Multi-tenant | Sin datos de negocio | N/A |
| V Observabilidad | Logs prefijados + evento de salida estructurado; estado consultable por JSON | PASS |
| VI Calendario | No aplica | N/A |
| VII Seguridad por defecto | No se leen ni exponen `.env`/secretos; el entorno se hereda al hijo sin imprimirse | PASS |
| VIII Operación resiliente | Health check por servicio; uno lento o fallido no rompe el dashboard | PASS |
| IX Confirmación explícita | Sin acciones del agente; dashboard sin acciones de control | N/A |
| X SOLID / SRP | Módulos separados (servicios, supervisor, health, dashboard, logger, exit-event, preflight, cli); dependencias inyectadas (DIP) para testear sin procesos reales | PASS |
| XI Seguridad de endpoints | Ver análisis abajo | PASS (con justificación) |
| XII Documentación | `dev/README.md`, JSDoc en funciones públicas, cabecera por módulo | PASS |

**Nota de stack**: la constitución fija Python/FastAPI para el *backend del producto*. Esto es tooling de desarrollo fuera del backend; Node.js ya lo exige `front-app/`. No altera ni reemplaza el stack del producto → sin enmienda.

**Análisis de endpoints (Principio XI)** — `GET /` y `GET /api/status`:
- ¿Autenticación? No; justificado: bind `127.0.0.1`, solo lectura, sin datos sensibles (spec, Assumptions). Se documenta en código y README.
- ¿Workspace? N/A, sin datos de tenant.
- ¿Rol mínimo? N/A; ningún método de escritura: 405 para todo salvo GET/HEAD.
- ¿Validación de input? No hay input (sin parámetros ni body).
- ¿Errores sin stack traces? Handler genérico devuelve `{"error": ...}` sin detalles.
- ¿Logging? Solo errores de bind; sin datos de requests.
- Respuesta limitada a: nombre, puerto, estado, `checkedAt` (FR-012).

**Re-evaluación post-diseño**: sin violaciones; Complexity Tracking vacío.

## Project Structure

### Documentation (this feature)

```text
specs/003-dev-orchestrator/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── dashboard-api.md
└── tasks.md             # /speckit-tasks (no creado aquí)
```

### Source Code (repository root)

```text
package.json             # scripts dev, dev:all, test; dependencia: express
package-lock.json
dev/
├── README.md            # uso, puertos, dashboard, solución de problemas
├── cli.mjs              # entrada: parsea --all, compone módulos, señales, exit code
├── services.mjs         # definición de servicios + configuración por env
├── supervisor.mjs       # spawn detached, kill de grupo, gracia + SIGKILL
├── exit-event.mjs       # lógica pura: código|señal → evento de salida
├── logger.mjs           # prefijo + color ANSI por línea, buffer de líneas parciales
├── health.mjs           # check TCP con timeout; estado up|down|not-included
├── preflight.mjs        # verifica herramientas/dependencias con mensaje accionable
├── dashboard.mjs        # express solo lectura, bind 127.0.0.1
└── __tests__/
    ├── health.test.mjs
    ├── exit-event.test.mjs
    ├── logger.test.mjs
    ├── supervisor.test.mjs
    └── dashboard.test.mjs
```

**Structure Decision**: Proyecto único en la raíz con carpeta `dev/`. Un módulo por responsabilidad; `cli.mjs` es la única composición. `.gitignore` ya ignora `node_modules/`. Sin cambios en `front-app/`, `backend-lang/`, `nginx/` ni compose.

## Complexity Tracking

Sin violaciones que justificar.
