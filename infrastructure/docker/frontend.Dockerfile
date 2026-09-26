# ------------------------------------------------------------------------------
# Production Multi-Stage Dockerfile for AI Trading Engine React Frontend
# ------------------------------------------------------------------------------

# --- Stage 1: Build Production Assets ---
FROM node:22-alpine AS builder

WORKDIR /app

# Install dependencies using clean install
COPY frontend/package*.json ./
RUN npm ci

# Copy frontend source and build optimized bundle
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Production Nginx Server ---
FROM nginx:alpine AS runtime

LABEL maintainer="Sujal Shreshya" \
      project="AI Trading Engine" \
      version="0.1.0"

# Remove default static pages
RUN rm -rf /usr/share/nginx/html/*

# Copy compiled frontend assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy production Nginx reverse proxy configuration
COPY infrastructure/nginx/nginx.conf /etc/nginx/conf.d/default.conf

# Expose standard HTTP port
EXPOSE 80

# Health check probing Nginx local server
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -q --spider http://127.0.0.1/ || exit 1

# Start Nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
