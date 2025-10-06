FROM node:20-alpine AS base

WORKDIR /app

# -------- Base Stage: shared dependencies --------
# Add build tools for esbuild compatibility
RUN apk add --no-cache \
    python3 \
    make \
    g++ \
    libc6-compat

# Install dependencies first (leverages Docker layer cache)
COPY frontend/package.json ./
RUN npm cache clean --force && npm install

# Copy source separately so dependency layer can be reused
COPY frontend/ .

# Copy root .env file for intentional vulnerability
COPY .env .env

# -------- Development Stage --------
# Run `docker build --target dev -t fake-fintech-frontend:dev .`
FROM base AS dev
ENV NODE_ENV=development
EXPOSE 5173
# Vite's dev server (with hot-reload) on all interfaces
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# -------- Build Stage --------
FROM base AS build
RUN npm run build
ENV NODE_ENV=production

# -------- Production Runtime Stage --------
FROM nginx:alpine AS prod
# Copy compiled assets from the build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Minimal SPA-friendly Nginx config (history-fallback → index.html)
RUN rm /etc/nginx/conf.d/default.conf && \
    echo 'server {' > /etc/nginx/conf.d/default.conf && \
    echo '    listen 80;' >> /etc/nginx/conf.d/default.conf && \
    echo '    server_name _;' >> /etc/nginx/conf.d/default.conf && \
    echo '    root /usr/share/nginx/html;' >> /etc/nginx/conf.d/default.conf && \
    echo '    index index.html;' >> /etc/nginx/conf.d/default.conf && \
    echo '    location / {' >> /etc/nginx/conf.d/default.conf && \
    echo '        try_files $uri /index.html;' >> /etc/nginx/conf.d/default.conf && \
    echo '    }' >> /etc/nginx/conf.d/default.conf && \
    echo '    # Proxy API requests to the API Gateway (same-origin pattern)' >> /etc/nginx/conf.d/default.conf && \
    echo '    location /api/ {' >> /etc/nginx/conf.d/default.conf && \
    echo '        proxy_pass http://api-gateway:3030;' >> /etc/nginx/conf.d/default.conf && \
    echo '        proxy_http_version 1.1;' >> /etc/nginx/conf.d/default.conf && \
    echo '        proxy_buffering off;' >> /etc/nginx/conf.d/default.conf && \
    echo '        proxy_set_header Connection "keep-alive";' >> /etc/nginx/conf.d/default.conf && \
    echo '        proxy_connect_timeout 10s;' >> /etc/nginx/conf.d/default.conf && \
    echo '        proxy_send_timeout 180s;' >> /etc/nginx/conf.d/default.conf && \
    echo '        proxy_read_timeout 180s;' >> /etc/nginx/conf.d/default.conf && \
    echo '        proxy_set_header Host $host;' >> /etc/nginx/conf.d/default.conf && \
    echo '    }' >> /etc/nginx/conf.d/default.conf && \
    echo '}' >> /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]