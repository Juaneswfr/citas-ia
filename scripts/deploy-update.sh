#!/bin/bash
# deploy-update.sh — Para deployar nuevas versiones del código.
set -e

echo "=== Actualizando código ==="
git pull

echo "=== Rebuilding imágenes ==="
docker compose build --no-cache frontend backend

echo "=== Reiniciando servicios (zero-downtime: nginx sigue vivo) ==="
docker compose up -d --no-deps frontend backend

echo "=== Limpiando imágenes viejas ==="
docker image prune -f

echo "=== Deploy completado ==="
docker compose ps
