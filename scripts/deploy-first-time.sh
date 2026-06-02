#!/bin/bash
# deploy-first-time.sh — Solo se corre UNA VEZ en el servidor.
# Obtiene el certificado SSL y luego levanta todo.

set -e

DOMAIN="hilo.esjuanez.com"
EMAIL="tu-email@dominio.com"   # <-- cambiar por tu email real

echo "=== 1. Levantando Nginx en modo solo-HTTP para validar dominio ==="
# Nginx temporal sin HTTPS (ssl_certificate no existe aún)
docker compose up -d nginx

echo "=== 2. Solicitando certificado Let's Encrypt ==="
docker compose run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email "$EMAIL" \
  --agree-tos \
  --no-eff-email \
  -d "$DOMAIN"

echo "=== 3. Habilitando HTTPS en Nginx ==="
docker compose restart nginx

echo "=== 4. Levantando servicios completos ==="
docker compose up -d

echo "=== Listo. Verificar en https://$DOMAIN ==="
