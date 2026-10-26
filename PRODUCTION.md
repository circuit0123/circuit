# Circuit — Production reference

How Circuit runs outside a laptop. If this file and CLAUDE.md disagree on
infrastructure, this file wins.

---

## 1. Architecture at a glance

| Layer | Choice | Notes |
|---|---|---|
| Landing site | Next.js (apps/landing) on Vercel | Static, SEO, own domain, no login |
| App | Next.js (apps/app) on Vercel | PWA, Supabase sign-in, calls the API |
| API | Django 5 + Django Ninja on Cloud Run, asia-south1 | Stateless. gunicorn, 2 workers × 4 threads = 8 requests at once per instance. Min instances 0 during the closed beta (no cost while idle; the first request after a quiet spell takes ~5–10 s), max 3. Raise min to 1 (about $8–12/month) before public launch. Image: docker/backend/Dockerfile |
| Admin | Django admin on the same service | Staff login + TOTP 2FA; super admins only; not in demo |
| Background jobs | Django management commands as Cloud Run Jobs, started by Cloud Scheduler on India time | Schedule and settings: deploy/gcp/app.toml (`make jobs` lists it). The five frequent jobs (expire_items, send_emails, build_exports, delete_accounts, check_jobs) share one `every-5-min` job so the container starts once, not four times. Migrations are their own job, run before a new revision gets traffic |
| Database | Supabase Postgres + PostGIS + pgvector | Source of truth; connect via the pooler |
| Auth | Supabase Auth | Google + email OTP; JWT verified in Django via JWKS |
| Files | Supabase Storage | `avatars` (public), `private` (reports, exports) |
| Realtime | Supabase Realtime | Notifications, circuit status; RLS-scoped |
| Cache + rate limits | Redis (Upstash), free tier to start. Optional for the beta: with `REDIS_URL` empty production runs on Postgres alone (one startup warning) | Disposable; Postgres fallback. Free tier = 500K commands/month; pay-as-you-go is $0.20 per 100K commands. If the limit is hit the app reads Postgres, slower but correct |
| Graph | Recursive SQL + networkx (core/graph) | Neo4j only if a BACKLOG.md trigger is hit |
| Secrets | Google Secret Manager | Never in repo, image or frontend. One secret per value, mounted as an environment variable; only the API's own service account can read them (`make secret`) |
| Images | Artifact Registry (asia-south1) | Built by the deploy workflow (x86_64 and ARM64, tagged with the commit), or on your laptop by `make deploy`; the newest 5 are kept |
| CI/CD | GitHub Actions | CI on every pull request; deploys log in with Workload Identity Federation (no key). RUNBOOK.md "Deploy" |
| Errors | Sentry (backend; the app's part arrives with the frontend) | PII scrubbed, tagged with environment and release (the commit) |
| Logs | Cloud Logging (structlog JSON) | Request IDs end to end |
| Uptime | Better Stack or UptimeRobot | Alerts reach a phone |
| Email | Resend (or Postmark) | Test sender until the domain is verified |
| Payments | Razorpay (Orders, Checkout, webhooks, refunds) | Test keys outside production; live keys + webhook secret in Secret Manager |
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
| Deploy | Manual | Manual, from a release tag | Auto on merge to main | Manual approval (GitHub Environment `production`) after a green `ci`; or `make deploy ENV=production` from the laptop, with a typed confirmation |
| Banner | "Dev" | "Demo — sample data" | "Staging" | "Beta" while BETA_MODE is on |
| BETA_MODE | off | off | on (to test the gate) | on until public launch |
| FEATURES | all everyone | all everyone | all everyone | see §2b |

**Rollout order.** Production is deployed first, behind BETA_MODE (invite-only). Staging and demo are postponed until before
payments or public launch. Nothing in the code is production-specific: `ENV=staging|demo|production` all work from
`deploy/gcp/<env>.toml`, so adding them later is filling in one file and running `make gcp-setup ENV=staging`.

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
| `LANDING_URL` | Landing site origin, links from app/emails | Production beta: `https://circuit-phi.vercel.app` (one Vercel project, landing at `/`) | `https://<domain>` |
| `APP_URL` | App address, email and invite links, auth redirects. May carry a path | Production beta: `https://circuit-phi.vercel.app/app` (same project as the landing site, `vercel.json` serves the app under `/app`; build variable `NEXT_PUBLIC_BASE_PATH=/app`). Staging/demo: `https://circuit-app-<env>.vercel.app` | `https://app.<domain>` |
| `API_URL` | App API base, links in emails | `auto` in deploy/gcp/<env>.toml: `https://circuit-<env>-api-<project number>.asia-south1.run.app` | `https://api.<domain>` |
| `CORS_ALLOWED_ORIGINS` | Exact origins allowed by the API: scheme + host only, no path or slash | The origin of `APP_URL` (+ `http://localhost:3000` in dev) | The origin of `APP_URL` only |
| `CORS_PREVIEW_REGEX` | Vercel PR previews (staging only) | `^https://circuit-app-staging-git-.*\.vercel\.app$` | empty |
| `CSRF_TRUSTED_ORIGINS` | Django admin form posts | `https://*.run.app` | `https://api.<domain>` |
| `ALLOWED_HOSTS` | Django host check | `.run.app` (any Cloud Run address; probes and `make smoke` need it) | `api.<domain>` (keep `.run.app` if you still deploy with a test address) |
| `EMAIL_FROM` | Sender | Provider test sender | `Circuit <hello@<domain>>` |
| `SUPPORT_EMAIL` | Footer, legal pages | Team inbox | `support@<domain>` |
| `SUPABASE_URL` | Auth, storage, realtime | Per-env project URL | Production project URL |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | Orders, payment signature | Test keys | Live keys |
| `RAZORPAY_WEBHOOK_SECRET` | Webhook signature | Test webhook secret | Live webhook secret |

Production beta uses ONE Vercel project: the landing site at `/` and the app at `/app` (`vercel.json`). Supabase redirect URL is
`https://circuit-phi.vercel.app/app/auth/callback`. The two-project layout above is what staging/demo and the real domain use.

Frontend build-time variables (set per Vercel project): `NEXT_PUBLIC_APP_URL`,
`NEXT_PUBLIC_LANDING_URL`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`,
`NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_ENV`. The landing project also reads `NEXT_PUBLIC_JOIN_LIVE`
(default `false`: every call to action opens the waitlist form; set `true` once the app has `/join` and is deployed),
and optionally `NEXT_PUBLIC_CONTACT_EMAIL` and `NEXT_PUBLIC_COMPANY_LEGAL_NAME` (footer).

Switching to the real domain (config only, ~1 hour plus DNS wait):
1. [YOU] Vercel: add `<domain>` to the landing project and `app.<domain>` to the
   production app project; set DNS; wait for HTTPS.
2. [YOU] API: map `api.<domain>` to Cloud Run; set DNS; wait for the certificate. Cloud Run's
   domain mapping is a preview feature that is not offered in every region: check
   `gcloud beta run domain-mappings create --help` and the console in asia-south1. If it is
   not available, the cheap route is a Firebase Hosting rewrite to the service (free), the
   robust one a load balancer (about $18/month). RUNBOOK.md has the steps for each.
3. Update the §2a variables in Vercel and Cloud Run / Secret Manager.
4. Supabase Auth: Site URL = `APP_URL`; redirect URLs = `APP_URL/auth/callback` (+ staging,
   demo and `http://localhost:3000/auth/callback`).
5. Google OAuth client: add `APP_URL` to authorised JavaScript origins.
6. Email: verify the domain (SPF, DKIM, DMARC), then switch `EMAIL_FROM`.
7. Redeploy; run `make smoke URL=<APP_URL>`.

## 2b. Feature flags per environment
`FEATURES` sets the default audience per flag, e.g.
`FEATURES=pulse:everyone,daily_drop:everyone,circuits:testers`. Flags not listed are
`off`. Super admins override in Django admin (CLAUDE.md "Feature flags").

| Flag | dev | demo | staging | production (beta start) |
|---|---|---|---|---|
| pulse | everyone | everyone | everyone | everyone |
| daily_drop | everyone | everyone | everyone | everyone |
| circuits | everyone | everyone | everyone | testers |
| investor_mode | everyone | everyone | everyone | off |
| partner_mode | everyone | everyone | everyone | off (testers once the partner is verified) |
| promotions | everyone | everyone | everyone | off |
| payments | everyone (test keys) | everyone (test keys) | everyone (test keys) | off |

When to switch on in production (check the numbers in the metrics view first):
- `circuits` → everyone: ≥ 30 members opted in with at least one need and one offer, and
  a tester round produced at least 3 circuits that were accepted.
- `partner_mode` → everyone: the first partner organisation is verified and its admin has
  used it with testers for a week.
- `investor_mode` → everyone: ≥ 15 startups are open to investors and ≥ 5 investors are
  verified (otherwise picks are empty).
- `promotions` → everyone: ≥ 300 weekly active students and ≥ 30 claimed startups, so a
  promotion is worth paying for.
- `payments` → everyone: promotions on, GST registration done, live Razorpay account
  activated, refund policy page live, one real ₹1-scale test payment and refund done
  end to end.
- Switching any flag on or off is a one-line change in Django admin; record the date and
  reason in PROGRESS.md.

## 3. Security baseline
- Supabase JWT verified on every request (signature, expiry, audience, pinned algorithm).
- Permission helpers + org scoping on every endpoint; IDOR tests for every ID parameter.
- RLS on every table (deny by default); service role key only in the backend.
- Django admin: staff only, TOTP 2FA required, non-obvious path, disabled in demo,
  all actions audit-logged. Django's security settings on (SECURE_*, HSTS, secure cookies).
- Rate limits (Redis): onboarding extraction, intros, applications, reports, claims.
- CORS: exact origins only. Headers: CSP, HSTS, nosniff, Referrer-Policy, frame-ancestors.
- Input validation (Ninja schemas), request size limits, upload type/size checks.
- No personal data in logs or analytics (tested).
- Dependabot + secret scanning; 2FA on GitHub, GCP, Supabase, Vercel, Upstash.

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
- Retention: events (pseudonymous, 365 days), notifications (read 90 days, any 180), request logs (30 days), unverified accounts
  (purged after 30 days), database backups (30 days). The daily `retention_cleanup` job does the database ones; RUNBOOK.md "Retention" lists every period.
- Processors listed: Supabase, Google Cloud, Vercel, the active LLM provider, Resend, Sentry, Upstash, Razorpay.
- Payments: refund and cancellation policy page; GST on invoices (accountant confirms
  GSTIN, rates and invoice format before live payments); Razorpay live activation
  (KYC) done by the founder.

## 6. Data safety
- Production: Supabase Pro daily backups (7 days). **Point-in-time recovery is NOT part of Pro**:
  it is a paid add-on (about $100/month per 7 days of retention, check supabase.com/pricing).
  Decide before real users whether the beta needs it; daily backups lose up to a day. Restore
  drill to staging (or a scratch project) before launch, then quarterly.
- Our own copy, on any plan: the `backup_db` job (02:30 IST) writes an encrypted `pg_dump` of the `public` and `auth` schemas to a
  private bucket in our Google project, kept 30 days (RUNBOOK.md "Restore from a backup"). Encrypted with an `age` PUBLIC key:
  the cloud holds no key that can open it; the private key is offline in a password manager. The job's service account can add files and
  nothing else. `make restore-drill` restores the newest one into a throwaway local database and compares row counts. Files in Supabase
  Storage are not part of it.
- The free Supabase plan pauses a project after a week without activity and has no backups:
  fine for trying the deploy, not for real members.
- Django migrations: reviewed, backwards-compatible (expand then contract), tested on a
  staging copy.
- Redis is rebuildable from Postgres (`manage.py rebuild_cache`).

## 7. Reliability
- `/health` (is the process up: touches nothing) and `/ready` (Postgres must answer; Redis down is
  only a warning, 200 `degraded`). Both are answered before host checks and the HTTPS redirect, and
  are not request-logged. Cloud Run's startup and liveness probes use `/health` ONLY: if they used
  `/ready`, a Supabase blip would make Cloud Run restart every healthy instance in a loop. `/ready`
  is for `make smoke` and uptime monitors. `/api/health` and `/api/health/deps` (adds the Supabase
  JWKS) stay for the app and for a deeper manual check.
- Logs are JSON with `severity` and `message` (Cloud Logging fields), plus the Cloud Trace link.
- Timeouts + retries + fallbacks on every external call.
- Jobs idempotent, retry-limited, alert on failure.
- Expiry: `expire_items` job every 5 min, and reads treat past-deadline items as expired.
- Supabase pooler; Django CONN_MAX_AGE and pool size × max instances under the limit.

## 7a. Database connections (Supabase pooler)
Cloud Run starts and stops many small instances, each with up to 8 threads, and Cloud Run cannot
reach Supabase's direct database address (IPv6 only). So the API connects through Supabase's
**transaction pooler** (port 6543) and says so with `DATABASE_POOLER=transaction`. Why that needs care:
- The pooler gives each *transaction* a different server connection. **Server-side cursors**
  (what `QuerySet.iterator()` uses) live on one connection, so they are switched off
  (`DISABLE_SERVER_SIDE_CURSORS`). **Prepared statements** are also per connection: Django's
  psycopg 3 backend leaves them off unless told otherwise, and a test asserts it stays so.
- **Session-level advisory locks** would not hold either. Jobs take a *lease* instead: one UPDATE
  on `core_job_runs` (core/jobs.py), which works on any connection and survives a killed job (it
  just expires).
- The app refuses to start on port 6543 without `DATABASE_POOLER=transaction`, and requires TLS to
  any database that is not localhost.
- Connections: each gunicorn thread keeps one for a minute (`CONN_MAX_AGE=60`, with a health check
  before reuse). Worst case = max instances × 8 + running jobs ≈ 3 × 8 + 3 = 27 client connections to
  the pooler, far under its client limit. Raise max instances only after checking that sum against
  your Supabase plan's pooler limit.
- Region: put the Supabase project in Mumbai (ap-south-1) too, so each query is ~1 ms, not ~150 ms.
- The Google Cloud project and the Supabase project can be on different Google accounts: they only
  meet through `DATABASE_URL` and `SUPABASE_URL` / keys, which live in Secret Manager.

## 8. Observability and alerts

| Signal | Tool | Alert when |
|---|---|---|
| Errors | Sentry (backend; names, emails, phones, tokens and request bodies removed before sending; tagged with environment and release) | New error type or error spike |
| Uptime | Cloud Monitoring uptime checks (API `/ready`, app, landing) | Down for 2 min, from more than one place |
| 5xx | Cloud Monitoring | More than 2% of API responses for 5 min (and at least 3) |
| Latency | Cloud Monitoring | API p95 > 1s for 10 min |
| Jobs | Cloud Monitoring + log metrics + `check_jobs` | A job fails (`job.failed`, or a Cloud Run Job execution fails); a job has no success for 2x its interval (`job.overdue`); the watcher itself has not run for 30 min |
| Free-tier limits | Weekly `usage_report` job | Anything at 70% of a limit (`usage.warning`) |
| Cost | GCP budget, Supabase, Anthropic limits | 50%, 80%, 100% of budget |

All of it is code: `infra/monitoring/` and `make monitoring ENV=production`. Alerts go to the notification channels named in `deploy/gcp/<env>.toml`
(email and a phone one). Each alert's text names the RUNBOOK.md section to open.

## 9. Performance targets
- API p95 < 300ms for cached reads, < 800ms otherwise.
- App initial JS < ~250KB gzipped; Lighthouse ≥ 90 mobile on landing and app Home.
- Load test ~1,000 concurrent users on staging before public launch.

## 10. Deploy and release
The pipeline (GitHub Actions, `.github/workflows/`):
1. Pull request → `ci`: ruff, mypy, then `make check` (ESLint, every backend test, the app's types and Playwright design checks, the landing build and
   Playwright). Branch protection on `main` requires the `ci` check, so a red pull request cannot merge. uv and pnpm downloads are cached.
2. Merge to main → `ci` again → staging deploys by itself (once staging exists: repository variable `STAGING_DEPLOY_ENABLED`).
3. Release tag `v*` → deploy demo → reset its data (once demo exists: `DEMO_DEPLOY_ENABLED`).
4. Production: "deploy production" is started by hand and waits for the approval of a required reviewer (GitHub Environment `production`).
5. Every deploy: confirm the commit is on `main` with a green `ci` → log in to Google Cloud with **Workload Identity Federation** (a signed token from GitHub;
   no JSON key exists anywhere; the deploy account can only be used by a job in the environment of the same name, from our repository) → build the image for
   x86_64 and ARM64 and push it → migrate as a job and wait → new revision at 0% traffic → smoke-test its private address → move traffic → smoke-test the
   live address → update jobs and schedules. A failed migration or private smoke test leaves the old version serving; a failed live smoke test sends
   traffic back to the previous revision automatically.
6. Rollback by hand: `make rollback ENV=production` (previous Cloud Run revision) + previous Vercel deployment (RUNBOOK.md "Rollback").

From the laptop, `make deploy ENV=production` does the same steps (you type the environment name instead of a reviewer approving). It is the
way to deploy if GitHub is unavailable. The deploy account may deploy, push images, edit schedules and see whether a secret has a value;
it cannot read secret values or member data.

## 11. Cost guardrails (check current pricing)
- Fixed: Supabase Pro (production), domain, Vercel Pro if needed.
- Usage: Cloud Run, Upstash, Anthropic API, Resend. Monthly estimate per piece: RUNBOOK.md "What it costs".
- `make gcp-setup` creates a budget with email alerts at 50/80/100% that counts real usage even while free credits pay the bill. It warns; it does not stop spending.
- Budget alerts on every paid service from day one.
- Free-tier guards in code (they keep a free plan from becoming a surprise bill or an outage): optional notification emails stop at 90/day and
  2,800/month (Resend free is 100 and 3,000), the AI provider is capped per day (`LLM_DAILY_CALL_LIMIT`; `LLM_PROVIDER=none` runs with no AI),
  Redis keeps fewer copies in lean mode (`REDIS_LEAN`, Upstash free is 500,000 commands a month), uploaded images are compressed before storage
  (`MEDIA_WEBP_QUALITY`), old events, notifications and snapshots are removed daily, and the weekly `usage_report` job warns at 70% of a limit
  (`make usage-report`). RUNBOOK.md "A free-tier limit is nearly hit" lists what happens at each limit.

## 12. Launch stages
1. Closed beta: invite-only (F18, BETA_MODE=true) in the PRODUCTION environment, because
   beta users are real people with real data. Requires LAUNCH.md Stages 1–8 (legal
   reviewed, production database with backups, monitoring). Start with 20–50 invited
   users; grow by invite codes. Staging and demo never hold beta users' data.
2. Pilot college: one partner, ~150 verified local startups, 30–50 claimed.
3. Public launch: after pilot metrics are healthy and the load test passes.

## 13. Pilot metrics
- Landing visit → sign-up → onboarding complete → first match → first action
- Intro acceptance (local vs bridge); circuits proposed / activated / completed
- Startups claimed, roles posted, applications, shortlists
- Weekly active users; 4-week retention

## 14. What breaks in production, and the test for each

Every row must have an automated test or a manual check that has passed on staging
before production. `make check` covers the automated ones; RUNBOOK.md lists the manual
ones with the date they last passed.

| # | What breaks | Why it only shows up in production | Test condition |
|---|---|---|---|
| 1 | Sign-in fails after deploy | Redirect URLs, CORS origins or JWT audience differ per environment | `make smoke` signs in on each env; CORS preflight from APP_URL passes; a token from another env's Supabase is rejected |
| 2 | Users logged out at random | Clock skew, JWKS key rotation | JWT check allows ≤60s skew; JWKS cache refreshes on unknown key id (test with a rotated key) |
| 3 | Migration locks the database | Real tables are big; dev tables are tiny | Migrations are expand/contract; run on a staging copy with production-sized seed (≥50k members, ≥500k events) and time them |
| 4 | "Too many connections" | Cloud Run scales to many instances | Load test at target users; pool size × max instances < Supabase limit; pooler URL used |
| 5 | Slow pages | N+1 queries, missing indexes on real data volume | Query-count assertions on list endpoints; `EXPLAIN` on Pulse, Discover, matches with production-sized data; p95 within §9 targets |
| 6 | Cold starts | Scale-to-zero | Min instances 0 during the closed beta (cost) and 1 before public launch; first-request latency after idle measured and written in RUNBOOK.md; startup CPU boost on; the embedding model is baked into the image |
| 7 | An external service is down or slow | LLM, Resend, Razorpay, Supabase Storage outages | Tests with mocked timeouts/5xx for each: onboarding falls back to manual chips, email queues and retries, payment shows "processing" and reconciles later |
| 8 | Duplicate or missed payment events | Webhooks retry, arrive out of order, or don't arrive | Same webhook twice → one state change; `captured` before checkout callback → still correct; no webhook → `reconcile_payments` fixes it; tampered body → 400 |
| 9 | Charged but campaign not live / live but not paid | Partial failures between steps | Campaign activates only in the webhook handler inside one transaction; test kill-mid-way cases |
| 10 | Jobs run twice at once | Scheduler retries, overlapping runs | Every job takes a lease in Postgres (core/jobs.py; advisory locks do not survive the pooler) and is idempotent; `tests/unit/test_scheduled_jobs.py` runs 8 threads at once → exactly one does the work |
| 11 | Daily Drop arrives at the wrong time | Servers run in UTC, users in IST | All scheduling in Asia/Kolkata; test 07:59/08:00/08:01 IST and the day boundary |
| 12 | Image uploads fail | iPhone HEIC, huge files, slow networks | Upload tests with HEIC, 12MB, 0-byte, wrong MIME, interrupted upload; client resize to 1440px |
| 13 | Broken names and text | Indic scripts, emoji, very long names | Fixtures with Tamil, Hindi, Kannada, Bengali names, emoji, 80-char names; layout snapshots at 375px |
| 14 | Realtime messages stop | Mobile networks drop sockets | Reconnect with backoff; missed messages fetched on reconnect (test by cutting the connection) |
| 15 | Stale data after edits | Redis cache not invalidated | Tests: edit profile/needs/job → matches and Pulse reflect it within the TTL rule; Redis down → Postgres fallback |
| 16 | Someone sees data they shouldn't | Real users try IDs, roles and minors' edges | IDOR tests on every ID; role matrix tests; under-18 tests (no stranger Requests, hidden profile, verified-startup promotions only) |
| 17 | Abuse and spam | Real users and bots | Rate-limit tests on every write; report → hide flow tested end to end |
| 18 | Wrong secrets in an environment | Copy-paste between envs | Startup check: refuses live Razorpay keys outside production, DEMO_AUTH in staging/production, missing variables anywhere |
| 19 | Emails land in spam or not at all | Domain not verified | SPF/DKIM/DMARC verified; test sends to Gmail and Outlook before launch |
| 20 | Bill shock | Runaway jobs, LLM loops, crawler | Budget alerts at 50/80/100%; LLM monthly cap enforced in code; job timeouts |
| 21 | Can't recover from a mistake | Bad deploy or data loss | Rollback tried once; backup restored to staging (restore drill) and timed |
| 22 | Works on a laptop, not on a ₹10k phone | Slow CPU and network | Lighthouse mobile ≥ 90; manual test on a real budget Android over throttled 4G |
