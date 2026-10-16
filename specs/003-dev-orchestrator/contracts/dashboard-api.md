# Contract: Dashboard de estado

Base: `http://127.0.0.1:${DEV_DASHBOARD_PORT:-4300}` — solo loopback, solo lectura, sin autenticación (justificado en plan.md, Principio XI).

## GET /

`200 text/html`. Muestra por servicio nombre, puerto y estado; hace polling a `/api/status` cada 2 s.

## GET /api/status

`200 application/json`

```json
{
  "services": [
    { "name": "frontend", "port": 5173, "state": "up",           "checkedAt": "2026-10-16T12:00:00.000Z" },
    { "name": "backend",  "port": 8000, "state": "down",         "checkedAt": "2026-10-16T12:00:00.000Z" },
    { "name": "agent",    "port": 8123, "state": "not-included", "checkedAt": "2026-10-16T12:00:00.000Z" }
  ],
  "generatedAt": "2026-10-16T12:00:00.000Z"
}
```

- `state` ∈ `up | down | not-included`.
- Nunca incluye env, secretos, rutas, comandos ni logs.
- Sirve el último resultado en caché; no espera comprobaciones.

## Otros métodos y rutas

- `HEAD` permitido en las rutas anteriores.
- `POST|PUT|PATCH|DELETE|OPTIONS` → `405` con `Allow: GET, HEAD`.
- Ruta desconocida → `404 {"error":"not found"}`.
- Error interno → `500 {"error":"internal error"}` sin stack.

## Cabeceras

`Cache-Control: no-store`, `X-Content-Type-Options: nosniff`; `X-Powered-By` deshabilitado.
