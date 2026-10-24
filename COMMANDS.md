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
`gcloud auth login`.

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
| `make mock` | App on :3000 against mock data (no backend, no login). Not available until the frontend data-layer session |
| `make up` / `make down` | Start / stop Postgres + Redis containers |
| `make logs` | Follow container logs |
| `make shell` | Django shell (`manage.py shell`) |
| `make dbshell` | psql into the local database |

## 3. Database and data
| Command | What it does |
|---|---|
| `make migrate` | Apply migrations |
| `make migrations` | Create migrations after a model change (review them before committing) |
| `make reset-demo` | Wipe local data and reload seed + the five demo stories (idempotent) |
| `make reset-demo ENV=demo` | Same on the demo environment (not available until Stage 5; asks for confirmation) |
| `make admin-user USER_NAME=asha` | Create a Django admin user (asks for a password) and print the 2FA setup link (`otpauth://…`) to add to an authenticator app. Run again to reset someone's 2FA |

| `make invite-codes N=10` | Create invite codes for the beta and print each with its one-tap link (`APP_URL/join?code=…&src=invite`). Optional: `USES=5` (people per code, default 1), `DAYS=30` (expiry), `ORG=3` (whoever redeems joins organisation 3), `NOTE="pilot cohort"`. Audit-logged |

`make reset-demo` refuses to run when ENV is staging or production.

## 4. Feature flags
| Command | What it does |
|---|---|
| `make flags` | List every flag and its audience (off / testers / everyone) |
| `make flag NAME=circuits TO=testers` | Change one flag locally |
| `make flag NAME=circuits TO=everyone ENV=staging` | Change it on staging (not available until Stage 5; asks for confirmation; runs as a Cloud Run Job) |

In production, change flags in Django admin only (audit-logged), not from the laptop.
Defaults per environment and when to switch each on: PRODUCTION.md §2b.

## 5. Background jobs (run by hand locally; scheduled in the cloud)
| Command | What it does |
|---|---|
| `make job NAME=compute_matches` | Run any management command as the scheduler would |
| `make jobs` | List all jobs and their cloud schedules |
| `make daily` | Run the 08:00 set: compute_matches, then the Daily Drop (investor picks join in Stage 4f) |
| `make circuit-round` | Run an exchange circuit round now |
| `make job NAME=send_emails` | Send queued emails that are due (invite emails retry here when the provider was down). Scheduled every 5 minutes in the cloud |
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
| `make test-web` | Frontend type check (Playwright + axe arrive with Stage 4) |
| `make e2e [SPEC=premium]` | Playwright journeys and design checks at 375px and 1280px, signed in as demo personas. Needs `make dev` running. `SPEC=premium` runs only `apps/app/tests/premium.spec.ts` (DESIGN.md §13: spacing, one primary button, accent budget, type sizes, truncation) and writes a report to `screenshots/premium/report/` |
| `make lint` | ruff (check + format check), mypy, ESLint (prettier is not installed yet) |
| `make fmt` | Auto-format Python with ruff (TypeScript formatting arrives with prettier) |
| `make check` | lint + backend tests with demo stories PASS/FAIL + frontend type check. Must be green before any push |
| `make smoke URL=https://...` (Stage 5) | Check a deployed environment (sign-in page, CORS, one read, one write, test email) |

## 7. API client
| Command | What it does |
|---|---|
| `make api-client` | Export openapi.json from Django and regenerate packages/api-client (`make openapi` is an alias) |

Run it after any endpoint change; commit openapi.json, the client, the handoff and the
contract test together.

## 8. Build
Only `make build-web` works today. The others print "not available until Stage 5" (the backend image is a placeholder).

| Command | What it does |
|---|---|
| `make build` | Production builds of everything: backend image + app + landing |
| `make build-api` | Backend Docker image for your machine's architecture |
| `make build-api-multiarch` | Backend image for ARM64 + x86_64 (what CI pushes) |
| `make build-web` | `pnpm build` for apps/app and apps/landing |
| `make run-prod-local` | Run the built image + built apps locally with ENV=dev, to check a production build before pushing |

## 9. Deploy (normally done by CI, PRODUCTION.md §10)
Not built yet: these print "not available until Stage 5" and exit 1.

| Command | What it does |
|---|---|
| `make deploy ENV=staging` | Build, push, migrate and deploy staging, then `make smoke` |
| `make deploy ENV=demo` | Deploy the latest release tag to demo, then reset demo data |
| `make rollback ENV=staging` | Route traffic back to the previous Cloud Run revision |

There is no `make deploy ENV=production`: production deploys only through CI with a
manual approval. Every deploy target shows what it will do and asks before running.

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
