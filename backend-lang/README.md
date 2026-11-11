# Backend — CitasIA / Hilo

FastAPI + LangGraph + SQLAlchemy 2.0 async (asyncpg) sobre PostgreSQL. Agente de citas por WhatsApp.
En producción corre con Docker Compose desde la raíz del repo.

## Desarrollo local

```bash
cd backend-lang
uv sync
uv run fastapi dev ./src/api/main.py
```

## Configuración

1. Copia la plantilla y rellena los valores:
   ```
   cp backend-lang/.env.example backend-lang/.env
   ```
2. `backend-lang/.env` **nunca** se commitea (está en `.gitignore`).
3. Docker Compose carga ese archivo con `env_file` en el servicio `backend`.

Variables principales:

- `DATABASE_URL`, `JWT_SECRET`: obligatorias.
- `ANTHROPIC_API_KEY`: agente de citas y lectura de comprobantes (Claude Haiku 4.5).
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `GOOGLE_ENCRYPTION_KEY`: Google Calendar.
- `UPLOADS_DIR`: carpeta de comprobantes de pago. Por defecto `uploads`; en producción `docker-compose.yml` la fija a `/app/uploads` (volumen `./uploads` del host, hay que respaldarla).

## Kapso (WhatsApp)

Con `KAPSO_ENABLED=false` (valor por defecto) las rutas de Kapso responden 404 y no se hace ninguna llamada a Kapso.

Para activarlo hacen falta:
- `KAPSO_API_KEY`: clave del proyecto Kapso. **Rótala antes de usarla** si alguna vez estuvo en el repo.
- `KAPSO_WEBHOOK_SECRET_PROJECT`: secreto del webhook de proyecto (eventos de conexión).
- `KAPSO_SECRETS_KEY`: clave Fernet (base64 urlsafe de 32 bytes) que cifra el secreto del webhook de cada número. Cada canal recibe su propio webhook (`/webhooks/kapso/n/{token}`) al llegar `whatsapp.phone_number.created`; la URL base sale de `FRONTEND_URL`.
- `KAPSO_SANDBOX_WEBHOOK_SECRET`: secreto del webhook del número de pruebas (lo genera Kapso al configurarlo).
- `KAPSO_SANDBOX_PHONE_NUMBER_ID`: opcional, por defecto `597907523413541`.
- `KAPSO_WEBHOOK_SECRET_NUMBER`: obsoleto (solo compatibilidad en `/webhooks/kapso`).
- `KAPSO_BASE_URL`: opcional, por defecto `https://api.kapso.ai`.

Con `KAPSO_ENABLED=true` el arranque exige `KAPSO_API_KEY`, `KAPSO_WEBHOOK_SECRET_PROJECT` y `KAPSO_SECRETS_KEY`.

## Webhooks

| Endpoint | Origen | Función |
|----------|--------|---------|
| `POST /webhooks/kapso` | Kapso proyecto | Eventos de conexión (`phone_number.created/deleted`), no mensajes |
| `POST /webhooks/kapso/n/{token}` | Kapso por número | Mensajes entrantes (producción) |
| `POST /webhooks/kapso/sandbox` | Kapso sandbox | Mensajes entrantes (pruebas) |
| `GET /webhooks/whatsapp` | Meta | Verificación handshake |
| `POST /webhooks/whatsapp` | Meta | Mensajes directos (sin Kapso) |
| `POST /webhooks/google-calendar` | Google | Notificaciones de cambio |

## Flujo de un mensaje entrante

```
Mensaje de WhatsApp (Kapso)
  → webhook verifica la firma y delega en inbound_message_service
  → texto: ConversationService.find_or_create → AgentService.run → appointment_agent.run_agent
           (Claude Haiku 4.5, 6 tools) → respuesta por WhatsApp
  → imagen o documento: receipt_service.ingest (comprobante `pending`; lo aprueba un manager)
  → botón de plantilla: acción directa o texto para el agente
```

El agente necesita por workspace: servicios activos, Google Calendar conectado y canal de WhatsApp activo.
El worker de seguimientos (`workers/followup_worker.py`) corre dentro del proceso del API cada 10 minutos.

## Migraciones

SQL directo en `migrations/`, aplicado en orden:

```bash
uv run python migrate.py           # aplica pendientes
uv run python migrate.py --status  # ver estado (en Windows: PYTHONIOENCODING=utf-8)
```

## Tests

```
cd backend-lang
PYTHONPATH=src uv run --group dev python -m pytest -q
```

Hace falta `DATABASE_URL` en el entorno para importar `core.database` (sirve un valor ficticio).
Los tests de migraciones contra Postgres real solo corren con `TEST_DATABASE_URL` apuntando a una base **desechable**: recrean los esquemas `public` y `auth`.
