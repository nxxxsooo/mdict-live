# Stage 1: Build React SPA
FROM node:22-alpine AS frontend
WORKDIR /app/website
COPY website/package.json website/package-lock.json ./
RUN npm ci
COPY website/ ./
RUN npm run build

# Stage 2: Python runtime
FROM python:3.11-alpine

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MDICT_CONFIG_FILE=/app/flask_mdict.json \
    MDICT_V2_ENABLED=true \
    MDICT_LIBRARY_DIR=/library \
    MDICT_DATA_DIR=/data \
    MDICT_INDEX_DIR=/data/index \
    MDICT_CONFIG_DIR=/config \
    MDICT_LIVE_TOKEN_FILE=/run/secrets/mdict_live_token

# Copy Flask source
COPY flask-mdict /app

# Remove all plugin files except __init__.py
RUN rm -f flask_mdict/plugins/[!__]*.py

# Remove 'translators' from requirements.txt to prevent installation
RUN sed -i '/translators/d' requirements.txt
# Keep only the LZO runtime in the final image. The compiler toolchain is
# needed to build python-lzo, then removed in the same layer.
RUN apk add --no-cache lzo && \
    apk add --no-cache --virtual .build-deps lzo-dev build-base && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir valkey 'gunicorn>=23,<24' && \
    apk del .build-deps

# Copy built SPA from stage 1
# app.py resolves SPA at ../website/dist relative to flask-mdict dir
COPY --from=frontend /app/website/dist /website/dist

# Keep source dictionaries read-only and every generated artifact under the
# persistent writable data/config mounts.
RUN addgroup -g 1000 mdict-live && \
    adduser -D -u 1000 -G mdict-live mdict-live && \
    mkdir -p /library /data/index /config && \
    chown -R mdict-live:mdict-live /data /config

USER mdict-live

# Expose the default port
EXPOSE 5248

# Readiness stays minimal and unauthenticated; it does not expose source data.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD wget -qO- http://127.0.0.1:5248/health/ready >/dev/null || exit 1

# One process owns the in-memory source catalog and bounded lookup executor;
# threads provide request concurrency without duplicating those resources.
CMD ["gunicorn", "--bind", "0.0.0.0:5248", "--workers", "1", "--threads", "8", "--timeout", "120", "wsgi:application"]
