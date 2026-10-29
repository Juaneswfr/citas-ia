# Multi-stage: build SSR dentro del container
# Actualizar: git pull + docker compose up --build frontend
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm install --legacy-peer-deps

# .env debe existir en el server (VITE_* se inlinan en el bundle del cliente)
COPY . .
RUN npm run build

# ── Runtime: solo el output de Nitro ───────────────────────────────────────
FROM node:20-alpine

WORKDIR /app
COPY --from=build /app/dist ./dist

EXPOSE 3000

CMD ["node", "dist/server/index.mjs"]
