# Multi-stage: build SSR dentro del container
# Actualizar: git pull + docker compose up --build frontend
FROM oven/bun:1-alpine AS build

WORKDIR /app

COPY package.json bun.lock ./
RUN bun install

# .env debe existir en el server (VITE_* se inlinan en el bundle del cliente)
COPY . .
RUN bun run build

# ── Runtime: solo el output de Nitro ───────────────────────────────────────
FROM node:20-alpine

WORKDIR /app
COPY --from=build /app/dist ./dist

EXPOSE 3000

CMD ["node", "dist/server/index.mjs"]
