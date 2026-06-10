# ── Stage 1: dependencias ─────────────────────────────────────────────────────
FROM python:3.12-slim AS deps

WORKDIR /app

# uv para gestión de paquetes (más rápido que pip)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
# --no-install-project: instala solo las dependencias, no el paquete local
# (src/ todavía no fue copiado en este stage)
RUN uv sync --frozen --no-dev --no-install-project

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY --from=deps /app/.venv .venv

# Copiar código fuente
COPY src/ ./src/

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
