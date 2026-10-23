# Circuit — engineering guide

Read this every session. It says WHAT Circuit is and HOW we build it.
- PRODUCTION.md: how it runs in production (infra, security, ops). Wins on infra questions.
- LAUNCH.md: the staged checklist. Do the stage(s) named in the session prompt only.
- BACKLOG.md: work after launch. Never build from it unless it's pulled into a stage.
- PROGRESS.md: current status. Create it in Stage 0; update it at the end of every session.
- DESIGN.md: visual and writing rules. Create it in Stage 4 before building screens.

## Product
Circuit is a startup ecosystem platform for India, starting with one pilot city and one
partner college.

Differentiator: we match people on what they NEED and what they can OFFER, not on sector
or job titles. That enables cross-sector "bridge" matches, warm intros and 3-person
exchange circuits, plus a map of who is hiring nearby.

Users:
- Students (often tier 2/3 colleges): find nearby hiring startups and jobs, matched on
  skills and proof of work, not college name.
- Founders, mentors, investors: matches with reasons, warm intros, exchange circuits.
- Partner admins (colleges, incubators): dashboard of their own organisation's gaps.
- Super admins (Circuit team, 2–3 people): verification, moderation, data review.

## Features (current scope)
F1  Smart onboarding: paste a bio → LLM suggests needs, offers, capabilities, traits from
    OUR FIXED LISTS ONLY → user confirms with chips. Manual pickers if the LLM fails.
F2  Startup map: filters (hiring, capability, distance), pins by hiring status, popup with
    match %, open roles, "I'm interested".
F3  Unclaimed startup profiles + claim flow (verify via company email domain). Shows
    student views/interest to motivate claiming. Claimed data is never overwritten.
F4  Matches with one-line reasons; "Bridge match" badge for cross-sector matches.
F5  Warm intros via the best mutual connection (1–2 hops); weekly capacity limits.
F6  Exchange circuits: weekly round + super-admin "Run round now". 3-person loops,
    weakest-link score, CP-SAT selection, 72h consent, live status, mark done, rating.
F7  Verification levels 1–3 as badges (1 email, 2 work email/LinkedIn, 3 admin-verified).
F8  Partner dashboard: gap chart + heatmap, network stats, local vs bridge acceptance.
    Scoped to the partner's organisation; counts under 5 hidden.
F9  Demo mode (dev and demo environments only): persona switcher + `make reset-demo`.
F10 Logging + events: one JSON log line per request; append-only events table.
F11 Jobs and applications: list, filters, job page with skill match, one-click apply,
    statuses, founder applicant view ranked by skill match.
F12 Account basics: sign-up/onboarding, settings, export, delete, notifications
    (in-app + email), report/block, help/FAQ, legal pages.
F13 Admin: Django admin for super admins (verify members, moderate reports, review
    crawled startups, takedowns, run circuit round, metrics), every action audit-logged.
F14 Landing site: separate public marketing site (own domain) explaining Circuit for
    students, founders and partners, linking into the app. Never calls private APIs.
F15 Build logs + Pulse: members post up to 4 images + 500 chars + up to 3 capability
    tags + optional link, visibility Everyone / Connections / My organisation. Pulse
    feed (chronological, last 7 days, ends with "You're caught up") mixes build logs,
    nearby matching roles and system activity. Reactions Helpful / Intro me / Let's
    talk (no public counts); one-level replies. Every post reportable; moderated in
    Django admin.
F16 Daily Drop + Today strip: 3 matches per day at 08:00 local time as a swipeable
    stack; Today strip of connections/followed startups/org who posted in 24h.
F17 Connections, follows and Inbox: connect (with note) to people, follow startups;
    1-to-1 messages via Supabase Realtime; Requests folder for non-connections;
    under-18 students receive no Requests from strangers.
DESIGN.md defines every screen, component, motion and healthy-habit rule for these.

## Repo layout (one monorepo)
```
backend/                 Django project (Python, uv)
  circuit/               settings (per ENV), urls, asgi/wsgi
  apps/                  accounts, organisations, startups, jobs, matching, intros,
                         circuits, dashboard, notifications, moderation, events,
                         social (posts, reactions, replies, follows, daily drop),
                         messaging
  core/                  auth (Supabase JWT), permissions, cache/, graph/, embeddings/,
                         llm/, logging, errors, pagination
  tests/                 unit, api, demo (story tests), eval (matching pairs)
apps/landing/            Next.js marketing site (static)
apps/app/                Next.js product app (PWA)
packages/ui/             shared design components and tokens
packages/api-client/     TypeScript client generated from the backend OpenAPI spec
docker/                  Dockerfiles (backend, postgres with PostGIS + pgvector)
docs: CLAUDE.md PRODUCTION.md LAUNCH.md BACKLOG.md PROGRESS.md DESIGN.md RUNBOOK.md
```
JavaScript workspace: pnpm workspaces (no other monorepo tool).

## Stack
Backend
- Python 3.12, uv; Django 5 + Django Ninja (typed endpoints, OpenAPI at /api/openapi.json)
- PostgreSQL 16 + PostGIS (GeoDjango) + pgvector (pgvector-python Django support); psycopg 3
- Django migrations (the only way schema changes)
- Redis client behind core/cache (cache + rate limits); fakeredis in tests
- fastembed (BAAI/bge-small-en-v1.5, 384 dims) behind an EmbeddingProvider, plus a
  deterministic fake provider for tests
- LLM behind core/llm with a provider setting (LLM_PROVIDER = gemini | groq | anthropic),
  used for onboarding extraction (later the crawler). Output is always validated against
  a strict schema; invalid output falls back to manual pickers. Free tiers allowed in
  dev, demo and staging only; production uses a paid tier whose terms exclude training
  on our data.
- networkx (cycles), OR-Tools CP-SAT (circuit selection)
- structlog JSON logs; pytest + pytest-django
- Background work = Django management commands, run as Cloud Run Jobs in staging/prod

Frontend
- Next.js (App Router) + TypeScript + Tailwind in both apps; shared packages/ui
- apps/landing: statically rendered, SEO metadata, no login
- apps/app: client-rendered product screens, PWA, MapLibre GL (OpenStreetMap tiles),
  Recharts, TanStack Query + packages/api-client (no hand-written fetch calls),
  Supabase JS only for auth, storage uploads and realtime

Approved supporting libraries (no need to ask):
- Backend: google-genai (Gemini), groq, anthropic (one active via LLM_PROVIDER),
  PyJWT[crypto] (JWKS), django-otp (admin 2FA), redis, fakeredis (tests),
  httpx, sentry-sdk, resend, django-environ or pydantic-settings (pick one), ruff, mypy,
  pillow (image checks and resize variants)
- Frontend: @supabase/supabase-js, @tanstack/react-query, @tanstack/react-virtual,
  openapi-typescript, openapi-fetch, motion (animations), lucide-react (icons), geist (font),
  maplibre-gl, recharts, serwist (PWA, Stage 10), @playwright/test, @axe-core/playwright,
  @sentry/nextjs, eslint, prettier

Infra: PRODUCTION.md. Four environments (dev, demo, staging, production) via ENV.
Local dev: docker compose (Postgres with PostGIS + pgvector, Redis). Every image must
work on ARM64 and x86_64. No hard-coded domains: all URLs come from config
(PRODUCTION.md §2a).

Graph queries (warm paths, circuits, 2nd-degree network) use recursive SQL + networkx
behind core/graph. Neo4j is NOT in scope (trigger in BACKLOG.md).

## Architecture rules
- Postgres is the only source of truth. Redis is disposable: if down, read from
  Postgres and log a warning.
- Ninja routers are thin; business logic lives in each app's services.py. React
  components stay thin; data logic lives in hooks.
- Heavy work (matching, circuit rounds, bulk LLM, crawling) never runs in a request;
  it runs as management commands/jobs and users read precomputed results.
- Every external call has a timeout, retries with backoff and a graceful fallback.
- Jobs and important endpoints are idempotent.
- One way to do each thing: one error format, one pagination style, one logging setup.

## Auth and access
- Users sign in with Supabase Auth (Google first, email OTP backup). We never store
  user passwords.
- A Ninja auth class verifies Supabase JWTs via JWKS (signature, expiry, audience,
  pinned algorithm) and loads the Member by auth_user_id.
- members is the source of truth for role, verification_level, organisation_id.
- Roles: student, founder, mentor, investor, partner_admin, super_admin.
- Permission helpers (require_role, require_level, org scoping) on every endpoint; IDOR tests.
- RLS enabled on every table (deny by default); the app's DB role is the only writer;
  the Supabase service role key exists only in the backend.
- Django admin: separate staff login for super admins only (Django staff users with
  mandatory TOTP 2FA via django-otp), served at a non-obvious path, never in demo.
  This is the only place passwords exist, and they are Django-hashed.
- DEMO_AUTH issues persona tokens in dev and demo only. The app refuses to start with
  DEMO_AUTH=true when ENV is staging or production.

## Data model (Postgres)
- members: id, auth_user_id (unique), role, display_name, bio, location (point), city,
  college, organisation_id (nullable), verification_level, open_intro_slots,
  circuits_opt_in, is_minor, profile_visibility, visible_to_org, suspended_at, pulse_seen_at, created_at, updated_at
- organisations: id, name, kind (college | incubator | program), city, email_domains,
  join_code, created_by. A member belongs to at most one organisation. Super admins
  create organisations and appoint the first partner_admin. Members join via invite
  code/link, or automatically after verifying an email on one of the org's domains.
  Partner admins can remove members; members can leave. Partner admins see aggregates
  over their own members only, plus members with visible_to_org = true.
- startups: id, name, website_domain (unique), description, sector, stage, address,
  location, hiring, tech_stack (json), claimed_by (member), source (seed | crawler | user),
  confidence, view_count, created_at
- startup_members; jobs; job_capabilities; applications (unique per student per job)
- capabilities (40–80), traits (20–30); needs; offers (embedding vector(384))
- member_traits, startup_traits, member_skills
- connections; intro_requests; match_results (score, components json, reason, is_bridge)
- circuits; circuit_legs (giver, receiver, capability, consent, fulfilled, rating)
- notifications; reports; blocks; audit_log; consents (policy_version, accepted_at)
- posts (author, body, link, visibility, capability tags, status: visible | hidden |
  removed), media_uploads (owner, purpose post | message, path, status pending | ready,
  width, height: an image can only be attached by its owner, once), post_media (post,
  upload, alt_text, order),
  reactions (post, member, kind; unique per member+post+kind), replies (post, author,
  body, parent nullable one level)
- follows (member → startup); connections (above) for people; connection_requests
  (sender, recipient, note, status pending | accepted | declined); daily_drops (member,
  date, candidate list); story_views (viewer, author or startup, date, viewed_at)
- conversations (two members, status: request | active | blocked), messages
  (conversation, sender, body, image, created_at, read_at, removed_at)
- events (append-only: actor, type, target_type, target_id, payload, created_at)
GIST indexes on locations, HNSW on embeddings, indexes on every foreign key.

## Matching (v1, rule-based)
- Candidates: local (same city, shared traits, 1–2 hop connections) + bridge (whole
  pool, need-to-offer on capability + embedding similarity, ignoring sector).
- score = w1*complementarity + w2*affinity + w3*trust_path + w4*timing - w5*load_penalty
  Complementarity both directions. Weights in settings. Pure, unit-tested functions.
- Ranking: diversity, capacity caps, ~25% bridge share. Students: distance is a hard filter.
- Precomputed by `manage.py compute_matches` into match_results, cached in Redis.
- Eval set (tests/eval/pairs.json) + `manage.py eval_matching`; scoring changes must not
  lower agreement.

## Privacy and safety
- Never log or send to analytics: names, emails, phones, tokens.
- Under-18 students: hidden profile by default, no messages from strangers.
- Aggregates hide counts under 5; heatmaps use coarse cells.
- Super-admin actions audit-logged.
- Crawling (later): company data only, robots.txt respected, takedown form.

## Seed data and demo stories
Configurable city centre (lat/lng in env). ~150 startups, ~300 members (mostly
students), realistic Indian names, places, roles and stipends. `manage.py reset_demo`
is idempotent. It must contain these five stories:
1. A biotech startup needing marketing, matched to a deep-tech marketer as a Bridge
   match (shared traits: long sales cycle, technical buyers).
2. A circuit: Asha needs marketing, Priya needs fundraising, Arjun needs hiring.
3. A tier-3-college student matched on skills to a nearby hiring startup, applies to its
   internship, and is the founder's top-ranked applicant.
4. A warm intro path through a respected mentor.
5. A visible regulatory-help gap on the partner dashboard.

## Testing
- Unit (scoring, reasons, circuits on known graphs, auth, logging), API (every endpoint:
  one success + at least one failure, IDOR, rate limits, events), demo story tests
  (tests/demo/), Playwright end-to-end for the app at 375px and 1280px, axe checks.
- Tests use a fresh seeded test database, the fake embedding provider, fakeredis and a
  mocked LLM. No live network calls in tests.
- `make check` runs everything and prints PASS/FAIL per demo story.
- `make smoke URL=...` checks a deployed environment. Never deploy on red.

## How to work with me
- I'm learning. Explain what you built and why in plain language.
- Work only on the LAUNCH.md stage(s) named in the session prompt, on its own branch.
- Write tests as you build. Never finish with failing tests.
- At the end: tick LAUNCH.md boxes, update PROGRESS.md, commit, summarise, stop for my OK.
- Approved dependencies are the ones listed in this file. Ask before adding any other.
- Ask before breaking schema changes or deleting data.
- Never commit secrets. .env is gitignored; .env.example documents every variable.
- Keep it simple. Prefer deleting code to adding abstraction.
