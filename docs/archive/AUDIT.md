# Circuit — pre-beta audit

Audit date: 2026-10-27. Branch `audit-prelaunch`, from `main` at `5c6397f` ("changed some toml's").
Read-only: nothing but this file was changed. No cloud commands were run, no secret values were read or printed, nothing was pushed to `main`.

## 1. Summary — can we deploy a minimal invite-only beta today?

**No. Not today, but it is close.** The backend design is sound (secrets are clean, DEMO_AUTH cannot start in production, RLS is on, 3,066 backend tests pass). What stops you is a pile of small, mostly mechanical problems, in two places:

1. **`deploy/gcp/production.toml` is broken.** It is not even valid TOML (the same key appears twice), and even after that is fixed, the backend would refuse to start for three more reasons (backup key placeholder, no LLM key, no `CSRF_TRUSTED_ORIGINS`). Two `<placeholders>` also make `make deploy` stop before it does anything. Roughly 30 minutes of editing, no code.
2. **The app (`apps/app`) does not compile in real mode.** `pnpm --filter app build` fails on 48 TypeScript errors (stale mock data after the API changed). Vercel would fail to build it, so there would be no app to sign in to. This is a frontend session of about half a day, and the backend already did its part.

Even after those, three things will bite you the moment real people use it, and they are listed as HIGH below: the browser-to-API address (CORS) is wrong, invite links point at the wrong path, and nobody can *answer* an intro or connection request in the real app (the buttons were never wired).

Honest scoreboard of the checks I ran (details in section 2):

| Check | Result |
|---|---|
| `git status` | clean at start |
| `make check` | **FAIL** at the first step (ruff format, 4 files). Tests never ran from `make check`, so I ran them separately |
| `make test` (backend pytest) | **FAIL**: 3,066 passed, **39 failed, 57 errors** |
| `pnpm -r typecheck` | **FAIL**: 48 errors in `apps/app` |
| `pnpm -r lint` | pass |
| `pnpm --filter app build` (real mode) | **FAIL** (same 48 type errors) |
| `pnpm --filter landing build` | **FAIL as-is** ("Missing build-time variables"); **passes** with the three variables set |
| `tomllib.load(production.toml)` | **FAIL**: `Cannot overwrite a value (at line 34)` |
| `test:boundary` (screens only talk to hooks) | pass |

Nothing in the failures is a data-loss or secret-leak problem. Most of the 96 test failures/errors come from just **two** causes (the broken TOML file, and the unfinished "B7 part 3" backend commit).

## 2. What I ran (key lines, no secrets)

**git** — `git status`: clean. `git log --oneline -20` ends at `5c6397f changed some toml's`; the history contains the commit `0683834 B7 part 3 (unfinished): F6 API requests ...`, which explains most backend test failures below.

**`make check`** stops at its first sub-step, `make lint`:
```
All checks passed!                       (ruff check)
4 files would be reformatted             (ruff format --check)
make: *** [Makefile:199: lint] Error 1
```
Files: `backend/apps/accounts/api.py:347`, `backend/apps/accounts/highlights.py:22`, `backend/apps/social/api.py:23`, `backend/tests/api/test_b7_f6_api.py:206`. Because `check: lint test test-web test-landing` aborts at the first failure, `make check` currently proves nothing about tests; I ran them one by one.

**`make test`** — `39 failed, 3066 passed, 57 errors in 301s`. Grouped by cause:

| Cause | Count | Where |
|---|---|---|
| `production.toml` does not parse (`TOMLDecodeError: Cannot overwrite a value (at line 34, column 46)`, seen 73 times) | ~58 (all the errors, plus 9 + 3 + 2 failures) | `tests/unit/test_deploy_config.py`, `test_scheduled_jobs.py`, `test_github_workflows.py`, `test_monitoring_config.py`, `test_backup.py`, `test_usage_report.py` |
| `PUT /api/me/highlights` returns **500** (`unhandled`, a `ValueError`) | 6 access-matrix + 2 highlights + 2 contract | `tests/api/test_access_matrix.py`, `test_b7_f6_api.py`, `tests/contract/test_contract.py`, `test_handoff.py` |
| `openapi.json` out of date: `AssertionError: run make openapi` | 1 | `tests/api/test_health.py::test_openapi_spec_is_in_sync` |
| Tests written for the old shapes after B7 part 3 changed them (notification prefs now have a `push` key; a member's posts are now a paged `{items, next_cursor}`; profile strength is 63 not 62) | ~8 | `test_settings.py` (2), `test_unsubscribe.py` (2), `test_reports.py` (1), `test_social_minors.py` (1), `test_b7_profile.py` (1), `test_b7_f6_api.py` (3) |
| A flaky test, **not** a leak: `assert "40" not in str(body)` matches the member id `1140` | 1 | `tests/api/test_b7_startup_page.py:49` (`view_count`/`interest_count` are correctly `None`) |

Demo stories 1–5 all print `PASS` in the pytest summary (no `tests/demo` test failed).

**`pnpm -r typecheck`** — `apps/app typecheck: Failed`, 48 `error TS` lines: `src/data/me.ts(47)`, `src/data/settings.ts(52)` (`"emerald"` not assignable to `ApiAccent`), `src/data/startups.ts(63)` (`privateCounts` can now be `null`), and ~42 in `src/data/mocks/*` (`llm_available`, `read_receipts`, `read_at`, `name`, `mint`...). PROGRESS.md and LAUNCH.md already say this is known ("48 type errors ... left for the frontend session").

**`pnpm -r lint`** — all four packages "Done", exit 0.

**`pnpm --filter app build`** — `Compiled successfully`, then `Running TypeScript ...` fails with the same errors: `Failed to type check.` Exit 1. (The build ran with the existing local `apps/app/.env.local`, i.e. real mode, not `NEXT_PUBLIC_MOCK`.)

**`pnpm --filter landing build`** — as-is: `Error: Missing build-time variables: NEXT_PUBLIC_APP_URL, NEXT_PUBLIC_LANDING_URL, NEXT_PUBLIC_API_URL`. That is by design (`apps/landing/next.config.ts:25`). With those three set to dummy values it builds all 12 pages (`/`, `/students`, `/founders`, `/mentors`, `/investors`, `/partners`, `/privacy`, `/terms`, ...). It also tried to read `/api/config` at build time and, when it could not, "treat[ed] every feature as off" (safe).

**TOML** — `production.toml`: FAIL (line 34). `staging.toml`, `demo.toml`, `app.toml`: parse fine.

**Side effects cleaned up:** the builds rewrote `apps/app/next-env.d.ts` and 39 tracked files under `apps/landing/out/` (finding M3). I restored them with `git checkout`, so the working tree is clean again.

**Not run** (so not covered by this audit): the Playwright suites (`test-web` mock tests, `test-landing`, `e2e`), `make build-api` / `make run-prod-local`, `make smoke`, any `gcloud` command, a real Supabase sign-in, the Docker image on ARM64. Everything about Cloud Run, Vercel, Supabase and Upstash below is read from code and docs, not tried.

## 3. Findings

Format: **ID — title** · where · what/why · fix · size · session. "Session" = which of the two parallel fix sessions should do it (**backend** or **frontend**); "config" items are edits to `deploy/gcp/*.toml` and belong to the backend session, since that is where those files live and are tested.

### BLOCKERS (stop deploy or login)

**BL1 — `production.toml` is invalid TOML** **[fixed in fix-backend]** · `deploy/gcp/production.toml:26` and `:34` (`EMAIL_FROM` twice), `:27` and `:35` (`SUPPORT_EMAIL` twice).
TOML forbids a key appearing twice in a table. `scripts/gcp.py` loads the file with `tomllib` (`gcp.py:163-165`), so every `make gcp-setup/deploy/secret/monitoring` crashes immediately, and ~58 deploy-related tests fail. Looks like new lines were added without deleting the old ones.
Fix: keep one `EMAIL_FROM = "Circuit <support@circuitapp.net>"` and one `SUPPORT_EMAIL = "support@circuitapp.net"`. · **S** · backend (config).

**BL2 — Two `<placeholders>` left; `make deploy` refuses to run** **[fixed in fix-backend]** · `production.toml:35` (`SUPPORT_EMAIL = "<support@circuitapp.net>"`, angle brackets by mistake) and `:48` (`notification_channels = ["<Circuit production on-call email>", "<Circuit production on-call phone>"]`). The check is `find_placeholders` (`scripts/gcp.py:223-235`), enforced at `gcp.py:1235-1240` for every non-dry-run command including `deploy`.
Fix: remove the angle brackets from `SUPPORT_EMAIL`. For the channels, delete the whole `[monitoring]` block for week 1 (monitoring is optional: `gcp.py:184` uses `mine.get("monitoring", {})`; only `make monitoring` needs the names). Cleaner long-term: make `find_placeholders` ignore `monitoring.*` unless the command is `monitoring` (S). · **S** · backend (config).

**BL3 — `BACKUP_AGE_RECIPIENT` is still the sample text** **[fixed in fix-backend]** · `production.toml:31` (`"age1...your public key..."`). `backend/circuit/config.py:172-175` requires `age1` + 58 chars or empty, otherwise the **app refuses to start**. This check runs *first*, which hides the next two blockers until it is fixed.
Fix for week 1: delete the line (empty is valid; see BL8 for the backup job). · **S** · config.

**BL4 — No LLM provider configured** **[fixed in fix-backend]** · `production.toml` has no `LLM_PROVIDER`; the default is `groq` (`config.py:82`) and `config.py:218-222` demands `GROQ_API_KEY` in production. `secrets = ["RESEND_API_KEY"]` (`production.toml:15`) adds no LLM key.
Fix: add `LLM_PROVIDER = "none"` under `[env]` (supported, no key needed; onboarding uses the manual pickers). Add the provider's key to `secrets` later when you turn an LLM on. · **S** · config.

**BL5 — `CSRF_TRUSTED_ORIGINS` missing** **[fixed in fix-backend]** · required in staging/production by `config.py:223-227`; not in `production.toml`. PRODUCTION.md §2a says the pre-domain value is `https://*.run.app`.
Fix: add `CSRF_TRUSTED_ORIGINS = "https://*.run.app"`. · **S** · config.

**BL6 — `REDIS_URL` cannot be left out** **[fixed in fix-backend]** · `config.py:56` (`redis_url: str = Field(min_length=1)`), `config.py:230-233` (must start with `rediss://`), `deploy/gcp/app.toml:31` (shared `secrets` list) and `scripts/gcp.py:793-795` (deploy refuses while the secret has no value). On top of that `core/cache/__init__.py:89` does `redis.Redis.from_url(settings.REDIS_URL)`, which would raise a plain `ValueError` for an empty URL, not the `RedisError` the cache swallows.
> Fixed in fix-backend. Redis is now optional: with no `REDIS_URL` the app reads Postgres and counts rate limits there (one `redis_not_configured` warning at start).
Answer to your question: **No, production cannot start without REDIS_URL today.** Smallest path: create a free Upstash database (2 minutes, Mumbai) and store its `rediss://` address; the app already works fine when Redis is down or slow (it reads Postgres), and `REDIS_LEAN=true` keeps you inside the free plan.
Code change if you really want none (M, backend): make `redis_url` optional (`""`), skip the `rediss://` rule when empty, remove `REDIS_URL` from `app.toml` secrets, and make `get_cache()` return a no-op cache when the URL is empty. Rate limits (`incr_window`) would then not work, which is a safety regression, so I recommend keeping Redis. · **S** (use Upstash) or **M** (code) · backend.

**BL7 — CORS origin does not match the app** **[fixed in fix-backend]** · `production.toml:25` `CORS_ALLOWED_ORIGINS = "https://circuit-app.vercel.app"` but `APP_URL`/`LANDING_URL` are `https://circuit-phi.vercel.app/` (`:19-20`). The browser will block *every* call from the app to the API ("login works, nothing loads"). `make deploy`'s smoke test will **not** catch it, because it reuses the same value as its test origin (`gcp.py:1252`). Also the waitlist form on the landing site is allowed only if `LANDING_URL`'s origin matches (`backend/apps/beta/cors.py:12-19`).
Fix: `CORS_ALLOWED_ORIGINS = "https://circuit-phi.vercel.app"` (exact origin, no slash, no path; the validator at `config.py:160` enforces this), or whatever your real production Vercel domain is. · **S** · config.

**BL8 — The deploy workflow cannot run (CI is red)** **[fixed in fix-backend]** · `.github/workflows/deploy.yml` job `verify` requires a green `ci` check on the exact commit and that it is on `main` (`deploy.yml:39-62`, job `verify`). Today `ci` would fail on `ruff format`, 39 test failures and 48 type errors. Also needs the GitHub Environment `production` variables `WIF_PROVIDER` / `DEPLOY_SA` from `make gcp-setup` (`deploy.yml:10-11`), which do not exist until gcp-setup has been run.
> Fixed in fix-backend. Backend part done (CI lint and backend tests are green); deploying from the laptop is still the week-1 route, and the frontend type errors (BL9) still fail `make check`.
Path around it for week 1: deploy from the laptop with `make deploy ENV=production` (types the environment name instead of `--yes`). Fix the tests and merge to `main` afterwards. · **L** (fix all red) · both sessions.

**BL9 — The app does not compile (real mode)** **[fixed in fix-frontend-h4-h7]** · `apps/app/src/data/me.ts:47`, `data/settings.ts:52`, `data/startups.ts:63`, and 42 errors in `data/mocks/*` (`fixtures.ts`, `handlers.ts`, `discover.ts`, `inbox.ts`, `signup.ts`, `settings.ts`, `profile.ts`, `circuits.ts`). `pnpm --filter app build` exits 1 at "Running TypeScript". Cause: `packages/api-client` was regenerated in B7 (`emerald` instead of `mint`, `llm_available`, `read_receipts`, nullable counts, typed message image...) and the hand-typed mock fixtures were not updated.
Fix: update the mock fixtures and the 3 real-code lines (`ApiAccent` mapping, nullable `privateCounts`). PROGRESS.md "Frontend: switch these hooks" already lists the plan. · **M** · frontend.

### HIGH (breaks a core screen or a CLAUDE.md safety rule)

**H1 — Invite and email links point at the wrong place** **[fixed in fix-backend]** · `production.toml:19` `APP_URL = "https://circuit-phi.vercel.app/"`; `vercel.json` serves the app under **`/app`** (landing at `/`), and `apps/app/next.config.ts:4` sets `basePath` from `NEXT_PUBLIC_BASE_PATH=/app`. The backend builds links as `APP_URL + /join?code=...` (`backend/apps/beta/services.py:55`), `.../settings/export?token=` (`apps/accounts/export.py:225`), `.../unsubscribe?token=` (`notifications/unsubscribe.py:40`), `.../<path>` in notification emails (`notifications/services.py:93`). With the current value they all land on the *landing* site and 404, so **invite codes cannot be redeemed from a link** — the core of an invite-only beta.
Fix (given `vercel.json` as it is): `APP_URL = "https://circuit-phi.vercel.app/app"` and `LANDING_URL = "https://circuit-phi.vercel.app"`; in Vercel `NEXT_PUBLIC_BASE_PATH=/app`, `NEXT_PUBLIC_APP_URL=https://circuit-phi.vercel.app/app`; Supabase redirect URL `https://circuit-phi.vercel.app/app/auth/callback` (the app builds it as `origin + BASE_PATH + /auth/callback`, `apps/app/src/data/auth.ts:32`). Note `config.py:166` accepts a path in `APP_URL`; `CORS_ALLOWED_ORIGINS` must stay origin-only. PRODUCTION.md §2a still describes two separate Vercel projects (`circuit-app-<env>.vercel.app`): update it to match `vercel.json`. · **S** · config + docs (backend).

**H2 — `PUT /api/me/highlights` crashes with a 500** **[fixed in fix-backend]** · `backend/apps/accounts/highlights.py:34-58` (`replace`), router `backend/apps/accounts/api.py:145`. Fails for every role in `tests/api/test_access_matrix.py` ("500 ... internal_error", logged as `ValueError`), and the 2 highlight tests in `tests/api/test_b7_f6_api.py:47`. Part of the commit titled "B7 part 3 (unfinished)". Not reachable from the real app yet (no hook calls it), but it is a live 500 on a public route and it is in the contract. I did not isolate the line; the access-matrix test reproduces it. · **M** · backend.
> Fixed in fix-backend. Cause: the event `member.highlights_set` was never registered in `EVENT_TYPES`.

**H3 — `openapi.json` is stale** **[fixed in fix-backend]** · `tests/api/test_health.py::test_openapi_spec_is_in_sync` fails with "run `make openapi`". The frontend client and the API freeze (`scripts/check_api_freeze.py`, version `1.1.0`) are generated from this file, so the app may be typed against endpoints that differ from what runs. After H2 and the test fixes: `make openapi`, `make api-client`, bump the version if the freeze check asks. · **S** · backend (then frontend re-pulls).
> Fixed in fix-backend. API version is now 1.2.0.

**H4 — Nobody can answer an intro or a connection request in the real app** **[fixed in fix-frontend-h4-h7]** · `GET /api/intros`, `POST /api/intros/{id}/respond`, `POST /api/intros/{id}/rating`, `GET /api/connections/requests` (incoming), `POST /api/connections/requests/{id}/respond`, `DELETE /api/connections/{id}` exist in `openapi.json` but are **not called by any hook** in `apps/app/src/data` (the only calls are `intros.ts:34,51` for the path and sending, and `profile.ts:126` for sending a connection request). People can *send* but the other side has no screen to accept. That is F5/F17 (warm intros, connections), listed as core in CLAUDE.md. FRONTEND_HANDOFF.md §"Intros" documents the shapes. · **L** · frontend.

**H5 — "I'm interested" does nothing** **[fixed in fix-frontend-h4-h7]** · `POST/DELETE /api/startups/{id}/interest` is unused (grep: `interest` appears only as displayed counts in `data/startups.ts:38-78` and `StartupScreen.tsx`). F2 and the unclaimed-profile claim nudge (F3) rely on it: without taps the "N students are interested" number stays 0. · **M** · frontend.

**H6 — Several hooks still run on stand-ins in real mode** **[fixed in fix-frontend-h4-h7, except the startup logo upload and `GET /api/traits`, which no screen needs yet]** (PROGRESS.md "Frontend: switch these hooks from mocks to the real API", not done; LAUNCH.md line 258 unticked):
- `useWhere` / city list: hard-coded `CITIES` (`data/missing.ts:9`, `data/where.ts:35`); `GET /api/cities` unused.
- `useOrganisationSearch`: filters the hard-coded `ORGANISATIONS` array (`data/organisations.ts:4,13`); in a real build "accept the typed name" (`missing.ts:23`). `GET /api/organisations/search`, `/join`, `/leave`, `/mine` unused.
- `useDiscoverSearch`: searches the loaded lists, `GET /api/search` unused; skills in demand makes a second `/api/jobs` call (`GET /api/jobs/skills-in-demand` unused).
- Inbox: `GET /api/conversations/unread-count` and `POST .../decline` unused (dot derived from the list; no Decline).
- Profile photo/logo upload (`PUT/DELETE /api/me/photo`, `/api/startups/{id}/logo`) unused.
- Work-email verification (F7 level 2: `POST /api/me/verify/work-email`, `.../confirm`) unused, so members stay at level 1.
- `POST /api/join/visit` (funnel by `src`) unused; `POST /api/notifications/read-all` unused; `GET /api/intros/capacity` ("2 left") unused; `GET /api/traits` unused.
Promoted and partner items correctly stay mock-only (`home.ts:127`, `discover.ts:198` are gated by `MOCK`; nothing fake leaks into a real build). · **L** in total, can be split · frontend.

**H7 — Partner dashboard (F8) has no screen** **[decided: hidden for week 1, not built]** · `GET /api/dashboard/{gaps,heatmap,network,acceptance}` are unused and `apps/app/src/app/(shell)` has no dashboard route. CLAUDE.md lists the partner dashboard as core (never flagged). Not needed for a student/founder beta, but a `partner_admin` who signs in would find no home. Either hide the partner role from sign-up for week 1 or build it. · **L** · frontend.

**H8 — Under-18 and privacy rules: what I could and could not confirm.** **[fixed in fix-backend]** Confirmed by tests passing: aggregates/counts hidden below 5, `view_count`/`interest_count` are `null` for non-team viewers (B7 fix), PII-in-logs tests (`test_logging_pii*.py`), RLS-on-every-table tests (`test_rls.py`, `test_realtime_rls.py`), under-18 rules in `test_social_minors.py` (all but the one stale shape test above). I spot-checked, not re-proved, each rule. One under-18 test (`test_a_minors_profile_posts_are_a_404_for_strangers_and_visible_to_the_org`) is red only because the response shape changed (a dict with `items` instead of a list) — it still needs to be fixed and re-run so you know the rule holds. · **S** · backend.
> Fixed in fix-backend. The under-18 test now passes; an under-18 profile is a 404 to strangers, so the highlights are unreachable by them.

### MEDIUM

**M1 — `ruff format` fails on 4 files** **[fixed in fix-backend]** (listed in section 2). `make fmt`. · **S** · backend.

**M2 — Stale tests after B7 part 3** **[fixed in fix-backend]** (notification prefs `push`, paged member posts, strength 62→63, unsubscribe email prefs): see table in section 2. Update the expected values. · **S–M** · backend.
> Fixed in fix-backend. Also profile strength now rounds half up (5 of 8 = 63).

**M3 — Build output is committed although `.gitignore` excludes it** · `apps/landing/out/` has 39 tracked files (`git ls-files apps/landing/out`), against `.gitignore` (`/apps/landing/out/`). Every landing build/test shows as a diff (I saw 20 changed). Fix: `git rm -r --cached apps/landing/out`. Also `apps/app/next-env.d.ts` is tracked and Next rewrites it on every build. · **S** · frontend.

**M4 — The app's build does not insist on its public variables** · `apps/app/src/lib/env.ts:2-10` defaults `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_BASE_PATH` to `""`, and `apps/app/src/data/supabase.ts:4-9` makes Supabase `null` when `NEXT_PUBLIC_SUPABASE_URL` / `_ANON_KEY` are missing, so a Vercel build with a typo succeeds and ships an app where sign-in silently does nothing. The landing site already throws (`apps/landing/next.config.ts:25`). Fix: same guard in `apps/app/next.config.ts` for production builds (API URL, Supabase URL and anon key, `NEXT_PUBLIC_BASE_PATH` when you use the shared project). · **S** · frontend.

**M5 — Nightly `backup-db` job will fail in production** **[fixed in fix-backend]** · `deploy/gcp/app.toml:91-96` (`envs = ["production"]`). It needs the `BACKUP_DATABASE_URL` secret (`core/backup.py:219-221`) and an age key (BL3); neither is in `production.toml`, so Cloud Scheduler runs it every night and it errors. Harmless but noisy, and it creates a backup bucket. For "skip backups in week 1": set `enabled = false` on that job in `app.toml` (and adjust `tests/unit/test_backup.py::test_only_production_backs_up_and_the_job_is_nightly`), or simply ignore the failure. Supabase Pro does its own daily backups (RUNBOOK step 1), so there is still a safety net. **Turn it on before you have real member data you care about.** · **S** · backend.
> Fixed in fix-backend. Superseded: the job now logs `skipped: not configured` and exits 0 until `BACKUP_DATABASE_URL` exists.

**M6 — `/unsubscribe` page does not exist in the app** · links in every notification email go to `APP_URL/unsubscribe?token=...` (`notifications/unsubscribe.py:40`). `apps/app/src/app` has no `unsubscribe` route (the one-click `POST /api/unsubscribe` header link works; the human link would 404). Same for the moderation email's `/help/community-guidelines` (`moderation/actions.py:75`, the app has `/settings/help`). · **S–M** · frontend.

**M7 — With `LLM_PROVIDER=none` the app still offers "paste your bio"** · `/api/config` returns `llm_available`, but nothing in `apps/app/src` reads it (grep outside `mocks/`), so the extract step runs and returns nothing before falling back to the manual pickers (`data/onboarding.ts:253`, wrapped in a try, so it should not crash; I did not run it). Hide the paste step when `llm_available` is false. · **S** · frontend.

**M8 — Docs that no longer match the code**
- RUNBOOK step 11 (`RUNBOOK.md:70`) tells you to store `ANTHROPIC_API_KEY`, but `production.toml` neither sets `LLM_PROVIDER` nor lists that secret (BL4).
- RUNBOOK step 19 treats `CSRF_TRUSTED_ORIGINS` as a later domain step; the code needs it from the first start (BL5).
- RUNBOOK step 9 says "CORS = exactly the app address"; the committed value is a different domain (BL7).
- PRODUCTION.md §2a describes separate landing/app Vercel projects and `https://app.<domain>`; `vercel.json` is one project with `/app` (H1).
- PROGRESS.md "Status" still says F6 is waiting for OK and does not mention the unfinished B7 part 3; LAUNCH.md Stage 5 deploy boxes (lines 212-216), Stage 8/9 [YOU] boxes and line 258 are unticked (accurate — that is the work left).
- CLAUDE.md data model list is missing B7's new columns (`members.photo_path`, `read_receipts`, `startups.team_size`, `logo_path`, `jobs.duration_weeks`, `starts_on`, `conversations.declined_by`, `media_uploads.purpose` values) — PROGRESS.md B7 decision #12 says it was left for you.
- COMMANDS.md is in sync: all 60 documented Makefile targets appear in it, and every `make` target named in RUNBOOK.md exists.
- `production.toml:18` has a stale comment glued onto `ENV` ("AI calls per day...") and comments pasted onto lines 22 and 31 — cosmetic, but easy to mis-edit later.
· **S** · backend (docs).

**M9 — Health detail is public** · `GET /api/health/deps` (`backend/core/health.py:85`) returns the state of Postgres, Redis and JWKS without a login. Low risk (no secrets), but it tells an attacker what is down. Consider making it internal-only. · **S** · backend.

### LOW

- **L1** `production.toml:7` commits the billing account ID and `:23` the admin path; `:28-30` commit the grievance officer's name and address. Not secrets (the admin still needs a staff login + TOTP; the officer details are public by law), but the file comment itself says "this file is public", so decide whether the repo is. `ADMIN_PATH` is obscurity only.
- **L2** `min_instances = 0` (`production.toml:11`): first request after a quiet spell takes 5–10 s (documented). Fine for a closed beta; raise to 1 before public launch.
- **L3** The first landing build needs the API to be reachable if you want feature-aware pages: it fetches `GET /api/config` at build time and treats everything as "off" if it cannot (the build still succeeds). Deploy the API first, then build the landing site (RUNBOOK "Landing site: feature flags ... baked in at build time").
- **L4** Docker image, `make gcp-setup`, Workload Identity, Cloud Scheduler, Supabase Realtime with deny-all RLS, and Vercel rewrites have never been exercised against real accounts (the LAUNCH.md boxes say so). Expect first-time friction; the RUNBOOK "When a deploy fails" table covers the common ones.

## 4. Security and privacy results (CLAUDE.md rules)

| Rule | Result |
|---|---|
| Secrets in the working tree | **None found.** `git grep` for `sb_secret_`, `rzp_live_`, `rediss://user:pass@`, `AGE-SECRET-KEY`, `BEGIN ... PRIVATE KEY`, Resend/Groq/Anthropic/Google key shapes and JWTs: only config-validation code, docs and obvious test fixtures (`rediss://default:p@x.upstash.io`, `AGE-SECRET-KEY-1QQQ...`). The only tracked env file is `.env.example` |
| Secrets in git history | **None found.** Pattern searches over all commits: `sb_secret_`, `rzp_live_`, private keys, Resend/Groq/Anthropic/Google keys: 0 commits. Two commits match the broad `rediss://...@` and `AGE-SECRET-KEY` patterns (`9d1eeb6`, `1af2522`), both are the test fixtures above |
| Service-role key reachable from the frontend | **No.** `SUPABASE_SERVICE_ROLE_KEY` appears nowhere under `apps/` or `packages/`; the app uses only `NEXT_PUBLIC_SUPABASE_URL` and the anon key (`data/supabase.ts`). The key is a Secret Manager secret mounted on the backend only (`app.toml:31`) |
| DEMO_AUTH in production | **Impossible.** Startup refuses it (`config.py:136-139`, `core/apps.py:16`); `/api/demo/*` also 404 unless `DEMO_AUTH` and (dev or `DEMO_PUBLIC`) (`core/demo.py:35-37`); `app.toml:38` sets `DEMO_AUTH = "false"` |
| RLS | On for every table, deny-by-default, re-applied after every migrate, and the migration **fails** outside dev if a table is left open (`core/rls.py`, migration `0002`/`0003`). Tests pass |
| CORS / CSRF / hosts | Exact origins only, wildcards rejected (`config.py:158-161`), `ALLOWED_HOSTS=".run.app"` is fine for the pre-domain period, HSTS/secure cookies on outside dev (`settings.py:197-204`). **The configured values are wrong/missing: BL5, BL7** |
| PII in logs | Tests pass (`test_logging_pii.py`, `test_logging_pii_b3.py`); I saw request log lines in test output and they carry only method, path, status, ms, `member_id`, `request_id` |
| Public endpoints | 10 operations have no auth requirement: `GET /api/config`, `/api/health`, `/api/health/deps`, `/api/support/contact`, `GET+POST /api/unsubscribe`, `POST /api/waitlist`, `POST /api/join/visit`, and the two `/api/demo/*` (404 in production). `tests/api/test_access_matrix.py::test_only_public_routes_skip_auth` pins this list |
| Permission / IDOR coverage | `test_access_matrix.py` covers every route by role and 401; plus `test_account_idor.py`, `test_social_idor.py`. 6 matrix cases are red only because of H2 |
| Migrations | `manage.py makemigrations --check --dry-run`: "No changes detected"; no duplicate migration numbers in any app. (I could not run `showmigrations` against a database; the tests migrate a fresh one) |
| Scheduled jobs | `app.toml` lists them with IST schedules (compute-matches 07:30, daily drops 08:00, circuit round Mon 09:00, backup 02:30, every-5-min bundle, ...). `reconcile-payments` and `build-investor-picks` are `enabled=false` (not built yet, matches LAUNCH.md). The test that checks every job is listed cannot currently run (BL1) |

## 5. Frontend ↔ backend wiring (summary)

- The generated client matches the spec: of **97** `api.METHOD("/api/...")` calls in `apps/app/src/data`, **0** point at a path or method missing from `openapi.json` (108 paths, version 1.1.0 — but see H3: the spec file itself is stale).
- **35 endpoints** in the spec are not called by any hook (list in H4–H7: intros inbox/respond/rating, connection requests inbox, interest, dashboard x4, org search/join/leave/mine, search, cities, traits, photo/logo, work-email, unread-count, decline, read-all, join/visit, capacity, skills-in-demand, invites, unsubscribe, support contact, health).
- Auth: Google + email OTP via Supabase JS with PKCE; callback route exists at `apps/app/src/app/auth/callback/page.tsx` → `components/AuthCallback.tsx`; redirect URL is `origin + BASE_PATH + /auth/callback`. Supabase dashboard must list exactly that URL.
- Variables a real Vercel build needs: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_BASE_PATH=/app` (shared project), `NEXT_PUBLIC_ENV=production`, optionally `NEXT_PUBLIC_LANDING_URL` (legal links), `NEXT_PUBLIC_MAP_TILES_URL`. **Do not set** `NEXT_PUBLIC_MOCK`. Landing: `NEXT_PUBLIC_APP_URL`, `NEXT_PUBLIC_LANDING_URL`, `NEXT_PUBLIC_API_URL`, and `NEXT_PUBLIC_JOIN_LIVE=true` once the app is live (default `false` shows waitlist forms instead of app links), or `NEXT_PUBLIC_LAUNCH_MODE=waitlist` + `NEXT_PUBLIC_WAITLIST_URL`.
- Mock-only (correctly gated by `MOCK`, nothing leaks into real mode): promoted slots, partner items in Pulse, profile/startup "extras".

## 6. Landing site

- Builds with 3 variables (section 2). Pages: `/`, `/students`, `/founders`, `/mentors`, `/investors`, `/partners`, `/privacy`, `/terms`.
- Two modes: `NEXT_PUBLIC_JOIN_LIVE=true` → calls to action go to `APP_URL/join?role=<role>&src=<src>` (`apps/landing/src/lib/env.ts:35`); otherwise (default) they open the on-page waitlist form, which posts to `POST /api/waitlist` (the only call the landing site makes to the API; allowed through CORS only from `LANDING_URL`'s origin, `backend/apps/beta/cors.py`). Waitlist mode (`LAUNCH_MODE=waitlist`) never links the app.
- For an invite-only beta you want **JOIN_LIVE=true**, with `NEXT_PUBLIC_APP_URL=https://<domain>/app` (H1), so "Join" lands on the app's invite screen. The partner page stays contact-only unless the `partner_mode` flag is on (`AudiencePage.tsx:45`).

## 7. Minimal beta deploy plan (backend on Cloud Run asia-south1, app + landing on Vercel, invites, no Sentry/monitoring/backups in week 1)

Prerequisite: the backend session (done: `fix-backend`) has fixed BL1–BL8, H1–H3 and H8. The frontend session has done BL9 (and ideally M4, H4). Then:

**What is truly required**

| Thing | Where it is checked | Required for beta? |
|---|---|---|
| `SECRET_KEY` (32+ chars, 10+ distinct) | `config.py:19-25,153` | Yes, secret |
| `DATABASE_URL` (Supabase transaction pooler, port 6543) | `config.py:55,203-208` | Yes, secret |
| `REDIS_URL` (`rediss://`, e.g. free Upstash) | `config.py` | **No** (fixed in fix-backend): leave it out; Postgres does the cache fallback and rate limits. Add it to `secrets` later |
| `SUPABASE_SERVICE_ROLE_KEY` | `config.py:147` (storage) | Yes, secret |
| `RESEND_API_KEY` | `config.py:198`, `production.toml:15` | Yes to *start* (any valid key). Emails only deliver after the domain is verified in Resend; `EMAIL_FROM` must not be `@resend.dev` |
| `SUPABASE_URL` | `config.py:142` | Yes (already set, `production.toml:24`) |
| `LLM_PROVIDER = "none"` | `config.py:218` | Yes, set it; no key needed |
| `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`, `ALLOWED_HOSTS`, `APP_URL`, `LANDING_URL` | `config.py:158-169,223` | Yes, config (BL5, BL7, H1) |
| `TRUSTED_PROXY_HOPS=1`, `BETA_MODE=true`, `FEATURES`, `EMAIL_BACKEND=resend`, `STORAGE_PROVIDER=supabase`, seed city | `config.py:194,214,149` | Yes, already in the file |
| `SENTRY_DSN` | `core/monitoring.py` — empty = Sentry off | **No** |
| `BACKUP_DATABASE_URL`, `BACKUP_AGE_RECIPIENT`, `BACKUP_BUCKET` | `core/backup.py`, `config.py:172` | **No**: the `backup-db` job logs `skipped: not configured` and exits 0 |
| `[monitoring] notification_channels` | only `make monitoring` | **No** — it is `[]` in the file and never blocks `make deploy` |
| GROQ/GEMINI/ANTHROPIC key | `config.py:218-222` | **No** with `LLM_PROVIDER=none` |

**Steps** (commands exactly as in the Makefile; each `make` command prints its plan and asks you to type `production`)

1. [YOU] Supabase production project (Mumbai): `postgis` + `vector` extensions; Google + Email OTP; ES256 signing key; buckets `posts`, `messages`, `avatars`, `private`; Site URL = app address (`https://<vercel-domain>/app`); redirect URLs `https://<vercel-domain>/app/auth/callback` and `http://localhost:3000/auth/callback`. Copy the transaction-pooler address, project URL, anon key, service-role key. (RUNBOOK §A.1–2)
2. [YOU] Upstash Redis is optional now (skip it for week 1). [YOU] Resend: add domain + key. Optional but recommended: verify the sender domain this week so notification emails really arrive.
3. `deploy/gcp/production.toml` is already fixed (fix-backend). Only change a value if your real addresses differ. Check it parses: `python3 -c "import tomllib; tomllib.load(open('deploy/gcp/production.toml','rb'))"`. Check `make deploy ENV=production DRY=1` prints a plan with no "still has values for you to fill in" error.
4. `make doctor` then `gcloud auth login`; `make gcp-setup ENV=production`.
5. Secrets, one by one: `make secret ENV=production NAME=SECRET_KEY` (generate with `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`), `NAME=DATABASE_URL`, `NAME=SUPABASE_SERVICE_ROLE_KEY`, `NAME=RESEND_API_KEY`.
6. `make deploy ENV=production` (from the laptop; migrations run first and the old version keeps serving on failure). Write down the API address from the smoke output.
7. `make smoke URL=<api address> ORIGIN=https://<vercel-domain> EXPECT_ENV=production` — **use your real Vercel origin here**, not the toml value, so a CORS mistake is caught.
8. Vercel (one project, `vercel.json` as committed): set the variables listed in section 5, with `NEXT_PUBLIC_API_URL=<api address>`; redeploy. Landing: `NEXT_PUBLIC_JOIN_LIVE=true` after the app works.
9. First super admin from your laptop (RUNBOOK step 16: `make admin-user USER_NAME=<you>` with the production `DATABASE_URL` in the environment for that one command), sign in at `<api address>/<ADMIN_PATH>`, create invite codes (Beta → Invite codes), add your own email to the allowlist.
10. `make jobs` to see the schedule; `make jobs-run ENV=production JOB=compute_matches`, then `make logs ENV=production JOB=compute_matches` and look for `job.start` / `job.end`. Note `compute_matches` and the Daily Drop need members and seed data first.
11. Sign in with Google from the real app address, redeem an invite, finish onboarding with manual pickers, send yourself an intro.

**Skipped in week 1, with the safety net:** Sentry (errors still appear in Cloud Logging), `make monitoring` (no phone alerts: check `make logs` yourself daily), backups (Supabase Pro's own daily backups; set up `backup-db` before real data matters), staging/demo environments (postponed by PRODUCTION.md), branch protection and the GitHub deploy workflow (deploy from the laptop).

## 8. Fix sessions (ready to paste)

### 8a. Backend / config session

```
Session: pre-beta backend and deploy-config fixes. Branch: fix-prelaunch-backend (from audit-prelaunch
or main once AUDIT.md is merged). Read AUDIT.md first and fix ONLY the findings listed here. Do not touch
apps/ or packages/ (another session is working there). No cloud commands, no pushes to main, no secrets
printed. Explain what you did in plain language; I'm learning. Update COMMANDS.md if a make target changes,
tick/update LAUNCH.md and PROGRESS.md at the end, commit, stop for my OK. make test must be green for the
backend (do not edit apps/).

Config (deploy/gcp/production.toml and app.toml):
1. BL1: remove the duplicate EMAIL_FROM (lines 26/34) and SUPPORT_EMAIL (lines 27/35); one of each, no angle brackets (also BL2).
2. BL2: delete the placeholder [monitoring] block (lines 47-48) for week 1; optionally make scripts/gcp.py
   find_placeholders ignore monitoring.* unless the command is `monitoring`, with a test.
3. BL3: delete BACKUP_AGE_RECIPIENT (line 31).
4. BL4: add LLM_PROVIDER = "none" under [env].
5. BL5: add CSRF_TRUSTED_ORIGINS = "https://*.run.app".
6. BL7 + H1: CORS_ALLOWED_ORIGINS = "https://circuit-phi.vercel.app" (origin only, no slash), APP_URL =
   "https://circuit-phi.vercel.app/app", LANDING_URL = "https://circuit-phi.vercel.app" (ask me first if my real
   Vercel domain is different). Clean the stale comments on lines 18, 22, 31.
7. M5: set enabled = false on [jobs.backup-db] in app.toml for now (and adjust
   tests/unit/test_backup.py::test_only_production_backs_up_and_the_job_is_nightly), with a comment saying to
   turn it on before real data matters.
8. BL6: do NOT make Redis optional; keep it required. Only add a RUNBOOK note that a free Upstash database is
   enough.
After these, `python3 -c "import tomllib; tomllib.load(open('deploy/gcp/production.toml','rb'))"` must pass and
`make deploy ENV=production DRY=1` must print a plan with no placeholder error.

Code and tests:
9. H2: fix the 500 on PUT /api/me/highlights (apps/accounts/highlights.py replace(), router apps/accounts/api.py:145).
   Reproduce with tests/api/test_access_matrix.py and tests/api/test_b7_f6_api.py.
10. M2 + H8: update the stale tests for B7 part 3 (notification prefs now have `push`: test_settings.py,
    test_unsubscribe.py; member posts are paged: test_reports.py, test_social_minors.py; strength 63:
    test_b7_profile.py; contract cases for PUT /api/me/highlights in tests/contract/cases.py). Make
    tests/api/test_b7_startup_page.py:49 not match substrings of ids (flaky).
11. M1: make fmt (ruff format) for the 4 files.
12. H3: make openapi, make api-client, make contract-fixtures; bump the API version only if scripts/check_api_freeze.py
    demands it, and update FRONTEND_HANDOFF.md in the same commit.
13. M9: make /api/health/deps not publicly detailed (or leave it and tell me why).
14. M8: fix the docs: RUNBOOK steps 9, 11, 19; PRODUCTION.md §2a (one Vercel project, /app); CLAUDE.md data model
    list (B7 columns); PROGRESS.md status.
Done when: make lint, make test (backend) all green, Stories 1-5 PASS, production.toml parses.
```

### 8b. Frontend session

```
Session: pre-beta frontend fixes. Branch: fix-prelaunch-frontend. Read AUDIT.md first and fix ONLY the findings
listed here. Do not touch backend/ or deploy/ (another session is working there). If you need a backend change,
add it to BACKLOG.md under "Backend needed" and tell me. Explain in plain language; I'm learning. Follow
CLAUDE.md "Frontend architecture": screens only call hooks in apps/app/src/data, never the client directly.
At the end: tick LAUNCH.md, update PROGRESS.md, commit, stop for my OK.

1. BL9: make `pnpm -r typecheck` and `pnpm --filter app build` (real mode, no NEXT_PUBLIC_MOCK) pass. Update the typed
   fixtures in apps/app/src/data/mocks/* to the regenerated API types (emerald not mint, llm_available,
   read_receipts, read_at, nullable view/interest counts, typed message image, new required fields), and the
   three real-code lines: data/me.ts:47, data/settings.ts:52 (accent), data/startups.ts:63 (nullable privateCounts).
   Remove the mint<->emerald mapping in data/appearance.ts.
2. M3: git rm -r --cached apps/landing/out and apps/app/next-env.d.ts (they are in/under .gitignore intent).
3. M4: make `next build` for apps/app fail in production when NEXT_PUBLIC_API_URL, NEXT_PUBLIC_SUPABASE_URL or
   NEXT_PUBLIC_SUPABASE_ANON_KEY is missing (same style as apps/landing/next.config.ts).
4. H4: build the missing hooks and screens for answering intros and connection requests:
   GET /api/intros?box=received|sent|brokered, POST /api/intros/{id}/respond, POST /api/intros/{id}/rating,
   GET /api/connections/requests?box=incoming, POST /api/connections/requests/{id}/respond,
   DELETE /api/connections/{member_id}. Use FRONTEND_HANDOFF.md for shapes and DESIGN.md for the screens.
5. H5: wire "I'm interested" (POST/DELETE /api/startups/{id}/interest) into useStartup and the Startup/map popup.
6. H6 (do in this order, each as its own commit): useOrganisationSearch -> GET /api/organisations/search (+ join);
   useWhere -> GET /api/cities; useDiscoverSearch -> GET /api/search; skills-in-demand endpoint;
   unread-count and decline in the Inbox; photo upload (PUT /api/me/photo); work-email verification
   (/api/me/verify/work-email + confirm); POST /api/join/visit (useJoinVisit); notifications read-all;
   GET /api/intros/capacity. Delete each stand-in from data/missing.ts as you go.
7. M6: add an /unsubscribe page in the app (token from the query string, calls GET/POST /api/unsubscribe) and
   make the help link target an existing route.
8. M7: hide the "paste your bio" step when /api/config says llm_available is false.
9. H7 (ask me before starting): partner dashboard screen from GET /api/dashboard/{gaps,heatmap,network,acceptance}
   or hide the partner role at sign-up for the first beta.
Keep promoted and partner Pulse items on mocks (backend not built). Done when: pnpm -r typecheck, pnpm -r lint,
pnpm --filter app build (real mode), pnpm --filter landing build (with the 3 variables), and the Playwright mock
suites (make test-web, make test-landing) are green.
```

## 9. Order of work

1. Backend/config session: items 1–8 (an hour; unblocks `make deploy`), then 9–14.
2. Frontend session in parallel: items 1–3 first (unblocks the Vercel build), then 4–8.
3. You: the [YOU] accounts in section 7 steps 1–2 while those run.
4. Deploy (section 7). A deploy is possible once backend items 1–8 and frontend item 1 are done; H4 is needed before you invite real people, so they can actually answer each other.
