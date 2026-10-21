# Circuit — Production reference

How Circuit runs outside a laptop. If this file and CLAUDE.md disagree on
infrastructure, this file wins.

---

## 1. Architecture at a glance

| Layer | Choice | Notes |
|---|---|---|
| Landing site | Next.js (apps/landing) on Vercel | Static, SEO, own domain, no login |
| App | Next.js (apps/app) on Vercel | PWA, Supabase sign-in, calls the API |
| API | Django 5 + Django Ninja on Cloud Run, asia-south1 | Stateless, autoscaling, min instances ≥ 1 in prod |
| Admin | Django admin on the same service | Staff login + TOTP 2FA; super admins only; not in demo |
| Background jobs | Django management commands as Cloud Run Jobs + Cloud Scheduler | compute_matches, run_circuit_round, expire_items (every 15 min), cleanup |
| Database | Supabase Postgres + PostGIS + pgvector | Source of truth; connect via the pooler |
| Auth | Supabase Auth | Google + email OTP; JWT verified in Django via JWKS |
| Files | Supabase Storage | `avatars` (public), `private` (reports, exports) |
| Realtime | Supabase Realtime | Notifications, circuit status; RLS-scoped |
| Cache + rate limits | Redis (Upstash) | Disposable; Postgres fallback |
| Graph | Recursive SQL + networkx (core/graph) | Neo4j only if a BACKLOG.md trigger is hit |
| Secrets | Google Secret Manager | Never in repo or frontend |
| Images | Artifact Registry | Built by CI |
| CI/CD | GitHub Actions | Temporary staging key until Stage 9, then Workload Identity Federation |
| Errors | Sentry (backend + app) | PII scrubbed, releases + source maps |
| Logs | Cloud Logging (structlog JSON) | Request IDs end to end |
| Uptime | Better Stack or UptimeRobot | Alerts reach a phone |
| Email | Resend (or Postmark) | Test sender until the domain is verified |
| LLM | core/llm, LLM_PROVIDER = gemini, groq or anthropic | Free tier in dev/demo/staging; paid, no-training tier in production; monthly cap |

Request path: browser → Vercel (app) → API (Cloud Run) → Redis → Postgres (Supabase).
The landing site only links to the app; it never calls private API endpoints.

---

## 2. Environments

`ENV` is one of `dev`, `demo`, `staging`, `production`.

| | dev | demo | staging | production |
|---|---|---|---|---|
| Purpose | Building | Investor/partner demos | Testing releases | Real users |
| Where | Laptop (docker compose) | Cloud Run + Vercel | Cloud Run + Vercel (+ PR previews) | Cloud Run + Vercel |
| Supabase | Local Postgres | Free project | Free project | Pro (backups + PITR) |
| Redis | Local container | Upstash | Upstash | Upstash (paid) |
| Data | Seed + demo stories | Seed + demo stories only; reset nightly and on demand | Seed + test accounts; never real users' data | Real users only |
| Login | DEMO_AUTH personas | DEMO_AUTH personas (DEMO_PUBLIC=true) + Supabase | Supabase only | Supabase only; DEMO_AUTH impossible |
| Django admin | On | Off | On (staff + 2FA) | On (staff + 2FA) |
| Email | Console | Disabled | Test sender to team inboxes | Real sender |
| Search engines | n/a | noindex | noindex | Landing indexed; app noindex except public pages |
| Deploy | Manual | Manual, from a release tag | Auto on merge to main | Manual approval after staging passes |
| Banner | "Dev" | "Demo — sample data" | "Staging" | none |

Rules:
- Each environment has its own keys, database, Redis, buckets and OAuth redirect URLs.
  No environment reads another's data. Real user data exists only in production.
- Settings are validated at startup; a missing variable means the app refuses to start.
- The app refuses to start with DEMO_AUTH=true when ENV is staging or production.
- Demo runs the same code as production (a release tag), with demo config and data.
- `.env.example` documents every variable, with a note per environment.

## 2a. Domains and URLs (one place to change)

Nothing hard-codes a domain. Until the domain is bought, every environment uses its
platform default URL (`*.vercel.app`, `*.run.app`).

| Variable | Used for | Before domain | After domain (production) |
|---|---|---|---|
| `LANDING_URL` | Landing site origin, links from app/emails | `https://circuit-landing.vercel.app` | `https://<domain>` |
| `APP_URL` | App origin, email links, auth redirects | `https://circuit-app-<env>.vercel.app` | `https://app.<domain>` |
| `API_URL` | App API base, CSP connect-src | `https://<service>-<hash>.a.run.app` | `https://api.<domain>` |
| `CORS_ALLOWED_ORIGINS` | Exact origins allowed by the API | `APP_URL` (+ `http://localhost:3000` in dev) | `APP_URL` only |
| `CORS_PREVIEW_REGEX` | Vercel PR previews (staging only) | `^https://circuit-app-staging-git-.*\.vercel\.app$` | empty |
| `CSRF_TRUSTED_ORIGINS` | Django admin form posts | API origin | `https://api.<domain>` |
| `ALLOWED_HOSTS` | Django host check | `.run.app` host | `api.<domain>` |
| `EMAIL_FROM` | Sender | Provider test sender | `Circuit <hello@<domain>>` |
| `SUPPORT_EMAIL` | Footer, legal pages | Team inbox | `support@<domain>` |
| `SUPABASE_URL` | Auth, storage, realtime | Per-env project URL | Production project URL |

Frontend build-time variables (set per Vercel project): `NEXT_PUBLIC_APP_URL`,
`NEXT_PUBLIC_LANDING_URL`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`,
`NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_ENV`.

Switching to the real domain (config only, ~1 hour plus DNS wait):
1. [YOU] Vercel: add `<domain>` to the landing project and `app.<domain>` to the
   production app project; set DNS; wait for HTTPS.
2. [YOU] API: map `api.<domain>` to Cloud Run (domain mapping, or a load balancer if
   mapping isn't available in asia-south1); set DNS; wait for the certificate.
3. Update the §2a variables in Vercel and Cloud Run / Secret Manager.
4. Supabase Auth: Site URL = `APP_URL`; redirect URLs = `APP_URL/auth/callback` (+ staging,
   demo and `http://localhost:3000/auth/callback`).
5. Google OAuth client: add `APP_URL` to authorised JavaScript origins.
6. Email: verify the domain (SPF, DKIM, DMARC), then switch `EMAIL_FROM`.
7. Redeploy; run `make smoke URL=<APP_URL>`.

## 3. Security baseline
- Supabase JWT verified on every request (signature, expiry, audience, pinned algorithm).
- Permission helpers + org scoping on every endpoint; IDOR tests for every ID parameter.
- RLS on every table (deny by default); service role key only in the backend.
- Django admin: staff only, TOTP 2FA required, non-obvious path, disabled in demo,
  all actions audit-logged. Django's security settings on (SECURE_*, HSTS, secure cookies).
- Rate limits (Redis): onboarding extraction, intros, applications, reports, claims.
- Rate limits: `core.ratelimit.check_rate(member_id, action)` with limits in `settings.RATE_LIMITS`
  (extraction, intro, application, report, claim, org_join). Redis first; Postgres fallback if Redis is down.
- CORS: exact origins only. Headers: CSP, HSTS, nosniff, Referrer-Policy, frame-ancestors.
- Input validation (Ninja schemas), request size limits, upload type/size checks.
- No personal data in logs or analytics (tested).
- Dependabot + secret scanning; 2FA on GitHub, GCP, Supabase, Vercel, Upstash.

### 3a. Database roles and RLS
- Django connects as the **table owner** (the pooler URL's user). Owners bypass RLS, so the app is the only
  writer. Never `FORCE ROW LEVEL SECURITY`, or the app would lock itself out.
- Every table in `public` has RLS enabled with **no policies** (`core/rls.py`, run by migration `core.0002`
  and again after every `migrate`). Supabase's `anon` and `authenticated` roles (PostgREST, Realtime) therefore
  read nothing. When Stage 6 adds Realtime, add narrow per-table SELECT policies for `authenticated`; never a blanket one.
- The Supabase service-role key exists only in the backend's Secret Manager; never in Vercel or the repo.
- Supabase Auth must use **asymmetric JWT signing keys** (ES256 default, or RS256 via `SUPABASE_JWT_ALG`). The
  API pins that algorithm and rejects HS256 tokens, so projects still on the legacy shared secret will not work.
- Supabase Auth settings that auto-join relies on: only Google + email OTP enabled, password sign-up off,
  "Confirm email" on. The API trusts the `email` claim only for those providers and ignores `user_metadata`.
- `/api/docs` and `/api/openapi.json` are not served when `ENV=production`.
- Defence in depth behind RLS: migration `core.0003` revokes all table/sequence privileges from `anon` and
  `authenticated` (and from future tables). Stage 6 Realtime must `GRANT SELECT` per table, plus a policy, on purpose.
- Outside `dev`, `migrate` fails if any `public` table still lacks RLS (e.g. owned by a different role).
- Demo is internet-facing, so it gets the same settings as staging/production: HTTPS redirect, HSTS, secure
  cookies, DEBUG off, a random 32+ character `SECRET_KEY` (demo tokens are signed with a key derived from it).
- `SUPABASE_URL` must be `https://` outside dev (the signing keys are downloaded from it). Signing keys are cached
  10 minutes and, if Supabase is unreachable, trusted for at most 6 hours.
- Known limit: Supabase access tokens stay valid until they expire (about 1 hour) even after sign-out or a ban.

## 4. Roles and data access

| Role | Sees |
|---|---|
| student | Map, jobs, own matches and applications, "skills in demand" card |
| founder / mentor / investor | Own matches, intros, circuits; founders see own startup stats |
| partner_admin | Dashboard scoped to their organisation; opted-in members list |
| super_admin | Django admin: everything, audit-logged |

Aggregates hide counts under 5. Heatmaps use neighbourhood-sized cells.

## 5. Privacy and legal (India, DPDP Act)
- Privacy policy, terms, cookie notice before real users; lawyer-reviewed.
- Consent stored with policy version + timestamp.
- Under-18 students: hidden profile by default; no messages from strangers.
- Data requests: export, correction, deletion (deletes or anonymises).
- Retention: events (pseudonymous, kept), request logs (30 days), unverified accounts
  (purged after 30 days).
- Processors listed: Supabase, Google Cloud, Vercel, the active LLM provider, Resend, Sentry, Upstash.

## 6. Data safety
- Production: Supabase daily backups + point-in-time recovery; restore drill to staging
  before launch, then quarterly.
- Django migrations: reviewed, backwards-compatible (expand then contract), tested on a
  staging copy.
- Redis is rebuildable from Postgres (`manage.py rebuild_cache`).

## 7. Reliability
- `/api/health` (process) and `/api/health/deps` (Postgres, Redis, Supabase JWKS).
- Timeouts + retries + fallbacks on every external call.
- Jobs idempotent, retry-limited, alert on failure.
- Expiry: `expire_items` job every 15 min, and reads treat past-deadline items as expired.
- Supabase pooler; Django CONN_MAX_AGE and pool size × max instances under the limit.

## 8. Observability and alerts

| Signal | Tool | Alert when |
|---|---|---|
| Errors | Sentry | New error type or error spike |
| Uptime | Uptime monitor | Landing, app, API or sign-in down > 2 min |
| Latency | Cloud Monitoring | API p95 > 1s for 10 min |
| Jobs | Cloud Monitoring + logs | Any job fails twice in a row |
| Cost | GCP budget, Supabase, Anthropic limits | 50%, 80%, 100% of budget |

## 9. Performance targets
- API p95 < 300ms for cached reads, < 800ms otherwise.
- App initial JS < ~250KB gzipped; Lighthouse ≥ 90 mobile on landing and app Home.
- Load test ~1,000 concurrent users on staging before public launch.

## 10. Deploy and release
1. Pull request → CI: ruff, mypy, pytest (unit, API, demo), tsc, ESLint, Playwright, axe.
2. Merge to main → build image → migrate staging → deploy staging → `make smoke`.
3. Release tag → deploy demo → `make reset-demo ENV=demo`.
4. Manual approval → migrate production → deploy production → smoke → done.
5. Rollback: previous Cloud Run revision + previous Vercel deployment (RUNBOOK.md).

## 11. Cost guardrails (check current pricing)
- Fixed: Supabase Pro (production), domain, Vercel Pro if needed.
- Usage: Cloud Run, Upstash, Anthropic API, Resend.
- Budget alerts on every paid service from day one.

## 12. Launch stages
1. Closed beta: 10–20 known students and founders (LAUNCH.md Stages 1–6).
2. Pilot college: one partner, ~150 verified local startups, 30–50 claimed.
3. Public launch: after pilot metrics are healthy and the load test passes.

## 13. Pilot metrics
- Landing visit → sign-up → onboarding complete → first match → first action
- Intro acceptance (local vs bridge); circuits proposed / activated / completed
- Startups claimed, roles posted, applications, shortlists
- Weekly active users; 4-week retention
