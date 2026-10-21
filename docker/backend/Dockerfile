# Multi-arch (ARM64 + x86_64): only Debian packages and pure/wheel Python deps.
FROM python:3.12-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends gdal-bin libgdal-dev libgeos-dev libproj-dev \
 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/ ./
ENV PATH="/app/backend/.venv/bin:$PATH" PYTHONUNBUFFERED=1
# Stage 5: needs a production server (gunicorn is not on the approved list yet; ask first).
CMD ["python", "manage.py", "check"]
