# Circuit — Progress

Branch: `backend-core` (LAUNCH.md Stages 1–3, backend only)

## Status
- Stage 1 — Backend foundation: **done, awaiting OK** (make check green: ruff, mypy, 23 tests; Django pinned to 5.2)
- Stage 2 — Auth and security: not started
- Stage 3 — Core features API: not started

## What exists (Stage 1)
- `backend/` Django 5 + Ninja; settings validated by pydantic (`circuit/config.py`), so a missing variable stops startup.
- 11 apps, all models from CLAUDE.md, migrations, GIST/HNSW/FK indexes, RLS on every table (`core/rls.py`), append-only `events` (DB trigger).
- 60 capabilities + 24 traits (data migration). `manage.py reset_demo`: 300 members, 150 startups, 66 jobs + the five stories; idempotent.
- Admin: TOTP-protected, audit-logged, not mounted in demo. `/api/health`, `/api/health/deps`.
- `core/`: cache, graph, embeddings (fastembed + fake), llm (groq/gemini/anthropic + fake), logging, errors, pagination.
- `packages/api-client/openapi.json` (regenerate with `make openapi`; a test fails if stale).

## Decisions / things to know
- Dev DB is `circuit_dev` (not `circuit`): the `circuit` database in the docker volume already held an older Circuit build (24 tables, 300 members). It was left as it was (I had briefly enabled RLS on it by mistake and reverted that).
- GDAL/GEOS/PROJ installed on the host; Django + pytest run on the host, Postgres + Redis in docker.
- No Supabase yet: dev uses DEMO_AUTH personas; tests will use a locally signed JWT. GROQ key empty, so onboarding uses manual pickers in dev.
- `MemberSkill`/`MemberTrait` live in `matching` (not `accounts`) to avoid a circular app dependency.
- `Need` also has an embedding (spec only says offers): bridge matching compares need text to offer text.
- Cache fallback: Redis errors act as a miss and log a warning; callers read Postgres. The Postgres fallback for rate limits arrives in Stage 2.
- `docker/backend/Dockerfile` is a placeholder (not built yet); it needs a production server (gunicorn) that is not on the approved list. Ask in Stage 5.
- Asked, not yet approved: `django-cors-headers` (Stage 2).
- `.env` got new dev defaults (EMBEDDING_PROVIDER=fake, ADMIN_PATH, LOG_LEVEL, DEMO_PUBLIC, SUPABASE_URL); `.env.example` documents all.

## Next
Stage 2 (auth, permissions, orgs, rate limits, CORS/headers, tests, finecomb audit).
