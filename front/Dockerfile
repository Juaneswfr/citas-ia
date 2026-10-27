# Frontend pre-compilado localmente con: npm run build
# El build genera dist/client/ — se sirve como SPA estática via nginx
FROM nginx:alpine

COPY dist/client /usr/share/nginx/html

# Configuración SPA: todas las rutas sirven index.html
RUN printf 'server {\n  listen 3000;\n  root /usr/share/nginx/html;\n  index index.html;\n  location / {\n    try_files $uri $uri/ /index.html;\n  }\n}\n' \
    > /etc/nginx/conf.d/default.conf

EXPOSE 3000
