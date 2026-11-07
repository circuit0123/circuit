# Circuit — codebase analysis (Phase 1, read-only)

Generated 2026-11-07 on branch `main`. Nothing was modified except this file.
Method: three read-only explorers (backend, frontend, infra/secrets) using grep, AST and `git log -G`,
plus local `depcheck`, `pnpm typecheck`, `pnpm lint`, `ruff`, `mypy`. Paths are relative to the repo root.
No secret values appear below; secrets are reported by location only.

## 0. Corrections to the stack as you described it

| You said | What the code shows |
|---|---|
| Frontend at `app.circuitapp.net` | `deploy/gcp/production.toml:19` says `https://app.circuitapp.net`, but `vercel.json` serves the app under `/app` of a single Vercel project, and `PRODUCTION.md:77-90` still says `circuit-phi.vercel.app` + `/app`. **These three disagree.** Needs your decision (see §8). |
| Supabase Storage buckets avatars/posts/messages/private | Bucket names appear **nowhere in the frontend**; the backend (`backend/core/storage/`) chooses them. |
| Email: Resend | Yes, but via plain `httpx` POST in `backend/core/email.py:27`. The `resend` Python package is installed and never imported. |
| Deploy via `make deploy ENV=production` | Correct: Makefile:277 → `scripts/gcp.py deploy --env production`. Frontends are **not** deployed by any workflow; they rely on Vercel's Git integration. |

## 1. Folder tree

```
circuit/
├─ backend/                 Django 5 + Django Ninja API (Python 3.12, uv). Deployed to Cloud Run.
│  ├─ circuit/              Project package: config.py (pydantic-settings), settings.py, urls.py, api.py (NinjaAPI), asgi/wsgi, gunicorn.py
│  ├─ core/                 Shared code: auth (Supabase JWT + demo tokens), flags, jobs base, permissions, ratelimit, errors, health, email outbox, usage, backup, admin site (TOTP)
│  │  ├─ cache/             Redis wrapper with Postgres fallback and "lean" mode
│  │  ├─ embeddings/        fastembed or fake embedder
│  │  ├─ graph/             networkx trust-path helpers
│  │  ├─ llm/               provider switch: gemini | groq | anthropic | none | fake
│  │  ├─ storage/           local | Supabase storage, MemoryStorage for tests
│  │  ├─ templates/admin/   funnel.html admin page
│  │  ├─ management/commands/   13 ops commands
│  │  └─ migrations/        10 migrations
│  ├─ apps/                 accounts, beta, circuits, dashboard, events, intros, jobs, matching (+ ranker/), messaging, moderation, notifications, organisations, social, startups
│  ├─ seed/                 Demo seed data, personas, Pillow mock images
│  ├─ data/                 geocode_cache.json, startups_2026-10.csv
│  ├─ .media/               Dev-generated seed images (142 .webp, 3.6 MB) — TRACKED in git (see §7)
│  └─ tests/                unit (47 files), api (61), demo (6), contract (3), eval (data only: pairs.json, baseline.json)
├─ apps/
│  ├─ app/                  Next.js product app (PWA-style, client-rendered). Served under /app on Vercel.
│  │  ├─ src/app/           App Router: (shell)/ signed-in screens; auth/callback; join; design (dev only)
│  │  ├─ src/components/    Screens by feature (circuits, compose, discover, home, inbox, jobs, notifications, onboarding, posts, profile, settings, startups) + shell files
│  │  ├─ src/data/          The only layer that calls the API: TanStack Query hooks, client.ts, supabase.ts, session.tsx, realtime.ts
│  │  ├─ src/data/mocks/    MSW mock mode (handlers, fixtures, mock Supabase auth, 26 scenarios)
│  │  ├─ src/lib, src/hooks Helpers (env, format, image, upload), useDesktop
│  │  ├─ e2e/               Playwright against the real API (needs backend on :8000)
│  │  ├─ tests/             Playwright on mock mode (~300 tests) + boundary.test.mjs
│  │  └─ public/            Icons, mockServiceWorker.js
│  └─ landing/              Next.js marketing site, static export (`output: "export"`)
│     ├─ src/app/           /, /students /founders /mentors /investors /partners, /privacy /terms, sitemap, robots
│     ├─ src/components, src/content, src/lib   Sections, copy, env/flags/waitlist helpers
│     ├─ e2e/               Playwright (builds the site 4 ways on :3101–3104)
│     ├─ public/            brand/, screens/ (11 phone shots), og.png
│     ├─ out/, .out-after/, .out-before/   Build output — TRACKED despite .gitignore (§7)
│     └─ screenshots/       48 tracked files (remove-old-steps) (§7)
├─ packages/
│  ├─ ui/                   Shared components + tokens.css; consumed as source (no build)
│  └─ api-client/           openapi-fetch client; src/schema.d.ts generated from openapi.json; fixtures/ (67 contract fixtures)
├─ docker/
│  ├─ backend/Dockerfile    Two-stage Python 3.12 + uv, bakes fastembed model, gunicorn :8080, non-root
│  └─ postgres/Dockerfile   Postgres 16 + PostGIS + pgvector
├─ docker-compose.yml       Local db, redis, restore-db (profile "drill")
├─ deploy/gcp/              app.toml (service + jobs + secret names), production/staging/demo.toml, backup-lifecycle.json
├─ infra/monitoring/        Cloud Monitoring templates: 7 alerts, 4 metrics, 3 uptime checks (applied by scripts/gcp_monitoring.py)
├─ scripts/                 gcp.py (deploy/setup/rollback), gcp_monitoring.py, smoke.py, check_api_freeze.py, doctor.sh, restore_drill.py, landing-screens.mjs, serve-static.mjs
├─ .github/                 ci.yml, deploy.yml (reusable), deploy-{production,staging,demo}.yml, dependabot.yml
├─ docs/                    brand/ (416K), design-reference/ (31 *.dc.html mocks), legal/ (terms, privacy, cookies, …)
├─ screenshots/             449 tracked files, 37 MB — per-stage review shots (3 test helpers write here)
├─ .claude/                 settings.json, agents/test-runner.md
├─ Makefile                 Every command (297 lines)
└─ *.md                     CLAUDE, PRODUCTION, LAUNCH, BACKLOG, PROGRESS (234K), DESIGN, RUNBOOK, COMMANDS, FRONTEND_HANDOFF, AUDIT, PROMPTS, README
```

How each part is built/run/deployed:
- **Backend**: `make api` locally (docker compose db+redis). Deploy: `make deploy ENV=production` → `scripts/gcp.py` merges `app.toml` + `production.toml`, builds an amd64 image, runs the `migrate` Cloud Run Job, deploys a 0%-traffic revision, smoke-tests it, shifts traffic, rolls back on failure, then updates jobs + Cloud Scheduler. GitHub path: `deploy-production.yml` → `deploy.yml` (requires a green `ci` on main — currently impossible, §9).
- **Frontends**: `pnpm` workspaces. Vercel builds both from `vercel.json` (`/app/(.*)` → app, everything else → landing). No workflow deploys them.

## 2. Entry points

### 2a. Backend endpoints (145 Ninja operations, 13 public)
Mounted at `/api/` (`backend/circuit/urls.py:8`, `backend/circuit/api.py:30`). Default auth is `SupabaseAuth`. OpenAPI/docs are disabled in production (`api.py:34-35`). "App?" = called by a hook in `apps/app/src/data`.

| Method | Path | Handler | Auth / flag | App? |
|---|---|---|---|---|
| GET/PATCH | /me | accounts/api.py:94,105 | default | yes |
| PUT/DELETE | /me/photo | accounts/api.py:172,184 | default | yes |
| PUT | /me/highlights | accounts/api.py:154 | default | **no** |
| GET | /capabilities | accounts/api.py:208 | default | yes |
| GET | /traits | accounts/api.py:213 | default | **no** |
| GET/PUT | /me/needs, /me/offers, /me/skills | accounts/api.py:245–291 | default | yes |
| GET | /me/traits | accounts/api.py:296 | default | **no** |
| PUT | /me/traits | accounts/api.py:307 | default | yes |
| GET | /members/{id} | accounts/api.py:372 | default | yes |
| POST | /onboarding/extract | accounts/api.py:410 | default, rate-limited | yes |
| POST | /me/verify/work-email (+/confirm) | accounts/api.py:436,448 | default | yes |
| GET/PATCH | /onboarding/state | accounts/onboarding_api.py:47,59 | default | yes |
| GET/POST | /me/export, GET /me/export/download | accounts/privacy_api.py:47–69 | default | yes |
| POST | /me/deletion | accounts/privacy_api.py:82 | default | yes |
| POST | /support | accounts/privacy_api.py:94 | default | yes |
| GET | /support/contact | accounts/privacy_api.py:106 | **public** | no |
| GET | /me/settings | accounts/settings_api.py:196 | default | yes |
| PATCH | /me/privacy, /me/appearance, /me/notification-preferences | settings_api.py:208–237 | default | yes |
| POST | /me/consent | settings_api.py:250 | default | yes |
| POST | /beta/redeem | beta/api.py:31 | default, rate-limited | yes |
| GET | /invites | beta/api.py:55 | default | **no** |
| POST | /waitlist | beta/api.py:81 | **public**, IP limit | yes (landing + app) |
| POST | /join/visit | beta/api.py:100 | **public** | yes |
| GET | /circuits | circuits/api.py:133 | flag `circuits` | yes |
| GET | /circuits/{id} | circuits/api.py:149 | flag `circuits` | **no** |
| POST | /circuits/{id}/respond, /legs/{leg}/done, /legs/{leg}/rating | circuits/api.py:164–192 | flag `circuits` | yes |
| GET | /dashboard/gaps, /heatmap, /network, /acceptance | dashboard/api.py:65–98 | org admin | **no** (F8 UI not built) |
| GET/POST | /intros/capacity, /intros/path/{id}, /intros, /intros/{id}/respond, /rating | intros/api.py:90–151 | default / NETWORK_ROLES | yes |
| GET | /jobs, /jobs/skills-in-demand, /jobs/{id} | jobs/api.py:100–131 | default | yes |
| POST/PATCH | /jobs, /jobs/{id} | jobs/api.py:142,156 | FOUNDER | **no** |
| POST | /jobs/{id}/apply, GET /me/applications | jobs/api.py:212,226 | STUDENT | yes |
| POST | /applications/{id}/withdraw | jobs/api.py:238 | STUDENT | **no** |
| GET | /jobs/{id}/applicants; PATCH /applications/{id} | jobs/api.py:251,281 | FOUNDER | yes |
| GET | /matches | matching/api.py:47 | default | yes |
| GET/POST | /conversations (+ unread-count, {id}, messages, accept, decline, block, read) | messaging/api.py:89–204 | default | yes |
| POST | /reports | moderation/api.py:34 | default | yes |
| GET/POST/DELETE | /me/blocks, /members/{id}/block | moderation/blocks_api.py:23–48 | default | yes |
| GET/POST | /notifications (+ unread-count, read-all, {id}/read) | notifications/api.py:116–148 | default | yes |
| GET/POST | /unsubscribe | notifications/unsubscribe_api.py:47,60 | **public** (signed token) | no — used by email links |
| GET | /organisations/search | organisations/api.py:62 | default | yes |
| POST | /organisations/join-by-email | organisations/api.py:95 | default | yes |
| GET/POST/DELETE | /organisations/mine, /join, /leave, /mine/members | organisations/api.py:69–128 | default / org admin | **no** |
| POST | /media/uploads, /media/uploads/{id}/complete | social/api.py:50,62 | default | yes |
| posts / reactions / replies / pulse / livewire (13 ops) | social/api.py:141–375 | flag `pulse` | yes |
| GET/POST | /drop/today, /drop/today/{id}/swipe | social/api.py:408,424 | flag `daily_drop` | yes |
| follows, connections (9 ops) | social/api.py:437–537 | default | yes |
| GET | /startups/nearby, /startups/map, /startups/{id} | startups/api.py:55–134 | default | yes |
| PATCH | /startups/{id}; PUT/DELETE /startups/{id}/logo | startups/api.py:145–176 | default | **no** |
| POST/DELETE | /startups/{id}/interest, /claim, /claim/verify | startups/api.py:189–234 | STUDENT / FOUNDER | yes |
| GET | /search | startups/search_api.py:30 | default | yes |
| GET | /cities | core/cities.py:47 | default | yes |
| GET | /config | core/config_api.py:41 | **public** | yes |
| GET/POST | /demo/personas, /demo/token | core/demo.py:43,49 | **public**, 404 unless DEMO_AUTH | yes |
| GET | /health, /health/deps | core/health.py:75,87 | **public** | no — ops/uptime checks |
| GET | /health/jobs | core/health.py:136 | SUPER_ADMIN | no |
| GET | /media/dev/{bucket}/{path} | core/media_dev.py:16 | public, only ENV=dev + local storage | n/a |

Plain Django: `GET/HEAD /health`, `/ready` (core/health.py:15-37, first middleware); Django admin at `settings.ADMIN_PATH` (not in demo); catch-all `api/*` → 404.

25 of 132 spec operations are not called by the app. Most are **not dead**: they back unbuilt screens (F8 dashboard, job posting, org admin), email links (`/unsubscribe`), or ops (`/health*`).

### 2b. Management commands (28)
`JobCommand` = flag check + DB lease + JSON logs. "Sched" = has a `[jobs.*]` entry in `deploy/gcp/app.toml`.

| Command | JobCommand | Sched | Notes |
|---|---|---|---|
| build_exports, delete_accounts, build_training_set† | Y, Y, N | Y, Y, N | †no Makefile target |
| reset_demo | Y | Y (demo only) | |
| retention_cleanup | Y | Y 03:00 | |
| run_circuit_round | Y (flag circuits) | Y Mon 09:00 | |
| compute_matches | Y | Y 07:30 | |
| train_ranker | Y | Y Sun 02:00 | |
| build_daily_drops, first_drops | Y (flag daily_drop) | Y | |
| backup_db | Y | Y (production only) | |
| check_jobs, expire_items, usage_report | Y | Y | expire_items help text says "every 15 min", runs every 5 |
| run_jobs | N | Y | runs the every-5-min bundle |
| delete_member, export_member, invite_codes, eval_matching, ranker_report, simulate_network, load_startups, admin_user, export_openapi, flags, funnel, job_health, load_test_tokens | N | N | manual / Makefile |

`app.toml` also lists `migrate` (Django built-in), and two **disabled** entries whose commands do not exist: `build_investor_picks` (:78), `reconcile_payments` (:116).

### 2c. Frontend routes
- **apps/app** (no `route.ts` files): `/` `/discover` `/inbox` `/profile` (shell tabs), `/circuits` (404 if flag off), `/compose` (404 if `pulse` off), `/discover/applications`, `/discover/jobs/[id]`, `/discover/jobs/[id]/applicants`, `/inbox/[id]`, `/inbox/new`, `/members/[id]`, `/posts/[id]`, `/startups/[id]`, `/notifications`, `/settings` + `/appearance /blocked /delete /export /help /notifications /privacy /profile /legal/[doc]`, `/auth/callback`, `/join`. **Dev only** (404 otherwise): `/design`, `/design/pager`, `/design/crash`.
- **apps/landing**: `/`, `/students`, `/founders`, `/mentors`, `/investors`, `/partners`, `/privacy`, `/terms`, `/sitemap.xml`, `/robots.txt`.

### 2d. Makefile targets (PROD = can touch cloud)
`help doctor setup dev api app landing landing-screens mock up down shell dbshell migrate migrations reset-demo(PROD with ENV=demo) admin-user invite-codes flags flag job jobs daily circuit-round retention export delete-account simulate train ranker-report eval test test-web test-landing e2e lint fmt check smoke load-test funnel api-freeze api-client openapi contract-fixtures build build-api build-api-multiarch build-web run-prod-local`.
**PROD-capable:** `logs` (cloud logs), `load-startups` (:95, prompts for the production DATABASE_URL and writes directly), `backup-now`, `usage-report`, `job-health`, `restore-drill` (reads prod backup bucket with ENV=production). **Always cloud:** `gcp-setup deploy rollback secret monitoring jobs-run`.

### 2e. CI / Docker / scripts
- Workflows: `ci.yml` (lint job: ruff, ruff format, mypy, api-freeze; check job: builds PostGIS image, `make check`), `deploy.yml` (reusable; verifies green ci, Workload Identity, builds, `gcp.py deploy`), `deploy-production.yml` (manual, approval-gated), `deploy-staging.yml` (needs `STAGING_DEPLOY_ENABLED`; always skipped), `deploy-demo.yml` (`v*` tags, needs `DEMO_DEPLOY_ENABLED`), `dependabot.yml`.
- Scripts: all referenced by Makefile/CI except `scripts/serve-static.mjs` (only used by `screenshots/landing-*.mjs`).

## 3. Feature → files

| Feature | Backend | Frontend | Models | Env vars |
|---|---|---|---|---|
| Sign-in (Google + email code) | `core/auth.py` (JWKS verify), `core/demo.py` | `components/SignIn.tsx`, `AuthCallback.tsx`, `data/auth.ts`, `data/supabase.ts`, `data/session.tsx` | Member | `NEXT_PUBLIC_SUPABASE_URL`, `_SUPABASE_ANON_KEY`, `_BASE_PATH`, `_ENV`; backend `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `DEMO_AUTH` |
| Beta invite gate / waitlist | `apps/beta/` | `Gate.tsx`, `onboarding/Invite.tsx`, `Consent.tsx`, `JoinRoute.tsx`, `data/gate.ts`, `access.ts`, `join.ts` | InviteCode, BetaAccess, WaitlistEntry, AllowlistEntry, JoinVisit | `BETA_MODE`, `INVITES_PER_MEMBER`, `NEXT_PUBLIC_API_URL` |
| Onboarding | `accounts/onboarding_api.py`, `core/llm/` | `components/onboarding/*` (12 steps), `data/onboarding.ts`, `where.ts`, `organisations.ts` | Member.onboarding, Need, Offer, MemberSkill, MemberTrait | `LLM_PROVIDER`, `LLM_DAILY_CALL_LIMIT`, provider keys |
| Profiles | `accounts/api.py`, `profile.py` | `components/profile/*`, `settings/EditProfile.tsx`, `data/profile.ts`, `me.ts`, `missing.ts` | Member, Highlight | — |
| Feed / Pulse / posts | `apps/social/` (pulse, livewire, drop) | `components/home/*`, `posts/PostScreen.tsx`, `compose/Composer.tsx`, `data/home.ts`, `posts.ts`, `compose.ts` | Post, PostMedia, Reaction, Reply, DailyDrop, UpdateView | flags `pulse`, `daily_drop` |
| Media upload | `social/api.py:50-62`, `social/media.py` (Pillow→webp), `core/storage/` (picks buckets) | `data/photo.ts`, `compose.ts`, `conversation.ts`, `lib/upload.ts`, `lib/image.ts` (flow: POST /media/uploads → PUT signed URL → /complete) | MediaUpload | `STORAGE_PROVIDER`, `MEDIA_WEBP_QUALITY` |
| Messaging | `apps/messaging/` (Realtime broadcast ping) | `components/inbox/*`, `data/inbox.ts`, `conversation.ts`, `realtime.ts` | Conversation, Message | Supabase vars |
| Map | `startups/api.py:66` (`/startups/map`) | `components/discover/MapView.tsx` (MapLibre + OSM) | Startup.location (PostGIS) | `NEXT_PUBLIC_MAP_TILES_URL` (undocumented in .env.example) |
| Startup directory / hiring | `apps/startups/`, `apps/jobs/` | `components/discover/*`, `startups/*`, `jobs/*`, `data/discover.ts`, `startups.ts`, `jobs.ts` | Startup (`hiring` field), Job, Application, ClaimRequest, StartupInterest | none. **Hiring is a data field, not a flag.** |
| Admin | `core/admin_site.py` (TOTP via django-otp), admin.py per app | — | all | `ADMIN_PATH` |
| Landing / waitlist | `beta/api.py:81` (POST /waitlist), landing CORS in `apps/beta/apps.py` | `apps/landing/src/components/{Waitlist,PartnerForm,CtaLink,AudiencePage}.tsx`, `lib/{waitlist,features,join,src}.ts` | WaitlistEntry | `NEXT_PUBLIC_APP_URL`, `_LANDING_URL`, `_API_URL`, `_LAUNCH_MODE`, `_WAITLIST_URL`, `_JOIN_LIVE`, `_CONTACT_EMAIL`, `_COMPANY_LEGAL_NAME` |
| Email (Resend) | `core/email.py` (outbox + httpx), `OutboundEmail` model, `send_emails` via `expire_items`/run_jobs | — | OutboundEmail | `EMAIL_BACKEND`, `RESEND_API_KEY`, `EMAIL_DAILY/MONTHLY_BUDGET` |
| Circuits / intros / matching | `apps/circuits`, `intros`, `matching` (+ `ranker/`) | `components/circuits/*`, `home/IntroSheet.tsx`, `data/circuits.ts`, `intros.ts` | CircuitRound, Circuit, CircuitLeg, IntroRequest, MatchResult, FeatureSnapshot, ModelVersion | flag `circuits` |

## 4. Feature flags and settings

Defined once in `backend/core/flags.py:20-28`; default `off` unless listed in `FEATURES` (`parse_features`, :36); admin overrides in `FeatureFlag` rows. Env values: `deploy/gcp/{production,staging,demo}.toml` (`FEATURES` at :40 / :37 / :36).

| Flag | Depends on | Production | Staging / demo | Backend code gated | Frontend |
|---|---|---|---|---|---|
| `pulse` | – | everyone | everyone | 13 social endpoints, profile-strength step, `post.*` notifications | New build log button, Pulse/Live wire, /compose, post lists (`BUILT` set in `data/features.ts`) |
| `daily_drop` | – | everyone | everyone | /drop endpoints, jobs `build_daily_drops`, `first_drops` | Daily Drop on Home |
| `circuits` | – | **testers** | everyone | 5 circuit endpoints, `circuit.*` notifications, job `run_circuit_round` | Circuits tab, /circuits |
| `investor_mode` | – | off | everyone | **nothing** | onboarding row never shows (not in `BUILT`); landing /investors form |
| `partner_mode` | – | off | everyone | **nothing** | same; landing /partners form |
| `promotions` | pulse | off | everyone | **nothing** (a "Stage 4d" comment at `startups/services.py:370`) | mock-only slots |
| `payments` | promotions | off | everyone | config check only: production needs `rzp_live_` key (`circuit/config.py:190`) | – |

Other toggles (`backend/circuit/config.py`):

| Setting | Default | Production | Gates |
|---|---|---|---|
| `BETA_MODE` | False | **true** | invite gate |
| `DEMO_AUTH` | False | false (app refuses true in staging/prod, :136) | persona tokens |
| `DEMO_PUBLIC` | False | unset | public demo personas |
| `LLM_PROVIDER` | groq | **none** (so onboarding paste-a-bio falls back to manual pickers) | LLM extraction |
| `EMAIL_BACKEND` | console | resend | email sending |
| `STORAGE_PROVIDER` | local | supabase | uploads |
| `REDIS_URL` / `REDIS_LEAN` | "" / False | unset / true | no Redis in beta; Postgres fallback |
| `DATABASE_POOLER` | direct | transaction | DB connection mode |
| `TRUSTED_PROXY_HOPS` | 0 | 1 | client IP for rate limits |
| `CORS_PREVIEW_REGEX` | "" | – | dev/staging only |

## 5. Dead / suspicious code (with evidence)

How checked: every backend module's dotted name and `from x import leaf` grepped across `apps core circuit seed Makefile deploy scripts` (every module has a production importer — **no orphan modules**); AST scan for public top-level names found nowhere else; frontend exports grepped with `grep -rnw` over `apps/app/src`, `apps/landing/src`, `tests`, `e2e`.

| Item | Evidence |
|---|---|
| `backend/apps/startups/services.py:375` `expire_claims()` | Only the definition and `tests/api/test_startups.py:300` reference it; `expire_items` does not call it (so pending claim requests never expire). **Bug-ish, not just dead.** |
| `backend/core/permissions.py:22` `require_level()` | Used only by `tests/unit/test_permissions.py` |
| Duplicate `_check_role` | `apps/circuits/api.py:120` and `apps/intros/api.py:78`, identical; `core.permissions.require_role` exists |
| `resend` Python dep | `grep "import resend"` → 0 hits; `core/email.py:27` uses httpx |
| `fakeredis` (main deps) | Imported only in `tests/conftest.py`, `test_flags.py`, `test_cache_lean.py` |
| `apps/app/src/components/home/MatchesSection.tsx` | `grep -rnw MatchesSection` → only its own definition |
| `useMatches` (`data/home.ts:179`) | Only caller is MatchesSection |
| `useStartConversation` (`data/inbox.ts:118`), `useProblem` (`data/errors.ts:28`) | 0 hits outside definition |
| `packages/ui`: `Tabs`, `Modal`, `toneFor` | Not imported anywhere (only their own file and `index.ts`) |
| `packages/ui`: `Card`, `HiringBadge`, `DistanceBadge`, `partnerTabs` | Used only by the `/design` gallery; `partnerTabs` links to `/dashboard` which has no route |
| 16 exported helpers (`toCircuitView`, `groupBubbles`, `inboxTime`, …) | Used only inside their own file; the `export` is unneeded |
| `packages/ui/assets/logo/*.svg` | Nothing imports them (`logo-paths.ts` holds copies); referenced only in `docs/brand/README.md` |
| Mock handlers with no hook | GET `/circuits/:id`, GET `/support/contact`, GET `/traits` in `data/mocks/` |
| `apps/app/src/data/gate.ts:14` | Comment mentions an `/onboarding` route that doesn't exist |
| `scripts/serve-static.mjs` | Only used by `screenshots/landing-*.mjs` |
| `backend/.media/` | 142 tracked `.webp` (3.6 MB); `.gitignore` only has `/backend/.backups/` |
| Tracked build output | `apps/landing/out` (39 files), `.out-after` (80), `.out-before` (79) — all in `.gitignore` yet tracked |
| `apps/landing/screenshots/remove-old-steps` | 48 tracked files, nothing references them |
| `screenshots/` | 449 files / 37 MB; referenced by PROGRESS.md (13 mentions) and 3 test helpers that write into it (`apps/app/e2e/helpers.ts:7`, `tests/premium.spec.ts:16`, `tests/signup-helpers.ts:6`) |
| Commented-out code / `print` / `pdb` / TODO | None found in backend (one "HOOK FOR STAGE 4d" comment) |
| Code behind OFF flags | `investor_mode`, `partner_mode`, `promotions`, `payments` gate **no backend code**; only disabled job entries and mock stand-ins in `data/missing.ts` |
| depcheck | `apps/app`, `apps/landing`: flags `tailwindcss`, `@tailwindcss/postcss` as unused — **false positives** (used by `postcss.config.mjs` / `globals.css`). `apps/landing`: `@types/react-dom` genuinely unreferenced. `packages/*`: clean. |

## 6. Candidates to remove

| Path | Why | Evidence | Risk |
|---|---|---|---|
| `apps/landing/out/`, `.out-after/`, `.out-before/` | Tracked build output | In `.gitignore`; `git ls-files` lists 198 files | low |
| `apps/landing/screenshots/remove-old-steps/` | Leftover review shots | 48 files, no references | low |
| `backend/.media/` | Generated seed media | 142 .webp; regenerated by seed (confirm with `make reset-demo`) | low (verify seed regenerates) |
| `apps/app/src/components/home/MatchesSection.tsx` + `useMatches` | Never imported | grep, §5 | low |
| `useStartConversation`, `useProblem` | No callers | grep, §5 | low |
| `Tabs`, `Modal`, `toneFor` in `packages/ui` | No importers | grep, §5 | low |
| `resend` in `backend/pyproject.toml` | Never imported | grep, §5 | low |
| `fakeredis` | Move to dev group, not delete | tests only | low |
| `@types/react-dom` in `apps/landing` | depcheck | verify `tsc` still passes | low |
| `scripts/serve-static.mjs` | Only used by screenshots scripts | grep | low (goes with `screenshots/`) |
| `screenshots/` (37 MB) | Historical review shots | PROGRESS.md mentions; 3 test helpers write there | **med** — helpers need repointing; your memory note says screenshots go here |
| `packages/ui/assets/logo/*.svg` | Unused copies | only docs README | med |
| `require_level()` | Tests-only | CLAUDE.md lists it as a required helper | med |
| duplicate `_check_role` | Replace with `require_role` | behaviour must stay identical | med |
| `app.toml` jobs `build_investor_picks`, `reconcile_payments` | Commands don't exist | disabled entries | med — a test may expect them |
| Unused exports (`export` keyword) | Cosmetic | §5 | low, little value |
| Uncalled endpoints (25) | **Do not remove** | back unbuilt screens, email links, ops | high |
| OFF-flag code, `data/missing.ts` stand-ins | **Do not remove** unless you approve per flag | – | high |

## 7. Keep, but needs attention

1. **CI has never been green**: 0 successes in the last 30 `ci` runs (28 failed, 2 cancelled); the latest two (runs 40640820887, 40561624699) failed with a mypy INTERNAL ERROR. Locally `mypy .` passes (231 files) and `ruff` passes, so this is likely a CI-environment/cache/version issue. Because `deploy.yml`'s `verify` job needs a green `ci`, **no GitHub-based deploy can currently run.**
2. **App URL mismatch**: `production.toml:19` (`app.circuitapp.net`) vs `vercel.json` (`/app` path) vs `PRODUCTION.md:77-90` (`circuit-phi.vercel.app`). Also `vercel.json` rewrites `/app/(.*)`, which probably doesn't match a bare `/app` (unverified).
3. `expire_claims()` is never scheduled (see §5).
4. `_check_role` is applied unevenly: circuits only on list/get; intros only on list/rate. Probably covered by participant checks in services; worth confirming.
5. `partnerTabs` links to `/dashboard`, which doesn't exist; the dashboard endpoints are unused until that UI exists.
6. `.env.example` is missing `NEXT_PUBLIC_MAP_TILES_URL`, `NEXT_PUBLIC_APP_VERSION`, `NEXT_PUBLIC_MOCK`.
7. `production.toml` hard-codes `circuitapp.net` in 6 places (:19,20,26,28,33,34); CLAUDE.md says no hard-coded domains. Also `tests/unit/test_deploy_config.py:585,586,598`.
8. `staging.toml` / `demo.toml` still contain `<your-gcp-project-id>` placeholders; `deploy-staging.yml` is always skipped.
9. Stage-named test files that may overlap: `test_logging_pii.py` vs `test_logging_pii_b3.py`, `test_b7_*`, `test_audit_stage2.py`.
10. `job_health` and `check_jobs` wrap the same `core/jobhealth` (intentional, overlapping).
11. `expire_items` help text says 15 min; schedule is every 5.
12. CI does not run `next build` for `apps/app`, nor `apps/app/e2e` against the real API.
13. `data/missing.ts` mock stand-ins ship in the production bundle (inert unless `MOCK`).
14. `make load-startups` can write straight to the production DB (prompts for the URL) — keep, but note it.
15. `packages/ui/src/tokens.css` assumes Tailwind is loaded but doesn't declare it.

## 8. Secrets (locations only — no values)

- **Working tree**: no real credentials found. `.env` exists locally but is **not tracked** (`.gitignore:1`). `.env.example` has all secrets empty; `SECRET_KEY` (:6) is a dev placeholder, `DATABASE_URL` (:7) is the local dev DB.
- **Git history (232 commits)**: gitleaks/trufflehog not installed, so searched with `git log -p --all -G`. No `.env`, `.pem`, `.key` or credentials file was ever committed (only `.env.example`, commit e89aeb9). No hits for Razorpay, Resend, Groq, Anthropic, Google, GitHub, AWS keys, full JWTs, PEM keys, non-empty service-role key or `otpauth` secrets.
- **Harmless pattern hits (placeholders/test fakes)**: `postgres://` in `.env.example:7`, `RUNBOOK.md:27`, `backend/core/backup.py:81`, `docker/backend/Dockerfile:28` (build-only), and tests (`test_backup.py:24,55`, `test_startup_checks.py:142-184`, `test_config.py:9`, `test_deploy_config.py:489`, `test_audit_stage2.py:32`); fake age key `test_backup.py:44`; short fake JWTs `test_job_health.py:21,73`, `test_sentry_scrub.py:9`; `otpauth://` docs `COMMANDS.md:63`, `RUNBOOK.md:97`.
- **Sensitive but not secret, in a PUBLIC repo (`circuit0123/circuit`)** — worth acting on:
  - `deploy/gcp/production.toml:23` — the real `ADMIN_PATH` (added in commit 5c6397f). The admin URL's obscurity is its only hiding; it still needs the staff password + TOTP, but treat the path as exposed. Rotate it and keep the new value in Secret Manager or an uncommitted override.
  - `deploy/gcp/production.toml:7` — GCP billing account ID.
  - `deploy/gcp/production.toml:24` (Supabase project ref) and `:27-29` (grievance officer name/address) are meant to be public.
- I did not run any command that prints values.

## 9. Tests and CI

| Area | Count | Result today |
|---|---|---|
| Backend `tests/unit` | 47 files, ~607 tests | **not run** (Docker has no containers running; I didn't start any) |
| `tests/api` | 61 files, ~873 | not run |
| `tests/demo` (stories 1–5) | 6 files, ~15 | not run |
| `tests/contract` | 3 files, ~13 | not run |
| `tests/eval` | data only (`pairs.json`, `baseline.json`) | used by `test_eval_matching.py` |
| `apps/app/tests` (mock Playwright) | 14 specs, ~300 | not run |
| `apps/app/e2e` (real API) | 2 specs, 12 | not run; no package script, only `make e2e` |
| `apps/app/tests/boundary.test.mjs` | 5 | not run |
| `apps/landing/e2e` | 10 specs, ~76 | not run |
| `packages/*` | none | – |

Ran locally (read-only): `pnpm typecheck` ✅ (4 projects), `pnpm lint` ✅, `ruff check` ✅, `mypy .` ✅ (231 files), `depcheck` (see §5). `git status` was clean before this file.
Missing: unit tests for `packages/*`; `next build` in CI; real-API e2e in CI; a passing CI run.

## 10. Counts used for the later before/after comparison

- Tracked files: 1844 (backend 576, apps 553, screenshots 449, packages 137, docs 70).
- Endpoint baseline: 145 Ninja operations (132 in `openapi.json`/`schema.d.ts` after dedup; 109 paths). Phase 4 compares against `packages/api-client/openapi.json`.
