---

description: "Task list for Orquestador de Desarrollo Local"
---

# Tasks: Orquestador de Desarrollo Local

**Input**: Design documents from `/specs/003-dev-orchestrator/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/dashboard-api.md, quickstart.md

**Tests**: Incluidos. FR-017 exige que la lógica de estado y de manejo de salida sea verificable con pruebas automatizadas; plan.md fija `node:test` (`node --test dev/`), sin dependencias de test.

**Organization**: Tareas agrupadas por historia de usuario. Todas las rutas son relativas a la raíz del repo (`/opt/data/home/projects/citas-ia`). Solo se añaden archivos en la raíz y `dev/`; NO se tocan `docker-compose.yml`, `nginx/`, `front-app/` ni `backend-lang/` (FR-013).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivos distintos, sin dependencias incompletas)
- **[Story]**: Historia a la que pertenece (US1–US5)

## Convenciones de código (aplican a todas las tareas)

- Node.js ≥ 20, ESM, archivos `.mjs`, sin dependencias salvo `express` (solo dashboard). Sin librerías de color ni de orquestación.
- Cada módulo con cabecera de comentario de su responsabilidad y JSDoc (`@typedef`/`@param`/`@returns`) en funciones públicas (Principio XII).
- Responsabilidad única; las dependencias (spawn, kill, net, reloj) se inyectan para poder testear sin procesos reales (Principio X).
- No imprimir ni exponer variables de entorno ni secretos (FR-012, Principio VII). El entorno se hereda al hijo sin mostrarse.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Estructura del proyecto y dependencias

- [ ] T001 Crear `package.json` en la raíz con `"private": true`, `"type": "module"`, `"engines": {"node": ">=20"}`, scripts `"dev": "node dev/cli.mjs"`, `"dev:all": "node dev/cli.mjs --all"`, `"test": "node --test dev/"`, y ejecutar `npm install express` para generar `package-lock.json` (única dependencia de runtime)
- [X] T002 [P] Verificar que `.gitignore` en la raíz ya ignora `node_modules/` (añadir la línea solo si falta) y crear las carpetas `dev/` y `dev/__tests__/`
- [ ] T003 [P] Verificar los flags reales de los comandos de arranque con `--help` sin modificar código: `npm run dev -- --help` en `front-app/` (`--port`, `--strictPort`), `uv run uvicorn --help` y `uv run langgraph dev --help` en `backend-lang/` (`--port`, `--no-browser`, `--reload`, `--app-dir`); anotar cualquier discrepancia como comentario en `dev/services.mjs` al crearlo (research §4)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Módulos puros y compartidos que todas las historias necesitan

**⚠️ CRITICAL**: Ninguna historia puede empezar hasta completar esta fase

- [X] T004 [P] Implementar `dev/services.mjs`: typedef `ServiceDefinition` y función `loadServices(env = process.env)` que devuelve los 3 servicios y el puerto del dashboard. Definiciones según research §4/§8 y data-model: `frontend` (color cian, `npm run dev -- --port <P> --strictPort`, cwd `front-app/`), `backend` (color verde, `uv run uvicorn api.main:app --reload --port <P> --app-dir src`, cwd `backend-lang/`), `agent` (color magenta, `uv run langgraph dev --port <P> --no-browser`, cwd `backend-lang/`, `optional: true`). Puertos de env `DEV_FRONTEND_PORT` (5173), `DEV_BACKEND_PORT` (8000), `DEV_AGENT_PORT` (8123), `DEV_DASHBOARD_PORT` (4300). Validación: entero 1–65535 y sin duplicados entre los 4 puertos; si no, lanzar Error con mensaje accionable (indica la variable y el valor inválido). `name` ∈ `'frontend'|'backend'|'agent'`, único; `color` distinto por servicio
- [X] T005 [P] Implementar `dev/exit-event.mjs`: typedef `ExitEvent` y función pura `createExitEvent({service, code, signal, shuttingDown})` → `{service, code, signal, expected, message}`. Exactamente uno de `code`/`signal` no es nulo; `expected = shuttingDown`; `message` en español: `"<service> terminó con código <n>"` o `"<service> terminó por señal <SIG>"`
- [X] T006 [P] Implementar `dev/logger.mjs`: función `createLineLogger({name, color, write, useColor})` que devuelve `{push(chunk), flush()}`. Buffer por stream que parte por `\n` y emite solo líneas completas con prefijo `[nombre]` con padding al ancho del nombre más largo y color ANSI (`\x1b[<n>m` … `\x1b[0m`); `flush()` emite el resto parcial al cerrar el stream. `useColor` por defecto `false` si `NO_COLOR` está definido o `process.stdout.isTTY` es falso. Exportar también `createSystemLogger(write, useColor)` para mensajes del orquestador con prefijo `[dev]`
- [X] T007 [P] Test de `createExitEvent` en `dev/__tests__/exit-event.test.mjs` (`node:test`): código distinto de cero, señal (p. ej. `SIGKILL`), `expected` true/false según `shuttingDown`, y que exactamente uno de code/signal es no nulo
- [X] T008 [P] Test de `createLineLogger` en `dev/__tests__/logger.test.mjs`: chunks partidos a mitad de línea producen una sola línea con un solo prefijo; varias líneas en un chunk; `flush()` emite el parcial; con `useColor: false` no hay secuencias ANSI; con `true` cada línea lleva el color del servicio (cubre SC-003)
- [X] T009 [P] Test de `loadServices` en `dev/__tests__/services.test.mjs`: valores por defecto (5173/8000/8123/4300), override por env, rechazo de puerto no entero, fuera de 1–65535 y duplicado (mensaje menciona la variable), colores distintos, solo `agent` con `optional: true`

**Checkpoint**: Fundación lista — `node --test dev/` pasa para T007–T009

---

## Phase 3: User Story 1 - Levantar el entorno con un solo comando (Priority: P1) 🎯 MVP

**Goal**: `npm run dev` levanta frontend y backend en paralelo con logs prefijados y coloreados; `npm run dev:all` añade el agente

**Independent Test**: Con dependencias instaladas y puertos libres, `npm run dev` → `curl -I localhost:5173` y `curl localhost:8000/` responden en < 60 s y cada línea lleva `[frontend]`/`[backend]`; `npm run dev:all` añade `[agent]` en 8123

### Implementation for User Story 1

- [X] T010 [P] [US1] Implementar `dev/preflight.mjs`: función `runPreflight({services, exists, which})` (fs/PATH inyectables) que comprueba `uv` en PATH, existencia de `front-app/node_modules` y del entorno de `backend-lang` (`.venv`), solo para los servicios incluidos. Devuelve lista de problemas, cada uno con mensaje accionable que incluye el comando a ejecutar (`cd front-app && npm install`, `cd backend-lang && uv sync`) (FR-015, research §9). No lee ni imprime `.env`
- [X] T011 [US1] Implementar en `dev/supervisor.mjs` la creación del supervisor `createSupervisor({services, spawn, kill, logger, onExit})`: método `start()` que lanza cada servicio con `child_process.spawn(command, args, {cwd, detached: true, stdio: ['ignore','pipe','pipe'], env: process.env})`, conecta stdout/stderr de cada hijo a su `createLineLogger` (T006) y hace `flush()` al cerrar los streams; registra el `pid` por servicio. Dependencias inyectadas para testear (depende de T004, T006)
- [X] T012 [US1] Implementar `dev/cli.mjs`: parsear `--all` (incluye servicios `optional`), cargar servicios (T004) capturando errores de validación → mensaje + exit 1, ejecutar preflight (T010) y salir con código 1 listando problemas si hay alguno, componer logger + supervisor (T011) y arrancar los servicios incluidos, imprimiendo con el system logger la lista de servicios y puertos. Es la única composición del proyecto (depende de T010, T011)
- [X] T013 [US1] Test de `createSupervisor.start()` en `dev/__tests__/supervisor.test.mjs` usando hijos triviales con `node -e`: dos servicios en paralelo emiten líneas y cada línea llega al logger con el prefijo de su servicio (incluye chunk partido); el servicio opcional no se lanza si no se incluye
- [ ] T014 [US1] Ejecutar manualmente `npm run dev` y `npm run dev:all` (quickstart §2): confirmar 5173/8000(/8123) accesibles en < 60 s y prefijos/colores correctos; ajustar flags en `dev/services.mjs` si T003 reveló discrepancias

**Checkpoint**: US1 funcional y verificable por sí sola (MVP)

---

## Phase 4: User Story 2 - Fallo de un servicio detiene el resto con diagnóstico claro (Priority: P1)

**Goal**: Si un proceso termina, se informa servicio y código/señal, se detienen los demás y el orquestador sale con código ≠ 0

**Independent Test**: `pkill -f uvicorn` (o provocar puerto ocupado) → mensaje `backend terminó…`, los demás procesos terminan en < 10 s, `echo $?` ≠ 0

### Implementation for User Story 2

- [X] T015 [US2] En `dev/supervisor.mjs` manejar el evento `exit` de cada hijo: construir un `ExitEvent` con `createExitEvent` (T005), pasarlo a `onExit`, y si no es esperado iniciar el apagado de los demás servicios (llama a `shutdown()` de US3 cuando exista; hasta entonces `kill` de los restantes). Estados del orquestador `starting → running → shutting-down → exited`, transición idempotente (primer evento inesperado gana)
- [X] T016 [US2] En `dev/cli.mjs` imprimir el `message` del ExitEvent con el system logger y fijar el código de salida: el código del servicio si ≠ 0, `1` si salió con 0 o por señal, y `0` solo cuando el apagado lo pidió el usuario (research §3, FR-005). Cubre fallo de arranque (puerto ocupado/`--strictPort`) como un `exit` ≠ 0
- [X] T017 [US2] Ampliar `dev/__tests__/supervisor.test.mjs`: un hijo que sale con código 1 → se emite evento con servicio y código y los demás hijos reciben la orden de parada; un hijo terminado por señal → mensaje con la señal; dos salidas simultáneas → un solo apagado (idempotencia); salida con código 0 inesperada también cuenta como fallo
- [ ] T018 [US2] Verificar manualmente la cascada (quickstart §4): `pkill -f uvicorn` en otra terminal → mensaje correcto, resto detenido en < 10 s (SC-004), exit code ≠ 0; probar también puerto ocupado al arrancar

**Checkpoint**: US1 y US2 funcionan; el fallo siempre se diagnostica

---

## Phase 5: User Story 3 - Apagado limpio con Ctrl+C (Priority: P1)

**Goal**: SIGINT/SIGTERM/SIGHUP detienen todo el árbol de procesos sin huérfanos; gracia de 5 s y luego SIGKILL; doble Ctrl+C fuerza salida inmediata

**Independent Test**: Levantar, Ctrl+C → `ss -ltn | grep -E '5173|8000|8123|4300'` y `pgrep -f "vite|uvicorn|langgraph"` vacíos; repetible 10 veces

### Implementation for User Story 3

- [X] T019 [US3] En `dev/supervisor.mjs` implementar `shutdown({force})` idempotente: `kill(-pid, 'SIGTERM')` al grupo de cada hijo vivo (`process.kill(-pid, signal)` inyectable), temporizador de gracia de 5 s (inyectable) tras el cual `kill(-pid, 'SIGKILL')` a los que sigan vivos; `force: true` envía SIGKILL inmediato; ignora `ESRCH`; resuelve una promesa cuando todos los hijos han salido. Las salidas durante el apagado se marcan `expected: true`
- [X] T020 [US3] En `dev/cli.mjs` registrar handlers de `SIGINT`, `SIGTERM` y `SIGHUP` que llaman a `shutdown()` (primer disparo, exit 0 si no hubo fallo previo) y un segundo `SIGINT` que llama a `shutdown({force: true})`; salir del proceso solo cuando el supervisor confirme que todos terminaron (research §2)
- [X] T021 [US3] Ampliar `dev/__tests__/supervisor.test.mjs` con procesos reales triviales: (a) hijo `node -e` que lanza un nieto (`spawn` con `detached` heredando grupo) → tras `shutdown()` ni hijo ni nieto siguen vivos (verificar con `process.kill(pid, 0)` lanzando ESRCH); (b) hijo que ignora SIGTERM → es matado con SIGKILL tras la gracia (usar gracia corta inyectada); (c) `shutdown({force: true})` mata de inmediato; (d) llamar `shutdown()` dos veces no duplica kills
- [ ] T022 [US3] Verificar manualmente (quickstart §5): Ctrl+C, doble Ctrl+C, `kill -HUP` al orquestador; repetir 10 ciclos arranque/parada sin puertos ocupados ni procesos residuales (SC-005)

**Checkpoint**: Las tres historias P1 funcionan; el entorno de desarrollo es fiable

---

## Phase 6: User Story 4 - Dashboard de estado local (Priority: P2)

**Goal**: Dashboard HTML en `/` y JSON en `/api/status` con estado up/down/not-included por servicio, solo lectura y solo loopback

**Independent Test**: Con el entorno levantado, `curl -s http://127.0.0.1:4300/api/status` devuelve el JSON del contrato; detener un servicio lo cambia a `down` en < 5 s; `POST` → 405; `ss -ltn | grep 4300` muestra `127.0.0.1`

### Implementation for User Story 4

- [X] T023 [P] [US4] Implementar `dev/health.mjs`: typedef `ServiceStatus`, `checkPort(port, {timeoutMs = 1000, connect = net.connect})` → `Promise<boolean>` (conexión TCP a `127.0.0.1`, destruye el socket, resuelve `false` en error o timeout), y `createHealthMonitor({services, included, intervalMs = 2000, now, checkPort})` con `start()`/`stop()`/`getStatuses()`: sondeo cada 2 s con `Promise.all` (en paralelo), actualiza una caché y `getStatuses()` devuelve la última caché sin esperar; estados `up|down`, y `not-included` fijo para servicios no lanzados; `checkedAt` ISO-8601. Un check lento o fallido nunca rechaza ni bloquea (FR-009, Principio VIII)
- [X] T024 [P] [US4] Test de health en `dev/__tests__/health.test.mjs` con servidor TCP efímero (`net.createServer().listen(0, '127.0.0.1')`): `up` con servidor, `down` tras cerrarlo, timeout respetado con `connect` inyectado que nunca responde, `not-included` para el servicio excluido, `getStatuses()` no espera a un check lento
- [X] T025 [US4] Implementar `dev/dashboard.mjs` con `createDashboard({getStatuses, now, port})` (express): `app.disable('x-powered-by')`; middleware global con `Cache-Control: no-store` y `X-Content-Type-Options: nosniff`; middleware que responde `405` con `Allow: GET, HEAD` a todo método distinto de GET/HEAD (incluye OPTIONS); `GET /` devuelve HTML inline (nombre, puerto y estado por servicio, con polling a `/api/status` cada 2 s, sin acciones de control); `GET /api/status` devuelve exactamente `{"services":[{name,port,state,checkedAt}],"generatedAt"}` desde la caché, sin env, secretos, rutas, comandos ni logs (FR-012); ruta desconocida → `404 {"error":"not found"}`; handler de errores → `500 {"error":"internal error"}` sin stack. `listen(port, '127.0.0.1')` exclusivamente; si el bind falla (p. ej. `EADDRINUSE`) rechaza con un error de mensaje claro. Comentario de justificación de ausencia de auth (loopback + solo lectura, Principio XI) (depende de T023 para el tipo de estado)
- [X] T026 [US4] Test de dashboard en `dev/__tests__/dashboard.test.mjs`: `GET /api/status` devuelve solo los campos del contrato; `GET /` → 200 `text/html`; `POST|PUT|PATCH|DELETE|OPTIONS` → 405 con `Allow: GET, HEAD`; `HEAD` permitido; ruta desconocida → 404 JSON; cabeceras `Cache-Control`, `nosniff` presentes y `X-Powered-By` ausente; el servidor escucha en `127.0.0.1` (comprobar `server.address().address`); un error forzado en `getStatuses` → 500 sin stack; conflicto de puerto → error claro
- [X] T027 [US4] Integrar en `dev/cli.mjs`: crear el health monitor con los servicios incluidos (los no incluidos → `not-included`) y arrancar el dashboard en `DEV_DASHBOARD_PORT`; si el bind del dashboard falla, imprimir mensaje claro con el system logger y continuar sin tumbar los servicios; detener monitor y cerrar el servidor del dashboard durante el apagado (US3)
- [ ] T028 [US4] Verificar manualmente (quickstart §3): JSON del contrato, `agent: not-included` con `npm run dev`, cambio a `down` al matar un servicio en < 5 s (SC-006), `POST` → 405, `ss -ltn | grep 4300` solo en 127.0.0.1 (SC-007), y que con el puerto 4300 ocupado los servicios siguen funcionando

**Checkpoint**: Dashboard operativo e independiente del resto de historias

---

## Phase 7: User Story 5 - Convivencia con la infraestructura existente (Priority: P2)

**Goal**: Garantizar que no se altera docker-compose, nginx, `front-app/` ni `backend-lang/`

**Independent Test**: `git status --short front-app backend-lang nginx docker-compose.yml` vacío y `docker compose config` idéntico al previo

- [ ] T029 [US5] Antes de cerrar la feature, capturar la salida de `docker compose config > /tmp/compose-after.yml` y compararla con la de `git stash`/rama `master` (`git show master:docker-compose.yml` evaluado en un directorio temporal) o con una captura previa; confirmar que son idénticas (SC-008, FR-013)
- [ ] T030 [US5] Ejecutar `git status --short front-app backend-lang nginx docker-compose.yml` (debe estar vacío) y `git diff --stat master -- . ':!specs' ':!.specify' ':!.claude'` para comprobar que los únicos archivos añadidos son `package.json`, `package-lock.json`, `.gitignore` (si cambió) y `dev/**`

**Checkpoint**: No regresión confirmada

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentación, revisión de seguridad y validación final

- [X] T031 [P] Escribir `dev/README.md` (FR-016, Principio XII): requisitos (Node ≥ 20, `uv`, dependencias de `front-app/` y `backend-lang/`), comandos `npm run dev` / `npm run dev:all` / `npm test`, tabla de puertos y variables `DEV_*_PORT`, uso del dashboard (`/`, `/api/status`, solo loopback y solo lectura), comportamiento de Ctrl+C/cascada/códigos de salida, solución de problemas (puerto ocupado, `uv` ausente, dependencias sin instalar, puerto del dashboard ocupado) y alcance (solo desarrollo local; no sustituye a docker-compose; Windows nativo fuera de alcance)
- [ ] T032 [P] Revisión de cabeceras y JSDoc: cada módulo de `dev/*.mjs` tiene cabecera de responsabilidad y JSDoc en sus funciones públicas; sin código muerto ni dependencias no usadas en `package.json`
- [ ] T033 Revisión de seguridad (Principios VII/XI): comprobar que ningún log del orquestador ni respuesta del dashboard imprime `process.env`, rutas internas ni contenido de `.env`; que el dashboard solo hace bind a `127.0.0.1`; y que no hay endpoints de escritura
- [ ] T034 Ejecutar `npm test` (todas las pruebas deben pasar) y recorrer `specs/003-dev-orchestrator/quickstart.md` completo de principio a fin como validación final

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias
- **Foundational (Phase 2)**: depende de Setup — BLOQUEA todas las historias
- **US1 → US2 → US3**: comparten `dev/supervisor.mjs` y `dev/cli.mjs`, por lo que se implementan en orden de prioridad (cada una extiende la anterior); cada una sigue siendo verificable por separado con su Independent Test
- **US4 (Phase 6)**: `health.mjs`, `dashboard.mjs` y sus tests (T023–T026) solo dependen de Foundational y pueden hacerse en paralelo con US1–US3; la integración T027 requiere `cli.mjs` (US1) y el apagado (US3)
- **US5 (Phase 7)**: verificación; se ejecuta al final de la implementación
- **Polish (Phase 8)**: depende de las historias deseadas

### Dentro de cada historia

- Módulos puros antes de composición; tests junto al módulo que cubren; verificación manual al cerrar la historia

### Parallel Opportunities

- Setup: T002 y T003 en paralelo
- Foundational: T004, T005, T006 en paralelo; T007, T008, T009 en paralelo (cada uno tras su módulo)
- US1: T010 en paralelo con T011
- US4: T023 y T024 en paralelo con el trabajo de US1–US3 (archivos distintos)
- Polish: T031 y T032 en paralelo

---

## Parallel Example: Foundational

```bash
Task: "Implementar dev/services.mjs"      # T004
Task: "Implementar dev/exit-event.mjs"    # T005
Task: "Implementar dev/logger.mjs"        # T006
```

## Parallel Example: User Story 4 (en paralelo con US1–US3)

```bash
Task: "Implementar dev/health.mjs"                         # T023
Task: "Test de health en dev/__tests__/health.test.mjs"    # T024
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 Setup → Phase 2 Foundational
2. Phase 3 (US1): `npm run dev` funcional
3. **STOP y VALIDAR** con quickstart §2

### Incremental Delivery

1. Setup + Foundational → módulos puros testeados
2. US1 → arranque con un comando (MVP)
3. US2 → diagnóstico y cascada
4. US3 → apagado limpio sin huérfanos (las tres P1 completan un entorno fiable)
5. US4 → dashboard de estado
6. US5 + Polish → no regresión, README y validación final

---

## Notes

- [P] = archivos distintos, sin dependencias incompletas
- `supervisor.mjs` y `cli.mjs` los tocan varias historias: no marcar esas tareas [P]
- Commit tras cada tarea o grupo lógico
- No modificar `docker-compose.yml`, `nginx/`, `front-app/` ni `backend-lang/`

## Phase 9: Convergence

- [ ] T035 Alinear el script `test` de `package.json` (glob `'dev/__tests__/**/*.test.mjs'`, que requiere Node ≥ 21) con `engines.node >=20` y con `dev/README.md`: subir `engines` a `>=21` y documentarlo, o usar un comando de test compatible con Node 20, per plan: stack Node ≥ 20 / `node --test` (partial)
