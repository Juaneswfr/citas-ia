# Data Model: Orquestador de Desarrollo Local

Todo en memoria; sin persistencia. Tipos documentados con JSDoc (`@typedef`).

## ServiceDefinition (`dev/services.mjs`)

| Campo | Tipo | Notas |
|-------|------|-------|
| `name` | `'frontend' \| 'backend' \| 'agent'` | Único; prefijo de log |
| `port` | `number` | 1–65535; de env o default; único entre servicios y dashboard |
| `color` | código ANSI | Distinto por servicio |
| `command`, `args` | `string`, `string[]` | Comandos existentes (research §4) |
| `cwd` | `string` | `front-app/` o `backend-lang/` |
| `optional` | `boolean` | `true` solo para `agent` (se incluye con `dev:all`) |

## ServiceStatus (`dev/health.mjs`)

| Campo | Tipo | Notas |
|-------|------|-------|
| `name` | string | |
| `port` | number | |
| `state` | `'up' \| 'down' \| 'not-included'` | `not-included` si el servicio no se lanzó |
| `checkedAt` | ISO-8601 string | Última comprobación |

Transiciones: `down ⇄ up` según conectividad (el arranque es `down` transitorio); `not-included` es fijo durante la ejecución.

## ExitEvent (`dev/exit-event.mjs`)

| Campo | Tipo | Notas |
|-------|------|-------|
| `service` | string | |
| `code` | `number \| null` | |
| `signal` | `string \| null` | Exactamente uno de code/signal no es nulo |
| `expected` | boolean | `true` si ocurrió durante un apagado solicitado |
| `message` | string | Ej.: `backend terminó con código 1` / `por señal SIGKILL` |

## Estados del orquestador

`starting → running → shutting-down → exited`. Se entra a `shutting-down` por señal de usuario (exit 0) o por un `ExitEvent` inesperado (exit ≠ 0). Idempotente.
