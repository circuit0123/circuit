# Every command a human runs. `make help` lists them; COMMANDS.md explains each one.
# Targets whose feature is not built yet say so and exit 1 instead of pretending.

BACKEND = uv run --directory backend
MANAGE  = $(BACKEND) python manage.py
ENV    ?= local
unexport ENV   # ENV here means "which deployment" for these targets; Django's own ENV comes from .env

define not_yet
	@echo "'$(1)' is not available until $(2)."; exit 1
endef

.DEFAULT_GOAL := help
.PHONY: simulate train ranker-report help doctor setup dev api app landing mock up down logs shell dbshell migrate migrations \
	reset-demo admin-user invite-codes flags flag job jobs daily circuit-round retention export delete-account eval test test-web e2e lint fmt check \
	smoke api-client openapi build build-api build-api-multiarch build-web run-prod-local deploy rollback

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

mock: ## App on mock data, no backend (not built yet)
	$(call not_yet,mock,the frontend data layer session)

up: ## Start Postgres + Redis containers
	docker compose up -d --wait

down: ## Stop Postgres + Redis containers
	docker compose down

logs: ## Follow container logs
	docker compose logs -f

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
	$(call not_yet,reset-demo ENV=demo,Stage 5 (deploy staging and demo))
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
	$(call not_yet,flag ENV=$(ENV),Stage 5 (deploy staging and demo))
endif

# -- background jobs -----------------------------------------------------------------------
job: ## Run any management command: make job NAME=compute_matches
	@test -n "$(NAME)" || { echo "usage: make job NAME=compute_matches"; exit 1; }
	$(MANAGE) $(NAME)

jobs: ## List the jobs and when they should run in the cloud
	@printf '%s\n' \
	  'compute_matches      daily' \
	  'build_daily_drops    08:00 IST, after compute_matches' \
	  'run_circuit_round    weekly' \
	  'expire_items         every 15 minutes' \
	  'send_emails          every 5 minutes (retries emails the provider refused)' \
	  'build_exports        every 5 minutes (builds the data exports members asked for)' \
	  'delete_accounts      every 5 minutes (finishes the account deletions members asked for)' \
	  'retention_cleanup    daily (purges stale accounts, export files, old waitlist entries, old ranker snapshots)' \
	  'train_ranker         weekly (trains a candidate ranker; a super admin promotes it in Django admin)' \
	  '(build_investor_picks, reconcile_payments: added by their stages)' \
	  'Cloud schedules are created in Stage 5.'

daily: ## The 08:00 set: matches, then the Daily Drop (investor picks arrive with Stage 4f)
	$(MANAGE) compute_matches
	$(MANAGE) build_daily_drops

circuit-round: ## Run an exchange circuit round now
	$(MANAGE) run_circuit_round

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

test-web: ## Frontend type check (Playwright + axe arrive with Stage 4)
	pnpm typecheck
	@echo "note: Playwright and axe tests are not set up yet (LAUNCH.md Stage 4)."

e2e: ## Playwright (needs `make dev` running). SPEC=premium runs only the design checks
	pnpm --filter @circuit/app exec playwright test $(if $(SPEC),$(SPEC),)

lint: ## ruff, mypy, ESLint
	$(BACKEND) ruff check . && $(BACKEND) ruff format --check . && $(BACKEND) mypy .
	pnpm lint

fmt: ## Auto-format Python (prettier is not installed yet)
	$(BACKEND) ruff check . --fix && $(BACKEND) ruff format .

check: lint test test-web ## Everything: lint, tests with demo story PASS/FAIL, frontend types. Green before any push

smoke: ## Check a deployed environment (not built yet)
	$(call not_yet,smoke,Stage 5 (deploy staging and demo))

# -- API client ----------------------------------------------------------------------------
api-client: ## Export openapi.json from Django and regenerate packages/api-client
	$(MANAGE) export_openapi ../packages/api-client/openapi.json
	pnpm api:generate

openapi: api-client ## Same as api-client

# -- build ---------------------------------------------------------------------------------
build: ## Production builds of everything (not built yet)
	$(call not_yet,build,Stage 5 (the backend image is a placeholder))

build-api: ## Backend Docker image (not built yet)
	$(call not_yet,build-api,Stage 5 (the backend image is a placeholder))

build-api-multiarch: ## Backend image for ARM64 + x86_64 (not built yet)
	$(call not_yet,build-api-multiarch,Stage 5 (the backend image is a placeholder))

build-web: ## pnpm build for the app and the landing site
	pnpm build

run-prod-local: ## Run the production build locally (not built yet)
	$(call not_yet,run-prod-local,Stage 5 (the backend image is a placeholder))

# -- deploy (no production target: production deploys only through CI with approval) -------
deploy: ## Deploy staging or demo (not built yet)
	$(call not_yet,deploy,Stage 5 (deploy staging and demo))

rollback: ## Route traffic to the previous revision (not built yet)
	$(call not_yet,rollback,Stage 5 (deploy staging and demo))
