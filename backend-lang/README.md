# Backend (citas-ia)

FastAPI + SQLAlchemy + Postgres. Corre con Docker Compose desde la raíz del repo.

## Configuración

1. Copia la plantilla y rellena los valores:
   ```
   cp backend-lang/.env.example backend-lang/.env
   ```
2. `backend-lang/.env` **nunca** se commitea (está en `.gitignore`).
3. Docker Compose carga ese archivo con `env_file` en el servicio `backend`, así que las variables llegan al contenedor sin cambios en `docker-compose.yml`.

## Kapso (WhatsApp)

Con `KAPSO_ENABLED=false` (valor por defecto) las rutas de Kapso responden 404 y no se hace ninguna llamada a Kapso.

Para activarlo hacen falta:
- `KAPSO_API_KEY`: clave del proyecto Kapso. **Rótala antes de usarla** si alguna vez estuvo en el repo.
- `KAPSO_WEBHOOK_SECRET_PROJECT`: secreto del webhook de proyecto (eventos de conexión).
- `KAPSO_SECRETS_KEY`: clave Fernet (base64 urlsafe de 32 bytes) que cifra el secreto del webhook de cada número. Cada canal recibe su propio webhook (`/webhooks/kapso/n/{token}`) al llegar `whatsapp.phone_number.created`; la URL base sale de `FRONTEND_URL`.
- `KAPSO_WEBHOOK_SECRET_NUMBER`: obsoleto (solo compatibilidad en `/webhooks/kapso`).
- `KAPSO_BASE_URL`: opcional, por defecto `https://api.kapso.ai`.

Con `KAPSO_ENABLED=true` el arranque exige `KAPSO_API_KEY`, `KAPSO_WEBHOOK_SECRET_PROJECT` y `KAPSO_SECRETS_KEY`.

## Tests

```
cd backend-lang
PYTHONPATH=src uv run --group dev python -m pytest -q
```

Los tests de migraciones contra Postgres real solo corren con `TEST_DATABASE_URL` apuntando a una base **desechable**: recrean los esquemas `public` y `auth`.
