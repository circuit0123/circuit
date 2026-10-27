# Every command a human runs. `make help` lists them; COMMANDS.md explains each one.
# Targets whose feature is not built yet say so and exit 1 instead of pretending.

BACKEND = uv run --directory backend
MANAGE  = $(BACKEND) python manage.py
ENV    ?= local
unexport ENV   # ENV here means "which deployment" for these targets; Django's own ENV comes from .env

GCP = python3 scripts/gcp.py   # standard library only; talks to Google Cloud through the gcloud command
define need_env
	@case "$(ENV)" in production|staging|demo) ;; *) echo "usage: make $(1) ENV=production|staging|demo"; exit 1;; esac
endef

define not_yet
	@echo "'$(1)' is not available until $(2)."; exit 1
endef

.DEFAULT_GOAL := help
.PHONY: landing-screens simulate train ranker-report help doctor setup dev api app landing mock up down logs shell dbshell migrate migrations \
	reset-demo admin-user invite-codes flags flag job jobs daily circuit-round retention export delete-account eval test test-web test-landing e2e lint fmt check \
	smoke load-test funnel api-freeze api-client openapi contract-fixtures build build-api build-api-multiarch build-web run-prod-local deploy rollback gcp-setup secret jobs-run monitoring backup-now restore-drill usage-report job-health

help: ## List every command
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_-]+:.*## / {printf "  \033[1m%-22s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# -- setup and running ---------------------------------------------------------------------
doctor: ## Check tools and .env variables (never prints values)
	@bash scripts/doctor.sh

setup: ## Install deps, start Postgres/Redis, migrate, load demo data
	pnpm install
	uv sync --directory backend
	docker compose up -d --wait
	$(MANAGE) migrate
	$(MANAGE) reset_demo

dev: up ## API + app + landing together (Ctrl+C stops all three)
	@trap 'kill 0' EXIT INT TERM; \
	$(MANAGE) runserver 8000 & \
	pnpm --filter @circuit/app dev & \
	pnpm --filter @circuit/landing dev & \
	wait

api: ## Only the Django API on :8000
	$(MANAGE) runserver 8000

app: ## Only the product app on :3000
	pnpm --filter @circuit/app dev

landing: ## Only the landing site on :3001
	pnpm --filter @circuit/landing dev

landing-screens: ## Re-render the landing site's app pictures (AVIF, WebP, PNG) from docs/design-reference: make landing-screens [SCREENS="map job"]
	node scripts/landing-screens.mjs $(SCREENS)

mock: ## App on mock data on :3000, no backend and no login. Switch scenario in the banner, or add ?scenario=empty to the address
	pnpm --filter @circuit/app dev:mock

up: ## Start Postgres + Redis containers
	docker compose up -d --wait

down: ## Stop Postgres + Redis containers
	docker compose down

logs: ## Local: follow container logs. In the cloud: make logs ENV=production [JOB=compute_matches] [LIMIT=50] shows the newest log lines
ifeq ($(ENV),local)
	docker compose logs -f
else
	$(call need_env,logs)
	$(GCP) logs --env $(ENV) $(if $(JOB),--job $(JOB)) $(if $(LIMIT),--limit $(LIMIT))
endif

shell: ## Django shell
	$(MANAGE) shell

dbshell: ## psql into the local database
	$(MANAGE) dbshell

# -- database and data ---------------------------------------------------------------------
migrate: ## Apply migrations
	$(MANAGE) migrate

migrations: ## Create migrations after a model change (review before committing)
	$(MANAGE) makemigrations

reset-demo: ## Wipe local data and reload the seed + five demo stories
ifeq ($(ENV),local)
	$(MANAGE) reset_demo
else ifeq ($(ENV),demo)
	$(GCP) jobs-run --env demo --job reset_demo
else
	@echo "reset-demo refuses to run on ENV=$(ENV)."; exit 1
endif

admin-user: ## Create a Django admin user (USER_NAME=name); prints the 2FA setup link
	@test -n "$(USER_NAME)" || { echo "usage: make admin-user USER_NAME=asha"; exit 1; }
	$(MANAGE) admin_user $(USER_NAME)

invite-codes: ## Create beta invite codes: make invite-codes N=10 [USES=1] [DAYS=30] [ORG=id] [NOTE=text]
	@test -n "$(N)" || { echo "usage: make invite-codes N=10 [USES=1] [DAYS=30] [ORG=<organisation id>] [NOTE=text]"; exit 1; }
	$(MANAGE) invite_codes --count $(N) --uses $(or $(USES),1) $(if $(DAYS),--days $(DAYS)) $(if $(ORG),--org $(ORG)) $(if $(NOTE),--note "$(NOTE)")

# -- feature flags -------------------------------------------------------------------------
flags: ## List every flag and its audience
	$(MANAGE) flags

flag: ## Change one flag: make flag NAME=circuits TO=testers
	@test -n "$(NAME)" -a -n "$(TO)" || { echo "usage: make flag NAME=circuits TO=off|testers|everyone"; exit 1; }
ifeq ($(ENV),local)
	$(MANAGE) flags set $(NAME) $(TO)
else
	@echo "In staging and production, change flags in Django admin (Core -> Feature flags): it is audit-logged and needs no deploy."; exit 1
endif

# -- background jobs -----------------------------------------------------------------------
job: ## Run any management command: make job NAME=compute_matches
	@test -n "$(NAME)" || { echo "usage: make job NAME=compute_matches"; exit 1; }
	$(MANAGE) $(NAME)

jobs: ## List every scheduled job, when it runs (India time) and what it runs, read from deploy/gcp/app.toml
	@$(GCP) jobs --env $(if $(filter production staging demo,$(ENV)),$(ENV),production)

daily: ## The 08:00 set: matches, then the Daily Drop (investor picks arrive with Stage 4f)
	$(MANAGE) compute_matches
	$(MANAGE) build_daily_drops

circuit-round: ## Run an exchange circuit round now
	$(MANAGE) run_circuit_round

backup-now: ## Take an encrypted database backup now. Locally into backend/.backups/ (needs pg_dump, age and BACKUP_AGE_RECIPIENT in .env); in the cloud: make backup-now ENV=production
ifeq ($(ENV),local)
	$(MANAGE) backup_db
else
	$(call need_env,backup-now)
	$(GCP) jobs-run --env $(ENV) --job backup_db
endif

restore-drill: ## Restore the newest backup into a throwaway LOCAL database and check the row counts: AGE_KEY_FILE=~/backup.key make restore-drill [ENV=production]
	python3 scripts/restore_drill.py $(if $(filter-out local,$(ENV)),--env $(ENV))

usage-report: ## Free-tier usage (database, storage, emails, Redis, AI calls) with a warning at 70%: make usage-report [ENV=production]
ifeq ($(ENV),local)
	$(MANAGE) usage_report
else
	$(call need_env,usage-report)
	$(GCP) jobs-run --env $(ENV) --job usage_report
	$(GCP) logs --env $(ENV) --job usage_report --limit 20
endif

job-health: ## Scheduled jobs: last result, last success, overdue ones. Locally your database; in the cloud: make job-health ENV=production runs the watcher once and shows its log
ifeq ($(ENV),local)
	$(MANAGE) job_health
else
	$(call need_env,job-health)
	$(GCP) jobs-run --env $(ENV) --job check_jobs
	$(GCP) logs --env $(ENV) --job check_jobs --limit 30
endif

retention: ## Run the daily clean-up now: stale accounts, expired export files, old rejected waitlist entries
	$(MANAGE) retention_cleanup

export: ## DEV ONLY: build one member's data export now: make export MEMBER=<id>
	@test -n "$(MEMBER)" || { echo "usage: make export MEMBER=<member id>"; exit 1; }
	$(MANAGE) export_member --member $(MEMBER)

delete-account: ## DEV ONLY: delete one member's account (asks to confirm): make delete-account MEMBER=<id>
	@test -n "$(MEMBER)" || { echo "usage: make delete-account MEMBER=<member id>"; exit 1; }
	$(MANAGE) delete_member --member $(MEMBER)

simulate: ## DEV ONLY. Build a synthetic network to test the ML pipeline: make simulate [MEMBERS=400] [RESET=1]
	$(MANAGE) simulate_network --members $(or $(MEMBERS),400) $(if $(RESET),--reset)

train: ## Train a candidate ranker from the feature snapshots (never changes what members see)
	$(MANAGE) train_ranker

ranker-report: ## Intro request / accept rates per ranker arm and model version: make ranker-report [DAYS=28]
	$(MANAGE) ranker_report --days $(or $(DAYS),28)

eval: ## Matching eval set against tests/eval/pairs.json
	$(MANAGE) eval_matching

# -- tests and quality ---------------------------------------------------------------------
test: ## Backend tests (pytest)
	$(BACKEND) pytest -p no:cacheprovider

test-web: ## Frontend: type check, the "only src/data talks to the backend" rule, then Playwright on mock mode (design checks, TabPager touch tests, 404/500, scenarios, PWA, /design, axe). No backend needed
	pnpm typecheck
	pnpm --filter @circuit/app test:boundary
	pnpm --filter @circuit/app test:mock

test-landing: ## Landing site: build, serve and run Playwright (CTAs, waitlist, reduced motion, axe, premium rules). No backend needed
	pnpm --filter @circuit/landing exec playwright test

e2e: ## Playwright journeys against the real API (needs `make dev` running): sign-in and shell. SPEC=premium runs only the design checks (on mock mode, no backend needed)
ifeq ($(SPEC),)
	pnpm --filter @circuit/app exec playwright test
else
	pnpm --filter @circuit/app exec playwright test -c playwright.mock.config.ts $(SPEC)
endif

lint: ## ruff, mypy, ESLint
	$(BACKEND) ruff check . && $(BACKEND) ruff format --check . && $(BACKEND) mypy .
	pnpm lint

fmt: ## Auto-format Python (prettier is not installed yet)
	$(BACKEND) ruff check . --fix && $(BACKEND) ruff format .

check: lint test test-web test-landing ## Everything: lint, tests with demo story PASS/FAIL, frontend types, landing tests. Green before any push

smoke: ## Check a running API: make smoke URL=https://api.example.com [ORIGIN=https://app.example.com] [EXPECT_ENV=production]
	@test -n "$(URL)" || { echo "usage: make smoke URL=https://... [ORIGIN=https://app.example.com] [EXPECT_ENV=production]"; exit 1; }
	python3 scripts/smoke.py "$(URL)" $(if $(ORIGIN),--origin "$(ORIGIN)") $(if $(EXPECT_ENV),--expect-env $(EXPECT_ENV))

USERS ?= 50,200
load-test: ## Beta-mix load test at 50 and 200 users, p50/p95/errors vs PRODUCTION.md section 9: make load-test URL=http://localhost:8080 [USERS=50,200] [SECONDS=60] [TOKENS=file]. Refuses to run against production
	@test -n "$(URL)" || { echo "usage: make load-test URL=http://localhost:8080 [USERS=50,200] [SECONDS=60] [TOKENS=file with one token per line]"; exit 1; }
	@tokens="$(TOKENS)"; \
	if [ -z "$$tokens" ]; then \
	  tokens=$$(mktemp); $(MANAGE) load_test_tokens --count 200 --out $$tokens || exit 1; \
	fi; \
	lat=$$(sed -n 's/^SEED_CITY_LAT=\([^ #]*\).*/\1/p' .env); lng=$$(sed -n 's/^SEED_CITY_LNG=\([^ #]*\).*/\1/p' .env); \
	$(BACKEND) python -m core.loadtest --url "$(URL)" --tokens "$$tokens" --users $(USERS) --seconds $(or $(SECONDS),60) $(if $(RAMP),--ramp $(RAMP)) \
	  --lat "$${lat:-13.0827}" --lng "$${lng:-80.2707}" $(if $(JSON),--json "$(JSON)")

funnel: ## Sign-up funnel per source (landing click, signed up, beta access, onboarding done, first match action); counts under 5 are hidden: make funnel [DAYS=30]
	$(MANAGE) funnel $(if $(DAYS),--days $(DAYS))

api-freeze: ## Fail if openapi.json changed without a version bump and a FRONTEND_HANDOFF.md update: make api-freeze [BASE=origin/main]
	python3 scripts/check_api_freeze.py --base $(or $(BASE),origin/main)

# -- API client ----------------------------------------------------------------------------
api-client: ## Export openapi.json from Django and regenerate packages/api-client
	$(MANAGE) export_openapi ../packages/api-client/openapi.json
	pnpm api:generate

openapi: api-client ## Same as api-client

contract-fixtures: ## Rewrite packages/api-client/fixtures from the real API (after a deliberate API change; commit the diff)
	UPDATE_FIXTURES=1 $(BACKEND) pytest -p no:cacheprovider tests/contract

# -- build ---------------------------------------------------------------------------------
IMAGE ?= circuit-api

build: build-api build-web ## Production builds of everything: backend image + app + landing

build-api: ## Backend Docker image for your machine's architecture (tagged circuit-api:local)
	docker build -f docker/backend/Dockerfile -t $(IMAGE):local .
	@docker images $(IMAGE):local --format 'built {{.Repository}}:{{.Tag}}, {{.Size}}'

build-api-multiarch: ## Prove the backend image builds for ARM64 and x86_64 (slow: one of them runs under emulation; nothing is pushed)
	docker buildx build --platform linux/amd64,linux/arm64 -f docker/backend/Dockerfile -t $(IMAGE):multiarch .

build-web: ## pnpm build for the app and the landing site
	pnpm build

run-prod-local: ## Run the built backend image against the local Postgres/Redis (ENV=dev from .env) on :8080, to check the production build before pushing
	@docker image inspect $(IMAGE):local >/dev/null 2>&1 || { echo "Build it first: make build-api"; exit 1; }
	@# docker's --env-file keeps "# comments" in values, unlike the .env reader Django uses, so strip them into a temporary file first
	@f=$$(mktemp) && sed -E 's/[[:space:]]+#.*$$//' .env > $$f && \
	  docker run --rm --network host --env-file $$f -e DEBUG=false -e PORT=$(or $(PORT),8080) $(IMAGE):local; rc=$$?; rm -f $$f; exit $$rc

# -- Google Cloud (PRODUCTION.md, RUNBOOK.md "First production deploy"). Each prints its gcloud commands and asks you to type the environment name
gcp-setup: ## One-time per environment: turn on Google Cloud services, create the image repository, service accounts, empty secrets, budget alerts
	$(call need_env,gcp-setup)
	$(GCP) setup --env $(ENV)

deploy: ## Build the image, run migrations, deploy a new revision, smoke-test it, switch traffic: make deploy ENV=production (add DRY=1 to only print the plan)
	$(call need_env,deploy)
	$(GCP) deploy --env $(ENV) $(if $(DRY),--dry-run)

rollback: ## Send traffic back to the previous revision (or REVISION=name): make rollback ENV=production
	$(call need_env,rollback)
	$(GCP) rollback --env $(ENV) $(if $(REVISION),--revision $(REVISION)) $(if $(DRY),--dry-run)

secret: ## Store a new value for one secret (typed at a hidden prompt): make secret ENV=production NAME=SECRET_KEY
	$(call need_env,secret)
	@test -n "$(NAME)" || { echo "usage: make secret ENV=production NAME=SECRET_KEY"; exit 1; }
	$(GCP) secret --env $(ENV) --name $(NAME)

monitoring: ## Create or update the uptime checks, log metrics and alert policies in infra/monitoring/: make monitoring ENV=production (add DRY=1 to only print them)
	$(call need_env,monitoring)
	$(GCP) monitoring --env $(ENV) $(if $(DRY),--dry-run)

jobs-run: ## Run one job in the cloud now and wait: make jobs-run ENV=production JOB=compute_matches
	$(call need_env,jobs-run)
	@test -n "$(JOB)" || { echo "usage: make jobs-run ENV=production JOB=compute_matches   (make jobs lists them)"; exit 1; }
	$(GCP) jobs-run --env $(ENV) --job $(JOB)
