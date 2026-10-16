# Orquestador de desarrollo local

Levanta frontend, backend y (opcionalmente) el agente langgraph con un solo comando, con logs prefijados y coloreados, detención en cascada, apagado limpio y un dashboard de estado. **Solo para desarrollo local**: no sustituye a `docker-compose`. Windows nativo está fuera de alcance (usa procesos POSIX).

## Requisitos

- Node.js ≥ 20 y `npm install` en la raíz (instala `express`, usado solo por el dashboard).
- `uv` en el PATH.
- Dependencias instaladas: `cd front-app && npm install` y `cd backend-lang && uv sync`.

## Comandos

| Comando | Qué hace |
|---------|----------|
| `npm run dev` | Frontend + backend |
| `npm run dev:all` | Frontend + backend + agente (`langgraph dev`) |
| `npm test` | Pruebas (`node --test dev/`) |

## Puertos

| Servicio | Variable | Por defecto |
|----------|----------|-------------|
| frontend | `DEV_FRONTEND_PORT` | 5173 |
| backend | `DEV_BACKEND_PORT` | 8000 |
| agent | `DEV_AGENT_PORT` | 8123 |
| dashboard | `DEV_DASHBOARD_PORT` | 4300 |

Deben ser enteros entre 1 y 65535 y distintos entre sí; si no, el orquestador sale con un error que indica la variable.

## Dashboard

- `http://127.0.0.1:4300/` — página HTML con el estado de cada servicio (se refresca cada 2 s).
- `http://127.0.0.1:4300/api/status` — JSON `{services:[{name,port,state,checkedAt}],generatedAt}` con `state` ∈ `up | down | not-included`.

Solo escucha en `127.0.0.1`, solo admite `GET`/`HEAD` (el resto devuelve 405) y no expone entorno, secretos, rutas, comandos ni logs. No tiene autenticación porque es solo lectura y solo loopback.

## Apagado y códigos de salida

- `Ctrl+C` (o `SIGTERM`/`SIGHUP`): envía `SIGTERM` al grupo de procesos de cada servicio y, tras 5 s, `SIGKILL`. Un segundo `Ctrl+C` fuerza `SIGKILL` inmediato. Código de salida `0`.
- Si un servicio termina por su cuenta (con cualquier código o señal), se imprime `<servicio> terminó con código N` / `por señal SIG…`, se detienen los demás y el orquestador sale con el código del servicio si es ≠ 0, o `1`.

## Solución de problemas

- **Puerto ocupado**: el frontend usa `--strictPort`, así que falla en vez de saltar de puerto. Libera el puerto o cambia la variable `DEV_*_PORT`.
- **`uv` ausente / dependencias sin instalar**: el preflight lo indica con el comando a ejecutar.
- **Puerto del dashboard ocupado**: se avisa y los servicios siguen funcionando sin dashboard.
