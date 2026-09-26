# ------------------------------------------------------------------------------
# Production Multi-Stage Dockerfile for AI Trading Engine Backend
# ------------------------------------------------------------------------------

# --- Stage 1: Build & Dependencies ---
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy package metadata and install Python dependencies
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir .

# --- Stage 2: Production Runtime ---
FROM python:3.12-slim AS runtime

LABEL maintainer="Sujal Shreshya" \
      project="AI Trading Engine" \
      version="0.1.0"

# Install curl for healthcheck and libpq for PostgreSQL runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root user (UID 10001) for strict least-privilege security
RUN groupadd -g 10001 trader && \
    useradd -u 10001 -g trader -m -s /bin/bash trader

WORKDIR /app

# Copy virtualenv from builder stage
COPY --from=builder --chown=trader:trader /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy backend application source code
COPY --chown=trader:trader backend/ /app/backend/
COPY --chown=trader:trader pyproject.toml /app/

# Switch to non-root trader user
USER trader

# Expose FastAPI application port
EXPOSE 8000

# Health check using live probe endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

# Launch production ASGI server
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--log-level", "info"]
