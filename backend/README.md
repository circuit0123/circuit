# backend

Django 5 + Django Ninja API (Python 3.12, managed with `uv`). Postgres 16 with PostGIS and pgvector, Redis optional.
Deployed to Google Cloud Run (asia-south1); scheduled work runs as Cloud Run Jobs.

| Folder | What it is |
|---|---|
| `circuit/` | Project package: `config.py` (env settings), `settings.py`, `urls.py`, `api.py` (the NinjaAPI) |
| `core/` | Shared code: auth, feature flags, jobs base class, permissions, rate limits, email, storage, LLM, cache |
| `apps/` | One folder per domain: accounts, beta, circuits, dashboard, events, intros, jobs, matching, messaging, moderation, notifications, organisations, social, startups |
| `seed/`, `data/` | Demo data and the startup CSV |
| `tests/` | `unit`, `api`, `demo` (the five story tests), `contract`, `eval` |

## Run
From the repo root (needs Docker for Postgres and Redis):
```
cp .env.example .env
make setup      # install, start containers, migrate, load demo data
make api        # API on http://localhost:8000
```

## Test
```
make test       # pytest
make lint       # ruff, mypy, ESLint
make check      # everything, including the frontends
```
Tests use a fresh database, a fake embedder, fakeredis and a mocked LLM; no network calls.
Every command a human runs is a `make` target: see `COMMANDS.md`.
