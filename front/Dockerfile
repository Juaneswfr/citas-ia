# Runtime solamente: el build (npm run build) se hace fuera del servidor y se sube ./front/dist.
# docker-compose.yml monta ./front/dist en /app/dist, así que actualizar el front es copiar dist y
# `docker compose restart frontend`: no hay build ni rebuild de imagen en el VPS.
FROM node:20-alpine

WORKDIR /app

EXPOSE 3000

CMD ["node", "dist/server/index.mjs"]
