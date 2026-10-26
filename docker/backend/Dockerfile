# Backend image for Cloud Run (API, scheduled jobs and the migrate job all run this one image).
# Build from the repo root:  docker build -f docker/backend/Dockerfile .   (make build-api does it)
# Works on ARM64 and x86_64: only Debian packages and Python wheels. Cloud Run itself runs x86_64.

# ---- builder: has uv and the Python packages; none of this reaches the final image -----------------------------------------
FROM python:3.12-slim-trixie AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /usr/local/bin/uv
# collectstatic imports GeoDjango, which loads the GDAL and GEOS libraries (same packages as the runtime stage below).
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgdal36 libgeos-c1t64 \
 && rm -rf /var/lib/apt/lists/*
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app/backend

# Dependencies first, so editing code does not reinstall them (Docker layer cache).
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

# The embedding model (bge-small, ~130 MB) is baked in. Cloud Run's disk is memory and starts empty on every cold start, so
# downloading it at run time would add seconds to the first request and fail when the download host is down.
ENV FASTEMBED_CACHE_PATH=/app/models
RUN .venv/bin/python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"

COPY backend/ ./

# The admin's CSS/JS. collectstatic loads the settings, so it gets throw-away values (ENV=demo is the lightest deployed
# setting). Nothing here is a real secret and none of it is kept in the final image.
RUN ENV=demo SECRET_KEY=build-only-0123456789-abcdefghijklmnopqrstuvwxyz DATABASE_URL=postgres://u:p@localhost/db \
    REDIS_URL=redis://localhost:6379/0 ALLOWED_HOSTS=build.invalid CORS_ALLOWED_ORIGINS=https://app.invalid \
    APP_URL=https://app.invalid LANDING_URL=https://www.invalid API_URL=https://api.invalid \
    SEED_CITY_NAME=Build SEED_CITY_LAT=0 SEED_CITY_LNG=0 \
    .venv/bin/python manage.py collectstatic --noinput

# ---- runtime: only what is needed to run --------------------------------------------------------------------------------
FROM python:3.12-slim-trixie
# libgdal36 + libgeos-c1t64: GeoDjango (PostGIS). libgomp1: LightGBM's OpenMP runtime (train_ranker, compute_matches).
# postgresql-client-17 (pg_dump; version 17 can dump Supabase's Postgres 15-17) + age: the nightly encrypted backup (core/backup.py).
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgdal36 libgeos-c1t64 libgomp1 postgresql-client-17 age \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin circuit

# Application files belong to root and are read-only for the app user: a bug or an attacker inside the app cannot change the code.
COPY --from=builder /app/backend /app/backend
# The model folder is owned by the app user because the model loader wants to write small lock files next to the model.
COPY --from=builder --chown=circuit:circuit /app/models /app/models

WORKDIR /app/backend
ENV PATH="/app/backend/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=circuit.settings \
    FASTEMBED_CACHE_PATH=/app/models \
    PORT=8080
USER circuit
EXPOSE 8080

# Cloud Run ignores this and uses the probes in deploy/gcp/app.toml; it keeps `docker run` and run-prod-local honest.
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import os,sys,urllib.request as u; sys.exit(0 if u.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=2).status == 200 else 1)"]

# Migrations are NOT run here. They run as their own Cloud Run Job before a new revision gets traffic (scripts/gcp.py deploy).
# Jobs reuse this image with a different command (`python manage.py <job>`), set in deploy/gcp/app.toml.
CMD ["gunicorn", "-c", "circuit/gunicorn.py", "circuit.wsgi"]
