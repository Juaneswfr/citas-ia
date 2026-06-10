# Imagen mínima: solo Python + dependencias
# El código fuente se monta como volumen desde el host
# Actualizar código: git pull + docker compose restart backend
# Rebuild solo si cambia pyproject.toml o uv.lock (nuevas dependencias)
FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN mkdir -p src && uv sync --frozen --no-dev --no-install-project

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
