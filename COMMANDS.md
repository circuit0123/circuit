# Circuit — commands

Every command you run is a `make` target. Run them from the repo root. `make help` lists
them all. If a target here doesn't exist yet in the repo, ask Claude Code to build it
(LAUNCH.md Stage 1b), never work around it by hand.

## 0. One-time laptop setup (Omarchy / Arch Linux)
```bash
sudo pacman -S --needed git make docker docker-compose docker-buildx nodejs
sudo systemctl enable --now docker
sudo usermod -aG docker $USER            # then log out and back in
curl -LsSf https://astral.sh/uv/install.sh | sh   # Python manager (installs Python 3.12 for you)
corepack enable && corepack prepare pnpm@latest --activate
```
Optional, only when deploying from the laptop: `yay -S google-cloud-cli`, then
`gcloud auth login` (RUNBOOK.md "First production deploy on Google Cloud" has every step).

Check everything is installed: `make doctor` (prints OK/MISSING per tool, and OK/MISSING/DEFAULT per .env
variable; never the values).

## 1. First run (fresh clone)
```bash
cp .env.example .env      # then fill values from your password manager
make setup                # installs Python + JS deps, starts Postgres/Redis, migrates, seeds demo data
make dev                  # starts API + app + landing together
```
Then open:
| What | URL |
|---|---|
| App | http://localhost:3000 |
| Landing site | http://localhost:3001 |
| API | http://localhost:8000/api/health |
| API docs (OpenAPI) | http://localhost:8000/api/docs |
| Django admin | http://localhost:8000/<ADMIN_PATH>/ (create a user with `make admin-user`) |
| Component gallery | http://localhost:3000/design |

In dev you sign in with the persona switcher (DEMO_AUTH), so no Google login needed.
Stop everything with Ctrl+C, then `make down`.

## 2. Everyday commands
| Command | What it does |
|---|---|
| `make dev` | API + app + landing with live reload (one terminal, coloured output) |
| `make api` | Only the Django API on :8000 |
| `make app` | Only the product app on :3000 |
| `make landing` | Only the landing site on :3001 |
| `make landing-screens [SCREENS="map job"]` | Re-renders the phone pictures on the landing site (`apps/landing/public/screens/<name>.{avif,webp,png}`, each at most 150 KB) from the screens in `docs/design-reference`. Replaces startup and people names with sample ones and adds a "Sample data" label. Needs `pnpm install` and Python with Pillow. Run it when a reference screen changes; commit the pictures |
| `make mock` | App on :3000 against mock data: no backend, no login, you are signed in as Ravi Kumar. The banner at the top switches scenario (default, empty, loading, error, slow 3G, beta access missing, features off, under 18) and theme; `?scenario=empty` in the address does the same. The data is temporary and typed against openapi.json (`apps/app/src/data/mocks/`; B7 replaces it with the contract fixtures). `/design` shows every component in both themes and all six accents |
| `make up` / `make down` | Start / stop Postgres + Redis containers |
| `make logs` | Follow the local container logs. In the cloud: `make logs ENV=production` prints the newest log lines (add `JOB=compute_matches` for one job, `LIMIT=100` for more) |
| `make shell` | Django shell (`manage.py shell`) |
| `make dbshell` | psql into the local database |

## 3. Database and data
| Command | What it does |
|---|---|
| `make migrate` | Apply migrations |
| `make migrations` | Create migrations after a model change (review them before committing) |
| `make reset-demo` | Wipe local data and reload seed + the five demo stories (idempotent) |
| `make reset-demo ENV=demo` | Same on the demo environment: runs the `reset-demo` job in Google Cloud (asks you to type `demo`) |
| `make load-startups FILE=backend/data/startups_2026-10.csv [DRY=1]` | One-off: load startups from a CSV as unclaimed, visible profiles (source `crawler`). Matches on website domain, never touches a claimed startup, running it again changes nothing. Looks up pins on OpenStreetMap (1 request a second, answers cached in `backend/data/geocode_cache.json`); no address or "area only" means no pin. Prints the sector mapping, created / updated / skipped, and geocode hits / misses. `DRY=1` writes nothing |
| `make load-startups FILE=... ENV=staging` or `ENV=production` | Same against the cloud database: asks you to type `production` first, then for the `DATABASE_URL` (hidden), and runs from your laptop like RUNBOOK step 16 |
| `make admin-user USER_NAME=asha` | Create a Django admin user (asks for a password) and print the 2FA setup link (`otpauth://…`) to add to an authenticator app. Run again to reset someone's 2FA |

| `make invite-codes N=10` | Create invite codes for the beta and print each with its one-tap link (`APP_URL/join?code=…&src=invite`). Optional: `USES=5` (people per code, default 1), `DAYS=30` (expiry), `ORG=3` (whoever redeems joins organisation 3), `NOTE="pilot cohort"`. Audit-logged |

`make reset-demo` refuses to run when ENV is staging or production.

## 4. Feature flags
| Command | What it does |
|---|---|
| `make flags` | List every flag and its audience (off / testers / everyone) |
| `make flag NAME=circuits TO=testers` | Change one flag locally |
| `make flag NAME=circuits TO=everyone ENV=staging` | Not available: in staging and production change flags in Django admin (Core, Feature flags). It is audit-logged and needs no deploy |

In production, change flags in Django admin only (audit-logged), not from the laptop.
Defaults per environment and when to switch each on: PRODUCTION.md §2b.

## 5. Background jobs (run by hand locally; scheduled in the cloud)
| Command | What it does |
|---|---|
| `make job NAME=compute_matches` | Run any management command as the scheduler would |
| `make jobs` | List every scheduled job, when it runs (India time) and the command it runs. Read from `deploy/gcp/app.toml`, the same file the deploy uses, so it is always what is deployed |
| `make daily` | Run the 08:00 set: compute_matches, then the Daily Drop (investor picks join in Stage 4f) |
| `make circuit-round` | Run an exchange circuit round now |
| `make job NAME=send_emails` | Send queued emails that are due (invite emails retry here when the provider was down). Runs every 5 minutes in the cloud, inside the `every-5-min` job |
| `make job NAME=build_exports` | Build the data exports members asked for and email their download links (24-hour link). Scheduled every 5 minutes in the cloud |
| `make job NAME=delete_accounts` | Finish the account deletions members asked for (sign-in, files, profile and personal data removed; posts and messages show "Deleted member"). Scheduled every 5 minutes in the cloud |
| `make retention` | The daily clean-up now: accounts that never accepted the terms (30 days), expired export files, rejected waitlist entries older than 90 days, ranker snapshots older than a year. Logs counts only. Request logs are kept 30 days in Cloud Logging, not here |
| `make export MEMBER=<id>` | DEV ONLY. Build one member's data export right now and print where the zip is (members normally ask in the app) |
| `make delete-account MEMBER=<id>` | DEV ONLY. Delete one member's account right now (asks you to type DELETE). Refuses outside dev |
| `make eval` | `eval_matching` against tests/eval/pairs.json |
| `make simulate [MEMBERS=400] [RESET=1]` | DEV ONLY (refuses in production). Builds a synthetic network (members with hidden tastes who see lists and answer intros) so the ML pipeline can be tested end to end. Does nothing if one exists, unless `RESET=1`. Simulated members are never matched with real ones |
| `make train` | `train_ranker`: builds the training set from feature snapshots and intro outcomes, trains a LightGBM ranker, evaluates it against the rule ranker (NDCG@10, acceptance proxy, eval-set agreement, fairness by college tier and Bridge vs local) and saves it as a **candidate**. It never changes what members see; a super admin promotes it in Django admin (Matching → Model versions). Scheduled weekly in the cloud |
| `make ranker-report [DAYS=28]` | Intro request and accept rates per ranker arm and model version (real members only) |

## 6. Tests and quality
| Command | What it does |
|---|---|
| `make test` | Backend tests (pytest) |
| `make test-web` | Frontend: type check, the "only `src/data` talks to the backend" ESLint rule (`apps/app/tests/boundary.test.mjs`), then Playwright on mock mode at 375px and 1280px (no backend needed, about 3 minutes): the DESIGN.md §13 design checks, TabPager touch tests, sheet detents, first paint and accents, 404/500, every mock scenario, the PWA manifest, `/design` with axe |
| `make test-landing` | Landing site tests: builds the static site three times with test URLs (every feature flag on and `NEXT_PUBLIC_JOIN_LIVE=true` on :3101; flags off with the switch on, :3102; flags on with the switch off, the default, :3103; the flags come from a mock `/api/config`) and runs Playwright at 375px and 1280px in both themes: home and the five audience pages (CTA role and src, `?src=` carry-through, both flag-off fallbacks, the join switch (no button leads to a 404 in either mode), the waitlist and partner forms with a mocked API, reduced motion, axe, SEO tags, DESIGN.md premium rules). No backend needed; a run takes about four minutes |
| `make e2e [SPEC=premium]` | Playwright journeys against the real API (sign-in and the shell, `apps/app/e2e/`), signed in as demo personas. Needs `make dev` running. `SPEC=premium` (or any other spec name from `apps/app/tests/`) runs just that spec on mock mode, no backend needed; `premium` writes its report to `screenshots/premium/report/` |
| `make lint` | ruff (check + format check), mypy, ESLint (prettier is not installed yet) |
| `make fmt` | Auto-format Python with ruff (TypeScript formatting arrives with prettier) |
| `make check` | lint + backend tests with demo stories PASS/FAIL + frontend type check + landing tests. Must be green before any push |
| `make smoke URL=https://... ORIGIN=https://app.example.com` | Check a running API from the outside. See section 9 |
| `make load-test URL=http://localhost:8080 [USERS=50,200] [SECONDS=60] [TOKENS=file] [JSON=out.json]` | Simulates the beta mix (sign-in, Home, Discover, Map, job page and apply, Inbox, send a message) at each user level and prints p50 / p95 / error rate per endpoint against PRODUCTION.md §9 (300 ms cached reads, 800 ms the rest). Without `TOKENS` it makes demo tokens for 200 seeded members (local and demo only; needs `make reset-demo` and `make daily` first). Staging needs a token file (RUNBOOK.md "Run a load test on staging"). **Refuses to run against production** (and against anything it cannot identify). Success: `RESULT: PASS`; `FAIL` names the endpoints over target |
| `make funnel [DAYS=30]` | Per sign-up source: landing clicks, signed up, beta access, onboarding done, first match action. Counts under 5 show `<5`. No personal data. The same table is in Django admin → Metrics |
| `make api-freeze [BASE=origin/main]` | Fails if `openapi.json` changed against BASE without a higher `info.version` and a change to `FRONTEND_HANDOFF.md`. CI runs it on every pull request |

## 7. API client
| Command | What it does |
|---|---|
| `make api-client` | Export openapi.json from Django and regenerate packages/api-client (`make openapi` is an alias) |
| `make contract-fixtures` | Rewrite `packages/api-client/fixtures/` from the real API: the demo world is seeded at a frozen clock, every screen's calls are made as `FRONTEND_HANDOFF.md` describes, each response is checked against openapi.json and written as JSON. Run it after a deliberate API change and commit the diff. Success: it ends with `1 passed`; `git diff packages/api-client/fixtures` shows exactly what changed for the frontend. Needs the test database (`make up`). The frontend's mock mode serves these same files |

Run both after any endpoint change; commit openapi.json, the client, the fixtures, `FRONTEND_HANDOFF.md` and the
contract tests together. `make check` fails when they disagree, so a changed endpoint cannot be committed alone.

## 8. Build (the backend image)
| Command | What it does, when to run it, what success looks like |
|---|---|
| `make build-api` | Builds the production Docker image for your computer (`circuit-api:local`). Run it before `run-prod-local`, or to check the Dockerfile after changing it. Success: it ends with `built circuit-api:local, 1.6GB` (about 3 minutes the first time, 30 seconds after) |
| `make run-prod-local` | Runs that image the way Cloud Run will (gunicorn, non-root user, read-only code) against your local Postgres and Redis, on http://localhost:8080 (`PORT=8081` for another port). Run it before a first deploy, in one terminal; in another run `make smoke URL=http://localhost:8080`. Success: `curl localhost:8080/health` prints `{"status": "ok"}`. Stop with Ctrl+C |
| `make build-api-multiarch` | Proves the image also builds for ARM64 (and x86_64). Nothing is pushed. Slow (15+ minutes: ARM64 runs under emulation). Run it after changing the Dockerfile or adding a Python dependency. Success: it finishes without an error |
| `make build-web` | `pnpm build` for the app and the landing site |
| `make build` | `build-api` + `build-web` |

## 9. Deploy to Google Cloud
Every target here **prints the exact `gcloud` commands first, then asks you to type the environment name** (`production`)
before anything changes. Anything else stops with nothing done. Each one is safe to run again: it only creates what is
missing and updates the rest. Add `DRY=1` (deploy, rollback, monitoring) to print the plan and the files it would write, with nothing
asked and nothing run. `ENV` is `production`, `staging` or `demo`. Settings live in `deploy/gcp/<env>.toml`
(fill the `<placeholders>` once); shared settings and the job schedule live in `deploy/gcp/app.toml`.

Two ways to deploy, same steps (RUNBOOK.md "Deploy"): **from GitHub Actions** (the normal way: CI runs on every pull request and blocks
a merge on red; "deploy production" is started by hand and waits for your approval) or **from your laptop** with these commands. In
the pipeline the approval replaces the typed confirmation, and a failed live smoke test sends traffic back to the previous revision by itself.

| Command | What it does | When to run it | What success looks like |
|---|---|---|---|
| `make gcp-setup ENV=production` | Turns on the Google Cloud services; creates the image repository (keeps the last 5 images), the two service accounts, one empty slot per secret, and a budget with email alerts at 50%, 80% and 100% | Once per environment, before the first deploy | `Done.` Rerunning prints `already there, skipped` for everything that exists |
| `make secret ENV=production NAME=SECRET_KEY` | Stores a new value for one secret in Secret Manager. You type it at a hidden prompt; it never appears in a command line or in your shell history | For every secret before the first deploy (`deploy/gcp/app.toml` lists them), and whenever a key changes | `Done.`, then run `make deploy`: running instances read secrets when they start |
| `make deploy ENV=production` | (From your laptop; GitHub does the same.) Checks every secret has a value; builds the image from the current commit and uploads it; runs the migrations as their own job and waits; creates a new revision with 0% of traffic; smoke-tests it on a private address; moves 100% of traffic to it; smoke-tests the live address; updates every job and schedule | Whenever you want new code live. Needs a clean `git status` (the image is named after the commit) | The last lines are the smoke test with `OK: 0 failed`, then `Done.` If migrations or the smoke test fail, nothing is switched and the old version keeps serving |
| `make smoke URL=https://... ORIGIN=https://app.example.com [EXPECT_ENV=production]` | Checks a running API from the outside, read-only: `/health`, `/ready`, `/api/config`, that the API description is public everywhere except production, that a protected endpoint refuses a missing or made-up token, that CORS allows exactly your app address and refuses a stranger, and the security headers | After every deploy (`make deploy` already runs it), and any time something feels off | `PASS` on every line and `OK: 0 failed`. `WARN` lines are information (for example Redis is down but the app still works from Postgres). Any `FAIL` exits non-zero and says what to fix |
| `make rollback ENV=production [REVISION=name]` | Sends 100% of traffic back to the previous revision (or the one you name) and points the jobs at its image | When a deploy turns out bad. Takes effect in seconds | The smoke test passes against the old version. The database migrations are **not** undone: every migration is written so the previous code still works with it |
| `make monitoring ENV=production` | Creates or updates, by name, the uptime checks (API, app, landing), the log-based metrics and the alert policies in `infra/monitoring/` (site down, 5xx rate, slow API, job failed, job overdue, job watcher stopped, free-tier limit). Alerts go to the channels named under `[monitoring]` in `deploy/gcp/<env>.toml` | After `gcp-setup`, once you have created an email and a phone notification channel in the Cloud Console; again whenever a file in `infra/monitoring/` or a URL changes | `Done: 14 objects`, each line `created` or `updated`. A missing channel stops it and names it. `DRY=1` prints every file with nothing asked |
| `make backup-now [ENV=production]` | Takes an encrypted backup of the database right now: `pg_dump` piped into `age`, so no readable copy is ever stored, plus a small file of row counts. Without `ENV` it backs up your local database into `backend/.backups/dev/` (needs `pg_dump`, `age` and `BACKUP_AGE_RECIPIENT` in `.env`); with `ENV=production` it runs the nightly job once, now, into the private bucket | Before a risky change, before the first real members, and to prove the nightly job works | `backup written: 12.3 MB, 87 tables`; the file shows up in the bucket (`gcloud storage ls gs://<project>-circuit-production-backups/production/`) |
| `AGE_KEY_FILE=~/backup.key make restore-drill [ENV=production]` | Restores the newest backup into a throwaway database on your computer (a temporary Postgres on port 5433, started and removed for you), counts every table and compares it with the counts taken when the backup was made. Never reads `DATABASE_URL`, refuses any database that is not on this computer | Before launch, then every quarter, and after any change to the backup job. Needs Docker, `age` and the PRIVATE key. The temporary Postgres is version 17 (what the cloud backup job uses); for a backup made with your laptop's newer `pg_dump` add `DRILL_PG_MAJOR=18` | `PASS` per table and `OK: 87 of 87 tables match`. Any `FAIL` exits non-zero. Time it and write the minutes in RUNBOOK.md |
| `make usage-report [ENV=production]` | Prints how close each free plan is to its limit: database size, file storage, sign-in accounts, emails (this month and busiest day), Redis memory and commands, AI calls today. Locally it reads your own database; with `ENV` it runs the weekly job now and shows its newest log lines. Anything at 70% or more is marked `!!` and logs `usage.warning`, which the alert in `infra/monitoring/` turns into a message | Before inviting a new group of members, when the app feels slow, and any time a bill or a limit worries you (it also runs by itself every Monday 09:00) | A table with a percentage per line and no `!!`. A `!!` line says which plan to upgrade or clean up (RUNBOOK.md, "A free-tier limit is nearly hit"). Supabase egress and Vercel bandwidth are not measured: look at their dashboards |
| `make job-health [ENV=production]` | Shows every scheduled job: how often it should succeed, when it last did, the last error, and `OVERDUE` for any job with no success for twice its interval. Locally it reads your own database (nothing is expected there, so it says so); with `ENV` it runs the watcher (`check_jobs`) once and prints its newest log lines. Super admins can read the same list at `GET /api/health/jobs` | When an alert says a job is overdue, and after any deploy that touches a job | `0 overdue of 14.` In the cloud: a `job.end` line for `check_jobs` and no `job.overdue` lines |
| `make jobs-run ENV=production JOB=compute_matches` | Runs one job in the cloud right now and waits for it to finish (`make jobs` lists the names) | To run a job outside its schedule, e.g. after a flag change | `Done.`; `make logs ENV=production JOB=compute_matches` shows its `job.end` line |
| `make logs ENV=production [JOB=...] [LIMIT=100]` | Prints the newest log lines of the API (or of one job), newest first, with severity | To see what happened, e.g. after a failed deploy or a skipped job | Lines such as `INFO request`. Read-only: it asks nothing |
| `make jobs` | Lists every job, its schedule and command | To see what runs when | A table; jobs whose code is not built yet are marked |
| `make reset-demo ENV=demo` | Runs the nightly demo reset in the cloud now | After editing the seed data, on the demo environment only | `Seeded: {...}` in the job output |

Flags in staging and production are changed in Django admin (Core, Feature flags), where every change is audit-logged;
there is no `make flag` for them.

## When something goes wrong
| Problem | Try |
|---|---|
| "port already in use" | `make down`, then check nothing else uses 3000/3001/8000/5432/6379 |
| Database errors after pulling | `make migrate`; if still broken, `make reset-demo` (local only) |
| App shows a blank screen | `make api-client` (client out of date), then restart `make dev` |
| Docker permission denied | You skipped the `usermod` step or didn't log out and back in |
| App refuses to start | Read the first error line: it names the missing or invalid .env variable |
| A feature is missing in the app | `make flags`: it may be switched off |
| Everything answers 403 `consent_required` | The member has not accepted the current `POLICY_VERSION` (`.env`). Accept it in the app (`POST /api/me/consent`), or run `make reset-demo` for the personas |
| Everything answers 403 `beta_required` | `BETA_MODE=true` and the member has no access: `make invite-codes N=1`, redeem it, or add them in Django admin (Beta → Beta access) |
