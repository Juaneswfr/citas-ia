from dotenv import load_dotenv
load_dotenv()

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from api.routes.auth import router as auth_router
from api.routes.workspaces import router as workspaces_router
from api.routes.services import router as services_router
from api.routes.appointments import router as appointments_router
from api.routes.channels import router as channels_router
from api.routes.conversations import router as conversations_router
from api.routes.billing import router as billing_router
from api.routes.webhooks import router as webhooks_router

log = logging.getLogger(__name__)

# ── Rate Limiter (Principio VII + SC-007) ────────────────────────────────────
# Usa la IP del cliente como clave por defecto.
# El endpoint de webhook usa workspace_id como clave (definido en webhooks.py).
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("[startup] CitasIA API iniciando")

    # T038: Iniciar scheduler de recordatorios en background
    from workers.reminder_worker import start_reminder_scheduler
    reminder_task = start_reminder_scheduler()

    yield

    # Shutdown limpio
    reminder_task.cancel()
    try:
        await reminder_task
    except Exception:
        pass
    log.info("[shutdown] CitasIA API detenida")


app = FastAPI(
    title="CitasIA API",
    description="Backend del SaaS de agendamiento por WhatsApp.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiter middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(auth_router)
app.include_router(workspaces_router)
app.include_router(services_router)
app.include_router(appointments_router)
app.include_router(channels_router)
app.include_router(conversations_router)
app.include_router(billing_router)
app.include_router(webhooks_router)


@app.get("/", tags=["health"])
def health():
    return {"status": "ok", "service": "citas-ia"}
