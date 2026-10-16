# Quickstart: validación del orquestador

**Prerrequisitos**: Node ≥ 20, `uv`, `npm install` en `front-app/`, `uv sync` en `backend-lang/`, `backend-lang/.env` presente.

## 1. Instalar y probar

```bash
npm install     # raíz: instala express
npm test        # node --test: health, exit-event, logger, supervisor, dashboard
```

Esperado: todas las pruebas pasan.

## 2. Arranque (US1)

```bash
npm run dev       # frontend + backend
npm run dev:all   # + agente (8123)
```

Esperado: líneas con prefijo `[frontend]`, `[backend]` (y `[agent]`) en colores distintos; `curl -I localhost:5173` y `curl localhost:8000/` responden en < 60 s.

## 3. Dashboard (US4)

```bash
curl -s http://127.0.0.1:4300/api/status
curl -i -X POST http://127.0.0.1:4300/api/status   # 405
ss -ltn | grep 4300                                 # 127.0.0.1, no 0.0.0.0
```

Esperado: JSON según [contracts/dashboard-api.md](./contracts/dashboard-api.md); con `npm run dev`, `agent` = `not-included`.

## 4. Cascada (US2)

`pkill -f uvicorn` desde otra terminal. Esperado: mensaje `backend terminó…`, los demás servicios se detienen en < 10 s, `echo $?` ≠ 0.

## 5. Apagado limpio (US3)

Ctrl+C. Esperado: `ss -ltn | grep -E '5173|8000|8123|4300'` vacío y `pgrep -f "vite|uvicorn|langgraph"` vacío. Repetir 10 veces (SC-005).

## 6. No regresión (US5)

```bash
git status --short front-app backend-lang nginx docker-compose.yml   # vacío
docker compose config                                                # idéntico al previo
```
