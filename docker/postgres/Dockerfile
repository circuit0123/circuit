# Local Postgres with PostGIS and pgvector. PG_MAJOR is 16 for the dev database (what Supabase runs today); the restore drill builds the
# same image with PG_MAJOR=17 so its pg_restore is never older than the pg_dump in the backend image (docker-compose.yml, restore-db).
ARG PG_MAJOR=16
FROM postgres:${PG_MAJOR}
ARG PG_MAJOR
RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql-${PG_MAJOR}-postgis-3 postgresql-${PG_MAJOR}-pgvector \
 && rm -rf /var/lib/apt/lists/*
