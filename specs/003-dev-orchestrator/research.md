# Research: Orquestador de Desarrollo Local

No quedaron `NEEDS CLARIFICATION`; el stack lo definió el usuario. Decisiones:

## 1. Orquestación de procesos
- **Decision**: `child_process.spawn` manual con `detached: true` (nuevo process group) y `process.kill(-pid, signal)`.
- **Rationale**: Controla la caída (`exit` con code/signal) y mata el árbol completo (vite, uvicorn `--reload`, workers de langgraph) sin huérfanos.
- **Alternatives**: `concurrently`/`npm-run-all` (dependencia extra, kill de árbol menos controlable); `pm2` (demasiado pesado).

## 2. Apagado
- **Decision**: SIGINT/SIGTERM/SIGHUP → SIGTERM al grupo de cada servicio; tras 5 s SIGKILL; segundo Ctrl+C → SIGKILL inmediato. Idempotente.
- **Rationale**: Cubre FR-006, doble Ctrl+C y cierre de terminal.
- **Alternatives**: `child.kill()` (deja nietos huérfanos).

## 3. Cascada y código de salida
- **Decision**: primer `exit` inesperado → imprimir evento, iniciar apagado, salir con el código del servicio si ≠ 0, o 1. Apagado pedido por el usuario → 0.
- **Rationale**: FR-004/FR-005; un fallo de arranque (puerto ocupado) es simplemente un `exit` ≠ 0.
- **Alternatives**: reinicio automático (fuera de alcance).

## 4. Comandos por servicio (existentes, sin modificar código)
- Frontend: `npm run dev -- --port <P> --strictPort` en `front-app/` (`strictPort` falla si el puerto está ocupado en vez de saltar a otro y desincronizar el dashboard).
- Backend: `uv run uvicorn api.main:app --reload --port <P> --app-dir src` en `backend-lang/` (mismo `api.main:app` del Dockerfile).
- Agente: `uv run langgraph dev --port <P> --no-browser` en `backend-lang/` (readme del backend).
- Verificar flags con `--help` durante la implementación.

## 5. Logs
- **Decision**: ANSI simple (`\x1b[<n>m`), prefijo `[nombre]` con padding; buffer por stream que parte por `\n` y emite solo líneas completas (flush al cerrar). Sin color si `NO_COLOR` o stdout no es TTY.
- **Rationale**: Sin `chalk`; SC-003 (100% de líneas prefijadas aun con chunks partidos).

## 6. Health checks
- **Decision**: conexión TCP (`net.connect`) a `127.0.0.1:<port>`, timeout 1 s, todas en paralelo (`Promise.all`). Un sondeo cada 2 s actualiza una caché; las peticiones HTTP leen la caché y nunca esperan. Estados: `up`, `down`, `not-included`.
- **Rationale**: FR-009; TCP basta para activo/caído sin acoplarse a rutas ni auth de cada app. Se deja opción `http.get` para checks por servicio si hiciera falta.
- **Alternatives**: GET `/` por HTTP (acopla a rutas del backend).

## 7. Dashboard
- **Decision**: express, `listen(port, '127.0.0.1')`, middleware que solo permite GET/HEAD (405 resto), `x-powered-by` off, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`; HTML inline con polling a `/api/status` cada 2 s. Fallo de bind se reporta sin tumbar los servicios.
- **Rationale**: FR-007/008/010/011/012.

## 8. Configuración por entorno
- `DEV_FRONTEND_PORT` (5173), `DEV_BACKEND_PORT` (8000), `DEV_AGENT_PORT` (8123), `DEV_DASHBOARD_PORT` (4300). Validación: entero 1–65535 y sin duplicados; si no, error accionable.

## 9. Preflight
- Comprobar `uv` en PATH, `front-app/node_modules` y entorno de `backend-lang`; mensaje con el comando a ejecutar (`cd front-app && npm install`, `cd backend-lang && uv sync`). FR-015.

## 10. Pruebas
- `node:test`: `health` (servidor TCP efímero: up/down/timeout), `exit-event` (código/señal/esperado), `logger` (chunks partidos), `supervisor` (hijos triviales con `node -e`, verifica kill de grupo y nietos), `dashboard` (405 en POST, bind 127.0.0.1, JSON sin campos extra).
