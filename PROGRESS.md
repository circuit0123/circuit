# Circuit — Progress

Stages 1–2 are merged into `main` (PR #1, from `backend-core`). Stage 3 continued on `backend-core` (you chose to keep it). Stage 3b is on its own branch, `stage-3b` (from `backend-core`). Backend only for now.

## Status
- Audit fixes, frontend (branch `fix-frontend-h4-h7`, from `main`): **in progress**. BL9 done (the app compiles: mock fixtures follow the regenerated API client; the mint/emerald mapping is gone). H4 done: Inbox has a "Waiting for you" section (connection requests, intros through you, intros for you; accept/decline/pass on) and "Your intros" with the 1–5 rating; a connected profile has Remove connection behind a confirm. Hooks: `useConnectionRequests`, `useRespondConnection`, `useIntros`, `useRespondIntro`, `useRateIntro`. Mock scenario `requests`. Tests: `tests/intros.spec.ts`. Also fixed test flakes: axe now waits out the 250ms accent crossfade (`inBothThemes`), and the Inbox "Yesterday" fixture no longer depends on the time of day. H5 done: students get "I'm interested" on the Startup page and in the map popup (`useInterest`, optimistic, put back on failure; founders and other roles see no button). H6 done, one commit each: organisation search, cities, Discover search + skills in demand, Inbox unread dot + Decline, profile photo (sign-up step and Edit profile), work-email verification (Settings → Verification), join-link funnel count, Mark all as read, intros left this week. Stand-ins for these are gone from `missing.ts`. Not done: the startup logo upload (needs an edit screen for the startup team) and `GET /api/traits` (no screen picks traits). H7 decided: the partner dashboard is not built for week 1; partner sign-up is hidden instead. The Role question has no partner row (`partner_mode` is not a built feature), the landing site's `/partners` shows the contact form while `partner_mode` is off, and the app now ignores `role=partner` on `/join` links so nobody is skipped past Role into the student path. A `partner_admin` made in Django admin would still have no home screen.
- Audit fixes, backend (branch `fix-backend`, from `main`): **done, waiting for your OK**. Every BLOCKER and HIGH finding that AUDIT.md gives to the backend is fixed, one commit each (`fix(audit #<id>)`), each with a test. Details in "Audit fixes, backend" below.
- L5 — landing cleanup, old "How it works" steps removed: **done, waiting for your OK** (branch `landing-remove-old-steps`, from `main`; details in "L5" below)
- F6 — profiles, build log composer and post view, Settings (Appearance, privacy, notifications, export, delete, help, legal): **done, waiting for your OK** (branch `frontend-f6`, from `main` after F3–F5; frontend only, mock mode; details in "F6" below)
- B6 — monitoring, job health, backups, free-tier guards, CI/CD, backend (Stages 8 + 9, backend boxes): **done, waiting for your OK** (branch `backend-b6`; code only, nothing deployed; "Cloud setup I must run later" and the decisions are in "B6" below)
- B5 — deployment code for Google Cloud, backend (Stage 5, backend boxes): **done, waiting for your OK** (branch `backend-b5`; code only, nothing deployed; staging and demo postponed until before payments or public launch; details in "B5" below)
- F3 — Home (Live wire, Update view, Daily Drop, Pulse, Notifications, desktop Home, intro request flow), **done, waiting for your OK** (branch `frontend-f3`, from `frontend-F2`; details in "F3" below)
- F2 — sign-up and access, **done, waiting for your OK** (all four parts: `/join`, sign-in, consent, invite, waitlist and sign-up steps 4–14; branch `frontend-F2`) (details in "F2" below)
- F1 — app foundation (theme, components, shell, data layer, mock mode, PWA basics, /design, design checks): **done, waiting for your OK** (branch `frontend-F1`) (details in "F1" below)
- L3 — landing motion (DESIGN.md §7) on all six pages: **done, waiting for your OK** (branch `landing-pages`) (details in "L3" below)
- L2 — landing audience pages (F14): **done, waiting for your OK** (branch `landing-pages`, from `frontend-landing`) (details in "L2" below)
- L1 — landing site home page (F14, first part): **done, waiting for your OK** (branch `frontend-landing`) (details in "L1" below)
- B4 — matching ML pipeline + onboarding state, backend (Stage 4c): **done, waiting for your OK** (branch `backend-b4`) (details in "B4" below)
- B3 — settings, notifications, report/block, export/delete, consent, legal drafts, backend (Stages 6 + 7): **done and merged** (PR #12, `backend-b3`) (details in "B3" below)
- B2 — invite-only beta, backend (Stage 4b): **done and merged** (PR #11, `backend-b2`) (details in "B2" below)
- B0 — feature flags + commands: **done and merged** (PR #9, #10, `backend-b0`) (details in "B0" below)
- Stage 1 — Backend foundation: **done and merged**
- Stage 2 — Auth and security: **done and merged** (make check green: ruff, mypy, 321 tests; finecomb audit done, findings fixed)
  - One box stays open on purpose: rate limits on extraction/intros/applications/reports/claims. Extraction, intros, applications, claims and org join now use `check_rate`. Reports now exist too (Stage 3b, `POST /api/reports`, limited to 10 a day), so that box can be ticked.
- Stage 3b — Social API (F15–F17): **done, waiting for your OK** (make check green: ruff, mypy, 1657 tests, Story 1–5 PASS; details in "Social API" below)
- Stage 3 — Core features API: **done, waiting for your OK** (make check green: ruff, mypy, 1109 tests, Story 1–5 all PASS)
  - Part 1 (committed): members/profile, onboarding extraction, work-email verification, startups nearby/map/views/interest, claim flow.
  - Part 2: jobs and applications (F11), in-app notifications, strict list of event types (`EVENT_TYPES`; an unknown type raises).
  - Part 3: matching (F4). `manage.py compute_matches` (1.3 s for the 300-member seed), `GET /api/matches`, `manage.py eval_matching` with 14 hand-labelled pairs, demo story 1 test.
  - Part 4: warm intros (F5), exchange circuits (F6), partner dashboard (F8), verification badge tests (F7), demo stories 2–5, and `make check` printing `Story n: PASS/FAIL` (marker `@pytest.mark.story(n)` plus a summary hook in `tests/conftest.py`).

## Audit fixes, backend (branch `fix-backend`): done, waiting for your OK
Scope: AUDIT.md findings for the backend, BLOCKER then HIGH. No `apps/` changes; `packages/api-client` was regenerated.

**Fixed (see AUDIT.md, each marked "fixed in fix-backend")**
- BL1 `production.toml` was invalid TOML (repeated keys). A new test parses every `deploy/gcp/*.toml`.
- BL2 `<placeholder>` check: alert channels only block `make monitoring`, never `make deploy`; `[monitoring] notification_channels = []` in production. The "fill these in" error now lists each value with a one-line hint. `make monitoring` with no channels prints its message instead of a traceback.
- BL3 `BACKUP_AGE_RECIPIENT` sample removed; the `backup-db` job logs `skipped: not configured` and exits 0 while `BACKUP_DATABASE_URL` is empty (it is not mounted as a secret yet).
- BL4 `LLM_PROVIDER = "none"` in production. BL5 `CSRF_TRUSTED_ORIGINS = "https://*.run.app"`. BL7 CORS = `https://circuit-phi.vercel.app`.
- BL6 Redis optional: empty `REDIS_URL` = cache off, rate limits count in Postgres, `/ready` says `redis: not_configured`, one `redis_not_configured` warning at start. A set value must still be `rediss://`. `REDIS_URL` moved from the shared secrets to staging/demo; add it to production `secrets` when you create Upstash. (This changes AUDIT's advice "keep Redis required", as you asked.)
- BL8 backend part: `ruff format`, one mypy error, and the stale B7 tests. CI lint and all backend tests are green. A real bug found on the way: the deploy script took `Circuit <support@...>` for a placeholder, so `make deploy` would have refused to run. Fixed and tested against the file as committed.
- H1 `APP_URL = https://circuit-phi.vercel.app/app`, `LANDING_URL = https://circuit-phi.vercel.app`; PRODUCTION.md §2a describes the one-project layout.
- H2 `PUT /api/me/highlights` 500: the event `member.highlights_set` was not in `EVENT_TYPES`.
- H3 openapi.json, api-client and contract fixtures regenerated; API version 1.2.0; FRONTEND_HANDOFF.md section 3 updated. The frontend session must re-pull `packages/api-client`.
- H8 the under-18 posts test was updated and passes. Also: profile strength now rounds half up (5 of 8 = 63).

**Not done here (frontend or later)**: BL9 and H4–H7 (frontend). `make check` still stops at the frontend type check until BL9 is done.

**After beta (MEDIUM/LOW, not touched)**
- M3 committed build output (`apps/landing/out`, `next-env.d.ts`); M4 app build should insist on its public variables; M6 `/unsubscribe` page and help link in the app; M7 hide "paste your bio" when `llm_available` is false (all frontend).
- M8 remaining doc drift: RUNBOOK step 9 and 19 wording, and the CLAUDE.md data-model list (B7 columns), which needs your OK because it is a CLAUDE.md edit.
- M9 `/api/health/deps` is public.
- L1 billing account, admin path and grievance officer details are committed (the file says it is public); L2 `min_instances = 0`; L3 build the landing site after the API is up; L4 nothing has been tried against real Google/Vercel/Supabase accounts yet.
- Turn backups on (`BACKUP_DATABASE_URL`, `BACKUP_AGE_RECIPIENT`, add to `secrets`) before real data matters.

## B7 part 2 — load test, cleanup, funnel, RUNBOOK and API freeze, backend (branch `backend-b7-2`): done, waiting for your OK
Built in the `../circuit-b7` worktree from `origin/main`. Your local `main` has an unpushed commit "hello" (landing build files, screenshots); I left it alone and moved `/home/klk/circuit` from `backend-b7-2` to `main` (same commit, clean tree) so the branch could live in the worktree. Nothing under `apps/` changed; `packages/api-client` was regenerated. No cloud command, no secret, no push to `main`.

**Checks.** ruff, ruff format and mypy clean; no new `noqa` or `type: ignore`. Backend tests: **3,119 passed, 0 failed** (3,086 before), Stories 1–5 PASS. ESLint clean. Landing tests: 361 passed. **`pnpm typecheck` in `apps/app` is still red with the same 48 errors as at the end of B7 part 1** (the app's typed mocks; you told me not to touch `apps/`), so `make check` as a whole stops at that step until the frontend session fixes them. Everything else it runs is green.

### 1. Load test (`make load-test`)
`make load-test URL=http://localhost:8080 [USERS=50,200] [SECONDS=60] [RAMP=10] [TOKENS=file] [JSON=out.json]` (script `backend/core/loadtest.py`, httpx + asyncio, nothing new installed). Each simulated user signs in, then loops through Home (Drop, Live wire, Pulse), Discover (matches, jobs, nearby, search), Map, a job page and Apply (students), Inbox, and a message (a member with no chats starts one first). It prints p50 / p95 / error rate per endpoint against PRODUCTION.md §9 and exits non-zero on a miss. **It reads `/api/config` first and refuses (exit 2) if the target says `production` or cannot be identified**; unit tests cover both. Locally it mints demo tokens for 200 seeded members (`load_test_tokens`, dev and demo only); for staging you pass real tokens (RUNBOOK.md "Run a load test on staging").

**How I ran it.** `make run-prod-local` (the production image: gunicorn, 2 workers x 4 threads = 8 requests at once, like one Cloud Run instance) on this laptop; Postgres, Redis and the load generator on the same machine; the 300-member demo seed with matches and drops computed. 60 s per level (90 s for the 50-user "after" run), users arrive over 10 s, 0.5–2 s between steps. "Before" = the image at the start of the session (45 s, everyone arriving at once, no ramp); "after" = the final image.

**50 concurrent users**

| Endpoint | Target p95 | Before p50 / p95 | After p50 / p95 | After |
|---|---|---|---|---|
| `GET /api/config` | 300 ms | 83 / 114 ms | 6 / 42 ms | PASS |
| `GET /api/conversations` | 800 ms | 195 / 589 ms | 19 / 80 ms | PASS |
| `GET /api/conversations/unread-count` | 800 ms | 193 / 573 ms | 21 / 93 ms | PASS |
| `GET /api/drop/today` | 800 ms | 380 / 929 ms | 34 / 110 ms | PASS |
| `GET /api/jobs` | 800 ms | 432 / 1010 ms | 50 / 169 ms | PASS |
| `GET /api/jobs/{id}` | 800 ms | 36 / 552 ms | 20 / 78 ms | PASS |
| `GET /api/livewire` | 800 ms | 630 / 1569 ms | 98 / 216 ms | PASS |
| `GET /api/matches` | 300 ms | 395 / 939 ms | 31 / 106 ms | PASS |
| `GET /api/me` | 800 ms | 90 / 159 ms | 10 / 32 ms | PASS |
| `GET /api/pulse` | 800 ms | 628 / 1653 ms | 114 / 260 ms | PASS |
| `GET /api/search` | 800 ms | 388 / 721 ms | 42 / 113 ms | PASS |
| `GET /api/startups/map` | 800 ms | 118 / 654 ms | 37 / 127 ms | PASS |
| `GET /api/startups/nearby` | 800 ms | 389 / 806 ms | 33 / 93 ms | PASS |
| `POST /api/conversations` | 800 ms | 342 / 813 ms | 23 / 118 ms | PASS |
| `POST /api/conversations/{id}/messages` | 800 ms | 292 / 886 ms | 26 / 108 ms | PASS |
| `POST /api/jobs/{id}/apply` | 800 ms | 43 / 559 ms | 18 / 73 ms | PASS |

After: 7,241 requests (80 per second), **no errors, every endpoint inside its target.**

**200 concurrent users.** One container is full here: it answers about 130 requests per second whatever the number of users, so latency is time waiting in line (the median is almost the same for every endpoint).

| Endpoint | Target p95 | Before p50 / p95 | After p50 / p95 | After |
|---|---|---|---|---|
| `GET /api/config` | 300 ms | 449 / 983 ms | 189 / 883 ms | FAIL |
| `GET /api/conversations` | 800 ms | 922 / 1898 ms | 882 / 1302 ms | FAIL |
| `GET /api/conversations/unread-count` | 800 ms | 975 / 2988 ms | 885 / 1300 ms | FAIL |
| `GET /api/drop/today` | 800 ms | 1979 / 4294 ms | 893 / 1346 ms | FAIL |
| `GET /api/jobs` | 800 ms | 2550 / 4199 ms | 1002 / 1398 ms | FAIL |
| `GET /api/jobs/{id}` | 800 ms | 756 / 2413 ms | 884 / 1330 ms | FAIL |
| `GET /api/livewire` | 800 ms | 2585 / 4528 ms | 995 / 1481 ms | FAIL |
| `GET /api/matches` | 300 ms | 2497 / 4318 ms | 958 / 1405 ms | FAIL |
| `GET /api/me` | 800 ms | 3520 / 6735 ms | 306 / 1115 ms | FAIL |
| `GET /api/pulse` | 800 ms | 2849 / 4518 ms | 1045 / 1504 ms | FAIL |
| `GET /api/search` | 800 ms | 2294 / 4019 ms | 961 / 1414 ms | FAIL |
| `GET /api/startups/map` | 800 ms | 1094 / 3101 ms | 921 / 1404 ms | FAIL |
| `GET /api/startups/nearby` | 800 ms | 2459 / 4075 ms | 963 / 1377 ms | FAIL |
| `POST /api/conversations` | 800 ms | 997 / 3594 ms | 857 / 1418 ms | FAIL |
| `POST /api/conversations/{id}/messages` | 800 ms | 963 / 3758 ms | 932 / 1393 ms | FAIL |
| `POST /api/jobs/{id}/apply` | 800 ms | 896 / 1168 ms | 895 / 1382 ms | FAIL |

After: 7,856 requests (131 per second), **0 errors** (before: 4 connection errors in 4,000 requests). Every endpoint is over its p95 target **on one container**. The beta mix at 200 users asks for about 160 requests per second, more than one container answers. Production runs up to `max_instances = 3` with `cpu = "1"` each (`deploy/gcp/app.toml`), which is less CPU per container than this laptop gave the test, so I cannot promise from here that 200 users fit. **The staging run answers that** (see your to-do list). If it fails there, the levers are `max_instances`, `cpu` and `concurrency` in `app.toml` (I was told to stay out of `deploy/`), then `min_instances`.

### 2. What the load test and the query counts found (all fixed, each with a test)
- **Live wire asked the database about every person separately** (mutual connections): 52 queries, now 37, and the same however many cards. `social/relations.mutual_counts`.
- **The jobs list built the full row for every open job (up to 500) and then threw away all but one page.** It still scores and orders all of them, but builds rows only for the page (`jobs/services.list_jobs_page`). **Pulse and Live wire did the same to find a handful of role cards**: they now drop the jobs that don't qualify, and only look inside the window, before building rows. Search uses the page version too. Together these were the biggest cost (Pulse: 628 to 114 ms median at 50 users).
- **gunicorn recycled each worker every ~1,000 requests, and each recycle reset the keep-alive connections it held**: about 1 request in 800 failed with a connection error. Now every ~10,000 (`circuit/gunicorn.py`).
- New `tests/api/test_query_counts.py`: 12 busy endpoints stay inside a query budget (measured: me 5, matches 10, jobs 7, Pulse 28, Live wire 37, Drop 15, conversations 4, search 10, map 5, nearby 5, notifications 4, unread count 7), and matches, jobs and Pulse cost the same number of queries for a page of 3 and a page of 20.
- Not changed, on purpose: `matches` writes one ranker snapshot per request (8 ms; it is the training data). I found no missing index (every endpoint is 4–37 queries on the seed). The seed is small (66 jobs): once there is real volume, re-run the load test and `EXPLAIN` the Jobs and Pulse queries (PRODUCTION.md §14 row 5).

### 3. Cleanup
`core/ist.py` replaces six copies of the India-time arithmetic (`DROP_TZ` and `NOTIFICATION_TZ` became one setting, `APP_TZ`); `core/smallcount.py` is the one "hide counts under 5" rule (startup page, partner dashboard and funnel use it); Live wire uses the matching code's distance function; unused `PULSE_PAGE_SIZE`, `Unauthenticated`, `ErrorResponse` / `ErrorBody` and `graph.best_path` are gone (found by a name sweep; there was no TODO or FIXME left). `tests/unit/test_env_example.py` fails if `.env.example` and the settings drift apart in either direction (the five variables the container reads straight from the environment are listed in the test).

### 4. Funnel
Landing click, signed up, beta access, onboarding done, first match action, per `src`. Django admin → **Metrics** (`/<ADMIN_PATH>/metrics/`; superusers with 2FA; all time, 30 or 7 days) and `make funnel [DAYS=30]`. Counts under 5 show `<5`; real members only (not simulated, not deleted); no names, emails or ids. Steps after "clicks" count members who signed up in the window, so they read as a funnel. "First match action" = the first of `intro.requested`, `drop.swiped`, `connection.requested`. **Clicks needed a new public call, `POST /api/join/visit {src}`** (204; adds 1 to a per-day count in the new `JoinVisit` table, which holds only src, day and count; 120 an hour per address). It is in FRONTEND_HANDOFF.md ("access"), with a contract case and fixture.

### 5. RUNBOOK.md
New "Running the beta": approve a production deploy, revoke an invite code, approve the waitlist, switch a flag, take down a post / profile / startup, run a load test on staging, incident checklist, who to contact, and the PRODUCTION.md §14 manual checks with a date column. Existing sections unchanged. Placeholders in `<…>` are for you.

### 6. API freeze
The API is **1.1.0**, not 1.0.0: B7 part 1 had already published 1.0.0, and adding `POST /api/join/visit` is a new endpoint, so the freeze check would fail this very pull request otherwise. FRONTEND_HANDOFF.md starts with `**API version:** 1.1.0` and a test ties it to `openapi.json`. `make api-freeze [BASE=origin/main]` (`scripts/check_api_freeze.py`, standard library only) fails when `packages/api-client/openapi.json` differs from BASE beyond `info.version` unless the version is higher **and** FRONTEND_HANDOFF.md changed too. CI runs it in the `lint` job against the pull request's base commit. `packages/api-client` was regenerated.

### Decisions and things to know (B7 part 2)
1. **The 200-user numbers fail on one container**, as above. Your call after the staging run: more instances or CPU in `app.toml`, or accept slower pages at peak.
2. **API version 1.1.0**, not 1.0.0 (section 6).
3. **`make load-test` without `TOKENS` mints local demo tokens**, so staging needs a token file; browser tokens last an hour.
4. Running the load test locally leaves a few hundred conversation requests and applications in your dev database (`make reset-demo` clears them).
5. `max_requests` of 10,000 means a leaking dependency is recycled later; Cloud Run caps memory at 1 GiB anyway, and the Sentry triage in RUNBOOK.md covers out-of-memory.

### Frontend remaining (from B7 part 2)
- Call `POST /api/join/visit {src}` once per browser session when `/join` opens with a `src` (fire and forget): add `useJoinVisit` in `apps/app/src/data`.
- Fix the 48 type errors in the app's mocks, then switch the hooks from mocks (the list under "B7 part 1").

### My to-do list (you)
- **Run the load test on staging**: RUNBOOK.md "Run a load test on staging" (10–20 real test accounts, then `make load-test URL=… TOKENS=…`); decide `max_instances` / `cpu` from the result.
- Fill in the `<…>` contacts and the manual-check dates in RUNBOOK.md ("Who to contact", "Manual checks").
- Review and merge the pull request; have the frontend fix the mock types and add `useJoinVisit`.

## B7 part 1 — API handoff and frontend gaps, backend (branch `backend-b7`, from `main` after F5): done, waiting for your OK
Built in a separate git worktree (`../circuit-b7`) so the frontend session's folder was never touched. Nothing under `apps/` changed; `packages/api-client` was only regenerated (`make api-client`). No cloud command was run, nothing was pushed to `main`.

**Checks.** ruff, ruff format and mypy are clean. Backend tests: **3,086 passed** (2,789 before; +297), demo Stories 1–5 PASS. `pnpm lint` is clean. **One check is red and it is meant to be: `pnpm typecheck` in `apps/app` fails with 48 errors**, all in the app's typed mock data (`src/data/mocks/*`, `me.ts`, `startups.ts`). Those fixtures are written `satisfies` the generated API types, so the regenerated client flags exactly what changed (a new required field, `emerald` instead of `mint`, the startup counts now `null`, a typed message `image`). You told me not to edit `apps/`, so they are left for the frontend session; `make check` runs that type check, so **`make check` is red on this branch until the frontend fixes the mocks** (list below). Everything else in `make check` is green.

### What was built, in plain words
1. **Every API gap the screens reported** (28 entries, see "Frontend → API needed": each marked "done in B7" or "not built, on purpose"). Highlights: the age answer now makes a member under 18 on the server; profile photos and startup logos; organisation search and a city list; search across people, startups and roles in one call; People filters; the Startup page and Job page in one call each; decline a message request; unread counts; intro capacity ("2 left"); read receipts (off by default); notification lines that name people; `emerald` instead of `mint`; a first Daily Drop within minutes of finishing sign-up.
2. **The Profile screen in one call** (`GET /api/members/{id}`): photo, headline, organisation (people in the same one only), connection state, what you can do (connect, message, intro), mutual connections, the warm path, a grid of their build logs, closed circuits (mine or a connection's), and on my own profile the strength meter with its one next step.
3. **A privacy fix found during the audit.** `GET /api/startups/{id}` used to send `view_count` and `interest_count` to every viewer; the app only hid them on screen. They are now `null` unless you are on the startup's team, or a founder looking at an unclaimed page (then not under 5). A test sweeps every fixture for fields that must never be sent.
4. **Under-18 rule in one place.** Roles and hiring only from verified (claimed) startups, enforced on jobs, the job page (404), applying (404), the map and nearby, search, skills in demand, Pulse and Live wire.
5. **FRONTEND_HANDOFF.md** (repo root): conventions (errors, lists, flags, gates, under-18, what is never sent, photos, Realtime, rate limits), then one section per screen with hooks, calls, shapes, errors and fixtures, then what is not built yet and what changed.
6. **Contract tests** (`backend/tests/contract/`): one test seeds the demo world at a frozen clock (Monday 2 March 2026, 09:30 IST), runs every screen's calls in every scenario (default, empty, founder, partner, under 18, features off, errors, ...) as the handoff describes, checks each response against `openapi.json`, and compares it with a committed fixture in `packages/api-client/fixtures/<screen>/<scenario>.json` (67 files, `index.json` lists screens → scenarios → hooks). Other tests keep the document and the cases in step (every endpoint named in the document exists, every screen has a section and a case, every endpoint is drawn by a screen or named as outside them with a reason) and sweep the fixtures for forbidden fields. `make contract-fixtures` rewrites the fixtures after a deliberate API change.

### Frontend: switch these hooks from mocks to the real API
Do the mock types first (the 48 errors), then each row. "Stand-in" = what to delete.
| Hook / place | Change | Stand-in to remove |
|---|---|---|
| Mock mode (`make mock`) | Serve `packages/api-client/fixtures/**` (`index.json` lists them) instead of `data/mocks/fixtures.ts` etc.; regenerate the handlers from them | the temporary typed fixtures in `data/mocks/` |
| `useAppearance` | The API says `emerald` | the `mint` ↔ `emerald` mapping in `data/appearance.ts` |
| `useOnboarding` (age, safety) | Just save `answers.age`; the server sets `is_minor` and the under-18 defaults. Re-read `GET /api/me` | the extra `PATCH /api/me/privacy` for minors |
| `useOnboarding` (photo, step 12) | Upload with purpose `avatar`, then `PUT /api/me/photo` | `actions.photo` (type and size only) |
| `useOrganisationSearch` | `GET /api/organisations/search?q=` | `ORGANISATIONS` in `data/missing.ts` |
| `useWhere` | `GET /api/cities` | `CITIES` in `data/missing.ts` |
| Ready (step 14) / `useDailyDrop` | A new member's first drop is built within about 5 minutes: poll `GET /api/drop/today` while `cards` is empty and `next_drop_at` is near | the "arrives tomorrow" fallback |
| `useIntroCapacity` (new) | `GET /api/intros/capacity` → "2 left" in the intro sheet | – |
| `useInboxDot` / `useInbox` | `GET /api/conversations/unread-count`; one subscription on `member:<id>` event `conversation` instead of one per conversation | the list-derived dot, per-conversation channels in `useInbox` |
| `useDeclineRequest` (new) | `POST /api/conversations/{id}/decline` | the mock-only Decline |
| `useConversation` | `message.image` is typed; `read_at` only with read receipts; Settings gets a `read_receipts` switch (`PATCH /api/me/privacy`) | the casts in `data/conversation.ts` |
| `useNotifications` / `useUnreadCount` | `text` already names people; `UnreadCountOut` is a real type | the cast in `data/notifications.ts` |
| `useDiscoverSearch` | `GET /api/search?q=` | search over the loaded lists |
| `useDiscoverPeople` | Pass `role`, `verified`, `capability`, `within_km`; use `headline`, `capabilities`, `photo` | client-side role / verified filters, `headline: ""` |
| `useDiscoverJobs`, `useJob` | `startup_verified`, `startup_logo`, `duration_weeks`, `starts_on`, `contact`, `is_team`; stop calling `useStartup` on the job page | `MissingJobFields`, the extra startup call in `JobScreen.tsx` |
| `useSkillsInDemand` | `GET /api/jobs/skills-in-demand?within_km=10` | the second `/api/jobs` call |
| `useStartup` | `founders` (with `via`), `build_logs`, `logo`, `team_size`; `view_count` / `interest_count` are `null` for most people | `STARTUP_EXTRAS`, the per-founder `useIntroPath`, the type error in `data/startups.ts` (`privateCounts` can now be null) |
| `useMe` | `startup_id`, `has_needs_and_offers`, `photo` (Circuits empty state; founder link) | – |
| `useProfile` (F6) | Draw the whole screen from `GET /api/members/{id}` | – |
| `useCircuits` | Nothing new; `next_step` is now an enum | the `as CircuitStep` cast |
| Pulse partner / promoted slots | **Keep the mocks**: not built (Stages 4d and 4g) | – |

### Decisions and things to know (B7)
1. **`make check` is red on the app type check until the frontend updates its mocks** (above). I did not touch `apps/`. If you would rather have a green branch now, tell me, and I will update `data/mocks` in one commit.
2. **Decline is a marker, not a status.** `conversations.declined_by` keeps `status` as `request`, so the sender sees a quiet unanswered request and cannot send more. The person who declined can still change their mind by writing back.
3. **Under-18 photos are shown only to the member themselves**, not to their connections (stricter than I first planned). They can still upload one so the profile looks the same across devices.
4. **Founders are listed on the Startup page for under-18s too, but with no intro path.** Intros are not available to them.
5. **Search finds people by name only**, never bios, and an under-18 searcher finds only their connections. 120 searches an hour.
6. **"Verified startup" is still "claimed"** (a company-email claim). There is no separate startup verification level.
7. **Requests for under-18s count as 0** in `unread-count`, though an organisation's staff can still message an under-18 member (that conversation is a request). The app has no Requests folder for them, so the count stays 0.
8. **Organisation search lists every organisation** (there is no `verified_at` column until Stage 4g). Joining still needs a code or a verified email.
9. **Pulse partner items and promoted slots are not built**, because the tables they read from (Stages 4d, 4g) do not exist. They break no rule; the planned shape is in FRONTEND_HANDOFF.md §2.
10. **Profile highlights and the GitHub summary** (DESIGN.md Profile) have no model yet and are listed as gaps.
11. **The contract fixtures are made at a frozen clock** (`timezone.now` patched while seeding and calling). Anything that reads the real clock (JWT expiry, rate-limit windows) is unaffected. Re-run `make contract-fixtures` twice and `git diff` is empty.
12. **CLAUDE.md's data model list was not updated** (it is the engineering guide, so I left it for you): the new columns are `members.photo_path`, `members.read_receipts`, `startups.team_size`, `startups.logo_path`, `jobs.duration_weeks`, `jobs.starts_on`, `conversations.declined_by`, and `media_uploads.purpose` now also takes `avatar` and `startup_logo`.
13. **Tests I changed** because behaviour changed on purpose: `test_messaging` (2: `read_at` is present and null; a new-conversation nudge), `test_startups` (3: counts are private), `test_matches` (1: new fields), `test_settings` and `test_account_idor` (accent `emerald`), `test_access_matrix` (new routes).

### New migrations (additive except the first, a data rewrite of `mint` → `emerald`; reversible)
`accounts.0009_accent_emerald`, `accounts.0010_read_receipts`, `accounts.0011_member_photo_path`, `messaging.0004_conversation_declined_by`, `social.0004_alter_mediaupload_purpose`, `startups.0003_startup_logo_path_startup_team_size`, `jobs.0002_job_duration_start`. Run `make migrate`.

### Deploy-side changes to know about (config, not code paths)
- **Create a private Storage bucket named `avatars`** in Supabase (profile photos and startup logos; RUNBOOK.md step lists it). Without it, photo uploads fail with a storage error; nothing else breaks.
- `deploy/gcp/app.toml`: the new job `first_drops` is in the `every-5-min` bundle, and the bundle's memory is now 2Gi (it ranks new members, which loads the member graph like `compute_matches`; idle runs end in seconds).
- New rate-limit keys `search` and `org_search` (`circuit/settings.py`).

### Not verified (needs a real environment)
- Supabase Storage with the `avatars` bucket and signed URLs for it (tested with the in-memory storage).
- The `member:<id>` / `conversation` Realtime event against real Supabase (the existing policy matches any event name on that topic, but it was only tested with the recorder).
- 2Gi is a guess for the bundle: check the first `first_drops` run in the logs once there are real members.

## Frontend → API needed
Things the screens needed that the API did not give. **B7 part 1 handled every entry below** (marked "done in B7", or "not built, on purpose" with the reason). F4's and F5's own lists further down are marked the same way. What the frontend does next is in "B7 part 1" below.
- **Accent name.** `PATCH /api/me/appearance` and `GET /api/me` call the default accent `mint`; DESIGN.md §5 calls it Emerald (and its colours are the Emerald ones). The app maps `mint` ↔ `emerald` in one place (`apps/app/src/data/appearance.ts`), so screens only say Emerald. Rename the value to `emerald` in the backend when convenient (the migration must read old `mint` rows). — **done in B7**: the API says `emerald` (stored rows migrated, `mint` still accepted on write and stored as `emerald`). The app can drop its mapping.
- **Age answer → `is_minor`.** Nothing sets `is_minor` from the Age step; the app saves the answer, shows the safety screen and sets `profile_visibility: hidden`, `allow_requests: false` through `PATCH /api/me/privacy`. The server-side under-18 rules only apply once the age answer sets `is_minor` (and the same defaults). — **done in B7**: `answers.age.adult: false` sets `is_minor` and every under-18 default on the server. Safe version: answering "adult" later never clears it; only a super admin can (Django admin action, audit-logged).
- **Profile photo upload.** `POST /api/media/uploads` only accepts `post` or `message`; the Photo step (12) is shown in mock mode only and only notes the file's type and size (`actions.photo` in `data/onboarding.ts`). Needs an avatar kind on that endpoint (or its own), then the step can be shown for real. — **done in B7**: upload purpose `avatar`, then `PUT|DELETE /api/me/photo`; `photo` on every person object. Safe version: an under-18 member's photo is shown to nobody but themselves.
- **Organisation search** (step 11, "Where do you study?"). No endpoint; real builds accept the typed name as `college`, mock mode searches a marked list (`data/missing.ts`). — **done in B7**: `GET /api/organisations/search?q=` (never a join code or domain; picking one only fills `college`).
- **City list with centres** (step 7, "Choose a city", and naming the city from "Use my location"). `data/missing.ts` holds a marked static list, pilot city first. — **done in B7**: `GET /api/cities`, pilot city first.
- **Instant first Daily Drop for new members** (step 14). Ready shows the first card of `GET /api/drop/today` if there is one, otherwise "your first drop arrives tomorrow". — **done in B7**: job `first_drops` (every 5 minutes, flag `daily_drop`) matches and builds the drop for members who just finished sign-up; `next_drop_at` says "in about 5 minutes" until then. The Ready screen should poll `GET /api/drop/today` for a few minutes.
- **Pulse items for partner calls/events and promoted roles** (F3). `GET /api/pulse` sends neither, so with `partner_mode` / `promotions` on, mock mode shows one stand-in of each (`PARTNER_STAND_IN`, `PROMOTED_STAND_IN` in `data/missing.ts`); a real build draws none. Also needed: a "hide this promotion" call and the "why am I seeing this" sentence per item. — **not built, on purpose**: it needs the promotion and partner tables (Stages 4d and 4g, B3b and B3e), which do not exist yet. Nothing in CLAUDE.md forbids it; promoted items must stay in their own endpoint and never touch ranking. The planned shape is in FRONTEND_HANDOFF.md §2. Keep the mock stand-ins.
- **Intros left this week.** The intro sheet can only react to the 409 (`intro_weekly_limit`, `target_full`). It cannot say "2 left" or when the next one frees up. A `GET /api/intros/capacity` (or the same on `GET /api/me`) would let the sheet warn before Send. — **done in B7**: `GET /api/intros/capacity` `{allowed, weekly_limit, used, left, next_frees_at}`; it says nothing about how full another person is.
- **Unread conversations.** The desktop rail's Inbox dot (Desktop.dc.html) needs a count of unread chats. Not drawn until F5. — **done in B7**: `GET /api/conversations/unread-count` `{chats, requests}` (requests always 0 for under-18s).
- **Notification text.** The reference's lines ("Meera accepted your intro request to Sakthi.") carry more than the API's ("Dr. Lakshmi Narayanan accepted your introduction."). Richer text would be a backend change. — **done in B7**: lines name the people and things ("Meera accepted your intro request to Sakthi."), looked up in bulk. Deleted, suspended and under-18 people are never named (the plain line is used); a decline still does not say who.
- **Two schemas named `CountOut`.** The notification unread count answers `{count}`, but the OpenAPI file keeps the dashboard's `{hidden, value}` shape under the same name. `useUnreadCount` reads the real shape with a cast (`data/notifications.ts`). Give them different names. — **done in B7**: now `UnreadCountOut` and `MaskedCountOut`.

## B6 — Monitoring, backups, free-tier guards, CI/CD, backend (branch `backend-b6`, from `main` after B5): done, waiting for your OK
`make check` is green: ruff, mypy, 2,789 backend tests (Stories 1–5 PASS), frontend type check, 247 app Playwright tests, 361 landing tests. **Code only: no gcloud, gsutil, supabase or GitHub command that creates, changes or deletes anything was run, and nothing was deployed.** I did run real **local** things: `pg_dump` against a scratch database on your local Docker Postgres (dropped afterwards), and the restore drill against a throwaway Postgres container (removed afterwards). Your `circuit_dev` database was not touched. Nothing under `apps/` or `packages/` changed.

One thing for the other session: the new `GET /api/health/jobs` is hidden from the OpenAPI description on purpose (it is for operators, not the app's client), so `packages/api-client/openapi.json` is unchanged and its sync test still passes.

### What was built, in plain words
1. **Monitoring.** Sentry for the backend (`backend/core/monitoring.py`): it is told not to collect personal data at all, and a second filter removes anything that still gets in (headers, cookies, query strings, the user block, request bodies; emails, phone numbers and tokens inside messages). Every error carries `environment` and `release` (the commit). A failed scheduled job is reported with a `job` tag. Cloud Monitoring is code in `infra/monitoring/`: 3 uptime checks, 4 log metrics, 7 alert policies (site down, 5xx rate, slow API, job failed, job overdue, job watcher stopped, free-tier limit). `make monitoring ENV=production` creates or updates them by name (REST API, not alpha gcloud commands).
2. **Job health.** Every job records `last_success_at` and `last_error` (class name plus a short message with emails/phones/tokens masked). `check_jobs` (in the every-5-min bundle) logs `job.overdue` for any job with no success for twice its interval and its own `job.end` is the heartbeat; the deploy script derives each interval from the cron in `app.toml` (`JOB_INTERVALS`). `GET /api/health/jobs` (super admin only, first use of `require_role(..., SUPER_ADMIN)`), `make job-health`, and an Overdue column in Django admin.
3. **Backups.** `backup_db` (02:30 IST, production only): `pg_dump | age` straight into a private bucket, so no readable copy ever exists; only the PUBLIC key is in the cloud. A counts file (table names and row numbers) goes with it. 30-day lifecycle; the API's service account can add files and nothing else. `make backup-now`, `make restore-drill` (restores into a throwaway local Postgres, compares counts, PASS/FAIL per table, never reads `DATABASE_URL`). **Tried for real locally: 63 of 63 tables matched.**
4. **Free-tier guards.** Retention now also removes old events (365 days), notifications (read 90 / any 180) and webhook records (90, skipped until payments exist). Resend budget (90/day, 2,800/month; hard limits 100 and 3,000): optional notification emails become in-app only, invites/exports wait for tomorrow. Redis lean mode (`REDIS_LEAN`: no copies of match lists, dashboards, image links; essential entries live at most 10 minutes). `LLM_PROVIDER=none` (manual pickers, no key, no network) and a daily LLM call cap (`LLM_DAILY_CALL_LIMIT`, counted in Postgres). Uploaded images step their WebP quality down until each size fits a byte budget. Weekly `usage_report` (Mondays 09:00 IST, `make usage-report`) warns at 70% of any limit.
5. **CI.** `.github/workflows/ci.yml`: ruff, ruff format, mypy, then `make check` with a real Postgres (PostGIS + pgvector) container; uv, pnpm, Playwright browser and the database image are cached; a final job `ci` is the one check branch protection should require. Dependabot for actions, uv, npm and docker.
6. **CD.** `deploy.yml` (reusable) + `deploy-staging.yml`, `deploy-production.yml`, `deploy-demo.yml`. Logs in with Workload Identity Federation (no key anywhere; a test fails if one appears), checks the commit is on `main` with a green `ci`, builds x86_64 + ARM64, pushes, then runs the same plan as `make deploy` with `--yes --no-build`. **Automatic rollback:** if the live smoke test fails after traffic moved, traffic goes back to the previous revision. Production is manual and waits for a required reviewer.
7. **RUNBOOK.md "Operating it":** one-time setup, deploy, rollback, restore from a backup, rotate a secret, a job is overdue, Sentry alert triage, site or API is down, a free-tier limit is nearly hit. Every alert's text names its section, and a test checks the section exists.
8. **Make targets** `monitoring`, `backup-now`, `restore-drill`, `usage-report`, `job-health` (in `make help` and COMMANDS.md).

### Decisions for you / things to know (B6)
1. **Product events are now deleted after 365 days** (you chose this; PRODUCTION.md §5 used to say "kept"). The events table still refuses every UPDATE and every DELETE except the retention job's, which switches on a permission for its own transaction (migration `events.0003`). Funnel analytics get a year of history.
2. **I could not install `age` here**, so the local end-to-end test used a stand-in script for `age` (copies the bytes). The `age` command line the code uses is the documented one (`--recipient`, `--output`, `--decrypt --identity`), but **encrypt/decrypt with the real `age` has not run**. The first `make backup-now` and `make restore-drill` on your side are the real test.
3. **The restore drill's scratch Postgres must be at least as new as `pg_dump`.** `pg_restore` cannot read an archive from a newer `pg_dump`. The production image has `pg_dump` 17; the drill container is Postgres 17 (`DRILL_PG_MAJOR`); on this laptop `pg_dump` is 18, so I ran the drill with `DRILL_PG_MAJOR=18`. `docker/postgres/Dockerfile` got a `PG_MAJOR` argument (default 16, so the dev database image is unchanged in content).
4. **A real restore into a fresh Supabase project is the least rehearsed part**: the `public` part is proven by the drill, but putting `auth.users`/`auth.identities` back into a new project (RUNBOOK "Restore from a backup", step 4) is written from documentation. Rehearse it once on a scratch Supabase project. If you are on Supabase Pro, its own dashboard restore brings `auth` and `public` back together and is the simpler route.
5. **Alerts to a phone need a notification channel that only you can create** (email + SMS or the Cloud Console app). `make monitoring` refuses to run, naming the channel, until the names in `production.toml` exist. The "API slow" alert can fire from cold starts alone while min instances is 0 and the beta is quiet; the runbook says how to tell.
6. **The multi-arch image:** the workflow builds x86_64 and ARM64 as you asked and pushes one image index. I believe Cloud Run picks the x86_64 image from an index, but I could not confirm it. If the first deploy complains about the manifest, set `PLATFORMS` in `deploy.yml` to `linux/amd64`. The ARM64 half is built under emulation: the first run takes a long time, later ones use the cache.
7. **Node version in CI is `24`** (`NODE_VERSION` in `ci.yml`); your laptop has a newer one. If the frontend needs the newer one, change that one line.
8. **GitHub actions are pinned by version tag** (`actions/checkout@v4`), not by commit hash, because I could not look hashes up. Dependabot proposes newer tags weekly. Pinning to hashes is the stricter choice if you want it.
9. **The deploy account has project-wide `roles/run.admin`, `artifactregistry.writer`, `cloudscheduler.admin`, `secretmanager.viewer` and `browser`**, plus `serviceAccountUser` on the runtime and scheduler accounts. That is what deploying needs; it cannot read secret values or the database. Each environment's account can only be used by a job in the GitHub Environment of the same name.
10. **LLM daily cap defaults:** production 500 calls/day, staging and demo 1,000 (`*.toml`), 0 (off) on a laptop. `LLM_PROVIDER=none` also works in production (then drop `ANTHROPIC_API_KEY` from `secrets`).
11. **Free-tier settings in the deploy files:** `REDIS_LEAN=true` and `MEDIA_WEBP_QUALITY=75` for all cloud environments (in `app.toml`); on a paid plan set them to `false` / `82`. Redis "commands" in the usage report are the server's total since it started; for the exact monthly count look at the Upstash dashboard.
12. **Changed existing behaviour:** `JobCommand` now records success/error and reports failures to Sentry; `retention_cleanup` reports three more counts; notification emails check the budget first; `flags` read their Redis cache as "essential"; the setup plan reads the project number and now creates the Workload Identity pool, the deploy account and (production) the backup bucket; `plan_setup` no longer says "grants nothing project-wide" (only the deploy account gets project roles; the test says so). Tests I edited: `test_deploy_config` (new placeholders, setup reads the project number, project-wide roles), `test_retention` (new count keys).
13. **New migrations (additive):** `core.0009_jobrun_health` (3 columns), `core.0010_usagecounter` (new table), `events.0003_allow_retention_purge` (replaces the trigger function). Run `make migrate` on your dev database (it was not migrated to B5's `core.0008` either).
14. **Not done:** Sentry in the app (frontend); the timeouts/retries/fallbacks audit (LAUNCH Stage 8); anything in the cloud.

### Unverified assumptions (all on first real run)
- REST shapes for Cloud Monitoring and Logging (`alertPolicies`, `uptimeCheckConfigs`, log metrics) and the exact metric names (`run.googleapis.com/job/completed_execution_count` with a `result` label, `monitoring.googleapis.com/uptime_check/check_passed`); `make monitoring` prints Google's error message if one is wrong, and each file is plain JSON to fix.
- `gcloud storage buckets create ... --public-access-prevention`, `--lifecycle-file`, the Workload Identity flags, and that Debian trixie packages `postgresql-client-17` and `age`.
- That GitHub's `ci` check run is named exactly `ci` (the job id), which the deploy's "green CI" check and branch protection rely on.
- The `check-runs` call needs the `checks: read` permission, which the workflows request.

### Cloud setup I must run later (in this order; every command asks you to type the environment name)
Details and exact commands: RUNBOOK.md "Operating it" → "One-time setup for monitoring, backups and CI".
1. `make migrate` locally (three new migrations), then `git checkout main && git merge backend-b6` via a pull request.
2. Install `age` (`sudo pacman -S age`), run `age-keygen -o backup.key`, store `backup.key` in your password manager and put the PUBLIC key in `deploy/gcp/production.toml` (`BACKUP_AGE_RECIPIENT`). Fill the other `<placeholders>` (including the two notification channel names).
3. Cloud Console → Monitoring → create the **email** and **SMS/phone** notification channels with exactly those names.
4. Sentry: create the project, then `make secret ENV=production NAME=SENTRY_DSN`.
5. Supabase: copy the **session pooler** (port 5432) address, then `make secret ENV=production NAME=BACKUP_DATABASE_URL`. Set a 5 MB file-size limit on the storage buckets.
6. `make gcp-setup ENV=production` (adds the monitoring API, backup bucket, Workload Identity pool and deploy account; prints `WIF_PROVIDER` and `DEPLOY_SA`).
7. GitHub → Settings → Environments → `production`: required reviewers = you; variables `WIF_PROVIDER`, `DEPLOY_SA`. Branches → rule on `main` requiring the `ci` check. Later: `staging` and `demo` environments and the `STAGING_DEPLOY_ENABLED` / `DEMO_DEPLOY_ENABLED` repository variables.
8. `make monitoring ENV=production DRY=1`, read it, then `make monitoring ENV=production`.
9. `make deploy ENV=production` (or run "deploy production" in GitHub) so the new jobs, env variables and the image with `pg_dump` and `age` are live.
10. `make backup-now ENV=production`, then `AGE_KEY_FILE=~/backup.key make restore-drill ENV=production`; write down the minutes and the date in RUNBOOK.md.
11. Rehearse a real restore into a scratch Supabase project once (RUNBOOK "Restore from a backup").
12. Rollback drill (RUNBOOK step 9); then delete the temporary deploy key and the Vercel token from Stage 0 and revoke them at the source.
13. Put a quarterly reminder in your calendar for `make restore-drill`.

### Frontend remaining (from B6)
- **Sentry in the app** (`@sentry/nextjs`, with the same scrubbing idea: no names, emails, tokens; release = `NEXT_PUBLIC_RELEASE`).
- **Resize photos on the phone before upload** (canvas, long side 2000 px): saves the member's data and the 5 MB limit; the server compresses anyway.
- **When the AI is off** (`LLM_PROVIDER=none` or the daily cap is reached) `/api/onboarding/extract` answers `source: "manual"` with empty suggestions; the screens already handle that. A "don't show the paste-your-bio box at all" variant would need a field on `GET /api/config`, which is a contract change for B7.

## B5 — Deployment code for Google Cloud, backend (branch `backend-b5`): done, waiting for your OK
`make check` is green: ruff, mypy, 2,600 backend tests (Stories 1–5 PASS), frontend type check, 247 app Playwright tests, 361 landing tests. **Code only: nothing was deployed and no gcloud, Supabase or other cloud command was run** (`gcloud` is not even installed here). The deploy commands have therefore been tested as printed plans and against fakes, never against real Google Cloud: the first real run is the next session, and it starts with `make deploy ENV=production DRY=1` so you can read every command first.

**Staging and demo are postponed until before payments or public launch.** Production is deployed first, behind BETA_MODE. Everything is written so `ENV=staging|demo|production` work with no code change: you fill in `deploy/gcp/<env>.toml` and run `make gcp-setup ENV=staging`.

**What it is, in plain language.** Your laptop builds one Docker image of the backend. Google Cloud runs that image two ways: as a **service** (the API, answering requests) and as **jobs** (the same image started on a schedule to do background work, such as computing matches at 07:30 India time). A small script, `scripts/gcp.py`, reads two settings files (`deploy/gcp/app.toml` = what is the same everywhere, `deploy/gcp/production.toml` = yours) and turns them into an ordered list of `gcloud` commands. It prints the list, asks you to type `production`, then runs it. Every step is safe to repeat. Secrets live in Google Secret Manager and are handed to the app as environment variables; they are never in the repo or the image.

### What was built (one commit per part)
1. **Image** (`docker/backend/Dockerfile`, `backend/circuit/gunicorn.py`): multi-stage, runs as a non-root user with read-only code, gunicorn with 2 processes × 4 threads (= the 8 requests Cloud Run is told to send at once), the embedding model baked in (Cloud Run's disk is empty on every cold start), the admin's CSS/JS collected at build time (WhiteNoise). 1.6 GB, of which 700 MB is Python libraries. Built and run for both x86_64 and ARM64 (`make build-api-multiarch`; GDAL and LightGBM load on ARM64). `make build-api`, `run-prod-local`, `build-api-multiarch` are real now.
2. **Deploy as code** (`deploy/gcp/*.toml`, `scripts/gcp.py`): service (min 0, max 3 instances, 1 CPU, 1 GiB), one Cloud Run Job per job, one Scheduler trigger per scheduled job (India time), two service accounts with the least they need (the runtime one can read only its own secrets; the scheduler one can only start jobs), budget alerts at 50/80/100%.
3. **Startup checks** (`circuit/config.py`): the app refuses to start on DEMO_AUTH in staging/production, live Razorpay keys outside production, a flag without its dependency, any missing **or empty** required variable, and (new) in staging/production: no real email, fake embeddings, no key for the chosen LLM, no CSRF origins, a Redis address without TLS; also an API/APP/LANDING address that is not a real URL (so an unfilled `<placeholder>` can never start), and port 6543 without `DATABASE_POOLER=transaction`. Each rule has a test for the refusal and for the valid case.
4. **`/health` and `/ready`** (`core/health.py`): answered before host checks, the HTTPS redirect and request logging, so a platform probe works and does not fill the log. `/ready` fails if Postgres is down; Redis down is a warning. Cloud Run's probes use `/health` only (see decision 2). Logs are JSON with `severity`/`message`, a trace link, and gunicorn's/Django's own lines are JSON too (otherwise Cloud Run shows gunicorn's routine startup lines as ERROR).
5. **Jobs** (`core/jobs.py`): ten commands now share one base class: flag off → `skipped: flag off`, exit 0; a database **lease** so two overlapping runs do the work once (one `UPDATE`; session advisory locks do not work through Supabase's transaction pooler); `job.start / job.end / job.skipped / job.failed` as JSON with counts only; non-zero exit on failure so Cloud Run retries. `run_jobs` runs the frequent jobs in one container. Migrations are their own job, run and awaited before a new revision exists, never at container start. Tests prove every job in the code is in `app.toml`, every entry is a real job (or waiting for its code), and the bundle is exactly the bundled jobs.
6. **Scripts**: setup, deploy (build → check secrets → migrate → 0% revision → smoke its private address → move traffic → smoke live → update jobs/schedules), rollback, secret (typed at a hidden prompt, passed on stdin), jobs-run, logs: all in `scripts/gcp.py`, each prints its commands and asks first.
7. **Make targets + COMMANDS.md**: `gcp-setup`, `deploy`, `rollback`, `secret`, `jobs-run`, `logs ENV=…`, `jobs` (generated from `app.toml`), `smoke`; `DRY=1` prints a plan only. A test keeps COMMANDS.md, RUNBOOK.md and the Makefile in agreement.
8. **`make smoke`** (`scripts/smoke.py`): `/health`, `/ready`, `/api/config`, OpenAPI (served except in production, where it must be hidden), protected endpoint refuses a missing and a made-up token, CORS allows exactly your app address and refuses a stranger, security headers. Tested against the local server and against a stub that is wrong on purpose for every check.
9. **Docs**: RUNBOOK.md "First production deploy on Google Cloud" (with troubleshooting, rollback, secret rotation and the monthly cost table), PRODUCTION.md updated (below), CLAUDE.md (gunicorn + whitenoise approved; the JobCommand rule; `job_runs`), `.env.example`, `make doctor` (gcloud optional).

### What changed in PRODUCTION.md
§1 API/jobs/cache/secrets/images rows (min instances 0 for the beta; frequent jobs share one trigger; Upstash free tier; per-secret access); §2 production-first rollout and the laptop deploy; §2a `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`/`API_URL` before a domain, and the domain-mapping options; §6 **PITR is not part of Supabase Pro**; §7 `/health`, `/ready`; new **§7a Database connections** (why the transaction pooler, what it breaks, the lease, the connection arithmetic); §10 the laptop deploy order; §11 cost pointer; §14 rows 6 and 10.

### Decisions for you / things to know (B5)
1. **Supabase PITR costs extra.** Supabase's pricing page lists Pro at $25/month with 7 days of daily backups; point-in-time recovery is an add-on of about $100/month. PRODUCTION.md §6 and LAUNCH Stage 8 assumed "Pro (backups + PITR)". Decide before real members: daily backups lose up to a day. Your Google credits do not cover Supabase.
2. **I changed the probe plan.** I planned `/ready` as a Cloud Run probe; the deploy uses `/health` for startup and liveness. If the liveness probe checked Postgres, a short Supabase outage would make Cloud Run restart every healthy instance in a loop. `/ready` is for `make smoke` and uptime monitors.
3. **`reconcile_payments` has its own 10-minute trigger** (disabled until B3c), not the 5-minute bundle, because CLAUDE.md says every 10 minutes. `build_investor_picks` is disabled until B3d. A test fails the moment either command exists while still disabled, so whoever builds them must switch them on in `app.toml`.
4. **`expire_items` runs every 5 minutes**, not every 15 (it is in the bundle; it is idempotent and cheap).
5. **Production cannot start until you verify an email domain in Resend** (existing rule: `@resend.dev` is refused in production). Same for a real Redis `rediss://` address and a paid LLM key.
6. **There is no monthly LLM spending cap in the code** (PRODUCTION.md §14 row 20 promises one). Set a spend limit in the Anthropic console. Not built here; left for B6.
7. **Cloud Run's custom-domain mapping may not exist in `asia-south1`.** RUNBOOK step 19 says how to check and gives the two fallbacks (Firebase Hosting rewrite, free; load balancer, ~$18/month). Until then the API uses its `*.run.app` address, which is why `ALLOWED_HOSTS` is `.run.app`.
8. **Upstash free tier is 500,000 commands a month.** Rate limits and caches use Redis; if the beta exceeds it the app falls back to Postgres (slower, still correct). Pay-as-you-go would be about $1 for the next 500,000.
9. **Cold starts.** With min instances 0 the first request after a quiet spell takes about 5–10 s. Raise `min_instances` to 1 in `production.toml` (about $8–12/month) before public launch. Estimated total for the closed beta: about $26–32/month, almost all Supabase Pro (RUNBOOK cost table; pricing pages could not be read by my tools, so Google's numbers are estimates: check the pricing calculator).
10. **Unverified assumptions (all on first run):** the exact gcloud flags and YAML shapes (written from documentation, never run); that Cloud Run's address is `https://<service>-<project number>.asia-south1.run.app` (the script computes `API_URL` from it; set `API_URL` explicitly in `production.toml` if it differs); that an org policy does not forbid public (`allUsers`) access to the service.
11. **Extra safety I added because the runbook needs it:** `admin_user` is interactive, so the first admin is created from your laptop against the production database for that one command. That would have let `make reset-demo` do the same, so the four dev-only commands (`reset_demo`, `delete_member`, `export_member`, `simulate_network`) now refuse a non-local database when `ENV=dev` (`core/devguard.py`, tested).
12. **Changed existing behaviour:** the ten job commands print the same summary lines as before, but now also write JSON log lines; `DATABASES` gets `connect_timeout=5`, health-checked connections, and TLS to non-local databases outside dev; empty required variables are now refused; `STATIC` files are served by WhiteNoise. Existing tests I edited: `test_config`, `test_flags`, `test_beta_admin`, `test_audit_stage2`, `test_startup_refusal` (a shared "valid deployed settings" set because the new rules apply to staging/production).
13. **New migration** `core.0008_jobrun` (additive, new table). Run `make migrate` on your dev database.
14. **Not done on purpose:** nothing in Google Cloud, Supabase, Upstash, Resend or Vercel was touched; no CI (Stage 9); no Sentry/uptime monitors (Stage 8).

### Next: the deploy session (Stage 5, deployment boxes)
Follow RUNBOOK.md "First production deploy on Google Cloud" from step 1: accounts, `production.toml`, `make gcp-setup`, secrets, `make deploy ENV=production DRY=1`, `make deploy ENV=production`, smoke, Vercel variables, first admin, rollback drill. Then fix whatever the first real run shows, in `scripts/gcp.py` and its tests.

### Frontend remaining (from B5)
Nothing new. `NEXT_PUBLIC_API_URL` must point at the deployed API address once it exists (RUNBOOK step 15). "Frontend → API needed" above is untouched.

## F6 — Profiles, posting and settings (branch `frontend-f6`, from `main` after F3, F4 and F5): done, waiting for your OK
Frontend only, mock mode only (no backend, keys or login). Screenshots per screen in `screenshots/f6/<screen>/` (375px dark and light, 1280px, and `side-375-dark.png` with the reference on the left where one exists); `node screenshots/f6/shots.mjs` makes them again.

**What it is, in plain language.** **Your profile** shows who you are, what you offer and need, your highlights and your build logs. A small "Profile strength" box (only you see it) says how complete your profile is and gives one next step, then disappears once everything is filled in. **Someone else's profile** has one main button, `Connect`, plus `Message` and "Intro via Meera, mentor" when you share a connection. It shows only "12 mutual connections", never followers. Under-18 members are private to strangers, and strangers can't message them. **The composer** puts photos first: add up to 4, each one is cropped to the build log's frame and shrunk on the phone, then uploads at once with its own progress bar and a Retry if it fails. Then you write (500 characters, with a counter), tag up to 3 skills, add a link and choose who can see it. **A build log's page** has the picture pager, the three reactions with no counts (the author sees their own totals, privately), replies one level deep, and Report (or Delete for your own). **Settings** has everything in one place: edit profile, privacy, notifications per type and channel, Appearance (theme, your colour with a live preview, swipe between tabs), blocked people, export, delete account (type DELETE, then confirm), help, legal pages and Sign out.

- **Profile** (`/profile`, `components/profile/Profile.tsx`, Profile.dc.html):
  - Large title with your name, then the circuit-pattern avatar, "Frontend developer · Chennai", the badge and your organisation, then your bio.
  - `Edit profile` and `Share` (share sheet, or "Link copied."). The settings gear is in the bar on a phone and is a third button on desktop.
  - The strength meter (`StrengthMeter`): bio, offers, needs, a skill with a proof link, first build log (that step only while `pulse` is on). "Only you see this." It hides itself at 100%.
  - "What I offer and need": chips plus highlights (up to 6 tiles).
  - `Build logs · Circuits · About` as a segmented control. Build logs is a 3-column grid of first pictures, and a text-only log shows its first words. Circuits are your current and past circuits. About has the bio, organisation, and skills with level words and "Proof" links.
  - Empty states: "Add what you can offer…" with `Add them`, and "Your build logs show here…" with `New build log`.
  - Under 18: a Private badge and "Your profile is private. Only your connections and people in your organisation can see it."
- **Person** (`/members/[id]`, `components/profile/Person.tsx`, Person.dc.html):
  - 96px avatar, name with badge, "Building a Kannada voice assistant · Chennai · 4 mutual connections".
  - `Connect` (primary). After you tap it: "Request sent", disabled, with a toast. A person you're connected to shows "Connected", and then no intro row.
  - `Message` opens the draft conversation (F5).
  - "Intro via Dr. Lakshmi Narayanan, mentor ›" when the warm path has a mutual. It opens the F3 intro sheet.
  - Offers, Needs, Highlights, then the same three tabs.
  - "…" gives Share profile, `Report Asha` (four reasons, then `Send report`) and `Block Asha` (confirm sheet).
  - Your own id redirects to `/profile`; an unknown id shows the 404.
  - A hidden under-18 profile shows only the name and "This profile is private.": no Connect, no Message, no chips. It doesn't say why, so a stranger isn't told the person's age.
  - Pulse names, match cards and Discover → People tiles now link here.
- **Composer** (`/compose`, `components/compose/Composer.tsx`, Composer.dc.html):
  - Top row: `Cancel` · "New build log" · `Post` pill.
  - "Add up to 4 photos" area (`AddMedia`), then a 2-column grid of `MediaSlot`s with progress, "Didn't upload" + `Retry`, and remove. The `Portrait / Square` frame control is set from the first photo.
  - Tapping a photo opens "Crop and describe": `CropFrame` (drag or arrow keys, rule-of-thirds guide), a required Description (alt text, DESIGN.md §10) and Remove photo.
  - "What did you build or learn?" with "0 / 500".
  - Capability chips (up to 3, from the fixed list, with search).
  - "Who can see this": a sheet with Everyone / Connections / My organisation. Under 18 it starts on My organisation, Everyone is disabled, and it says "Posting to everyone opens once your age is verified."
  - "Add a link" (GitHub, demo, Figma); a bad link blocks Post with a sentence saying why.
  - Under the form, one line says why Post is off (still uploading, a photo failed, a description missing, a bad link).
  - Cancel with something written asks "Discard this build log?".
  - Posting opens the new build log with "Posted.".
- **Post view** (`/posts/[id]`, `components/posts/PostScreen.tsx`):
  - The F3 `PostCard` with the `MediaPager`.
  - `Helpful · Intro me · Let's talk`, with no counts anywhere. "Intro me" opens the intro sheet; "Let's talk" saves the reaction and opens a message. Under 18 there is no "Intro me", as in Pulse.
  - Your own post has no reactions and shows "Only you see this: 4 found it helpful, 1 asked for an intro, 1 reply." `More` gives "Delete this build log?".
  - Replies (`ReplyThread`, one level, `Reply` only on top-level replies; "…" gives Report or Delete).
  - A pinned "Add a reply" box (300 characters; the counter appears near the end) with "Replying to Dr. Lakshmi Narayanan ×".
- **Settings** (`/settings` and nine screens, `components/settings/`, Settings.dc.html):
  - Hub groups: Account (Edit profile with "Ravi Kumar · r•••@gmail.com", Privacy "Members", Notifications "All on", Blocked people), Appearance ("System · Emerald"), Your data (Export my data, Delete account in red), Help (Help and FAQ, Contact support, Privacy policy, Terms, Community guidelines), then `Sign out` and "Circuit beta · Version dev · Policy 2026-10". The version comes from `NEXT_PUBLIC_APP_VERSION`, otherwise "dev".
  - **Edit profile:** Name, About you, City, College or organisation, What I offer (5), What I need (3), Skills with "Proof of work for …" links. `Save` is pinned at the bottom and only works when something changed; Discard changes asks first. The strength meter's steps land on `#bio`, `#offers`, `#needs`, `#skills`.
  - **Privacy:** Everyone / Members / Hidden with what each means; toggles for Visible to my organisation, Show me in circuits and Message requests; Blocked people. Show me in circuits is locked below level 2 once off, "Circuits need a verified work email (level 2)". Under 18, Everyone and Message requests are locked, and each says why.
  - **Notifications:** one grid, a row per type (Intros, Messages, Applications, Circuits, Replies, Announcements, each with a line of what it covers) and a switch per channel (App, Email). Screen readers hear "Intros by email". The note covers account notices, the 3-a-day push cap and quiet hours.
  - **Appearance** (Appearance.dc.html): Theme segmented control, "Your colour" with "Marks what's live and new. Buttons stay neutral.", the F1 `AccentPicker` (six accents, arrow keys, live preview) and "Swipe between tabs" as a `Toggle`. Every change applies at once and is saved on the member through `useAppearance`, so it follows you to every device.
  - **Blocked people:** each with `Unblock`; empty is "You haven't blocked anyone."
  - **Export my data:** `Ask for my data`, then "We're preparing your file…", then "Your file is ready. Open the link we emailed you… It works until 1 November." The email link `/settings/export?token=` downloads, or says the link expired (410) or belongs to another account (404).
  - **Delete account:** what happens (profile gone, posts and messages stay as "Deleted member", signed out everywhere), a link to export first, "Type DELETE to confirm", `Delete my account`, then a confirm sheet; after that you're signed out.
  - **Help:** six FAQs (the answer fades in and rises 8px, DESIGN.md §7), Contact support (kind, message, Send, then "Sent. Your reference is CIR-2026-0042."), Grievance Officer (from the settings call) and Policies.
  - **Legal pages** (`/settings/legal/privacy|terms|guidelines`): the same holding text as the landing site ("We're finishing this document with our lawyer…") plus the policy version you accepted, and a link to the landing page once `NEXT_PUBLIC_LANDING_URL` is set. Unknown names show the 404.
  - **Sign out.**
- **New in `packages/ui`** (new files only; no existing component changed): `Toggle` (role switch, 51×31), `ReplyThread` (+ `ReplyView`), and `PostComposer.tsx` with `MediaSlot`, `AddMedia`, `CharCounter` and `CropFrame` (+ `MediaAspect`). These are the PostComposer and ReplyThread from DESIGN.md §6. All are on `/design`.
- **Data layer:**
  - `data/profile.ts` (`useMyProfile` with `strength`, `useProfile` with connect/report/block, `useMemberPosts`, `useProfileDraft`, `useSaveProfile`).
  - `data/posts.ts` (`usePost`, `usePostReact`, which updates the post and Pulse caches, `useReplies` with send/remove/report, `useDeletePost`).
  - `data/compose.ts` (`useComposer`: photos, crop, upload with XHR progress since fetch can't report it, retry, text, tags, link, visibility, `blocker`, publish).
  - `data/settings.ts` (`useSettings` with ready row values, `usePrivacy`, `useNotificationPrefs`, `useBlocks`, `useExport`, `useExportDownload`, `useDeleteAccount`, `useSupport`, `useSignOut`).
  - `lib/image.ts` (crop rectangle, shrink to 1440px, JPEG). The upload is in `data/` because it uses the network.
  - `links.ts`: `memberHref`, `postHref`, `settingsHref`, `composeHref = "/compose"`; post notifications go to `/posts/<id>`.
- **Mock mode:**
  - `data/mocks/profile.ts`: your lists, people 2–11, connect.
  - `data/mocks/posts.ts`: posts 101, 201, 202, 301, replies, create/delete.
  - `data/mocks/settings.ts`: settings, privacy, notifications, blocks, export, delete, support.
  - Uploads are shared with chat (`mocks/inbox.ts`): each PUT takes about half a second so progress shows.
  - New scenarios: **Profile to fill in**, **Uploads fail once**, **Data export ready**, **Profile, posts and Settings loading / fail to load** (only those calls hang or fail, so each screen's own states show inside a working app, as F4/F5 did).
  - `GET /api/members/<id>` moved from `mocks/inbox.ts` to `mocks/profile.ts`.
- **Tests:**
  - `tests/profile.spec.ts`, `tests/compose.spec.ts` and `tests/settings.spec.ts`, each at 375px and 1280px.
  - What they cover: everything above, plus every scenario (empty, loading, error, slow 3G, under-18, features off, Pulse off, uploads failing) and axe in dark and light on every new screen.
  - A touch test closes the last TabPager item (LAUNCH.md): a sideways swipe on a post's pictures stays with the pictures.
  - `premium.spec.ts` already measured `/profile`; it now measures the real screen.
  - Updated because links now go somewhere real: `discover.spec.ts` (People tiles open the profile; the intro is one tap away there), `home.spec.ts` (the intro from Discover goes through the profile), `notifications.spec.ts` (a reply to your build log opens `/posts/201`).
- **Test results.**
  - Type check, ESLint, the boundary rule (20 passed) and the UI package's type check and lint are all clean.
  - New specs: `profile.spec.ts` 50, `compose.spec.ts` 46 (1 skipped on desktop: the touch test), `settings.spec.ts` 62. All pass.
  - Whole mock suite, one full run: **562 passed, 10 failed, 36 skipped**.
    - Eight failures were the four tests above, which still expected the old links (both widths). One was a 39px gap on the profile (premium rule needs 40). All are fixed.
    - The tenth was a `/design` sheet-detent test that passed on the re-run.
  - Re-run of every touched spec file (discover, home, notifications, premium, tabpager, profile, compose, settings): **365 passed, 2 failed, 35 skipped**. The two failures were Home's Update view arrow keys and the pager's scroll position (F4 already noted that one as flaky). Neither is F6 code, and both passed 3 out of 3 when run alone.
  - `foundation.spec.ts` after adding the F6 components to `/design`: 44 passed.
  - `make check` (backend) was not run: this session touched no backend code.
  - As in F4 and F5, Playwright ran with the pre-installed Chromium through a local, uncommitted config.

### Frontend → API needed (F6)
Served from clearly marked mocks (`data/missing.ts`, `PROFILE_EXTRAS` / `ME_EXTRAS`); never an invented endpoint in a real build.
1. **Profile fields on `ProfileOut`.** These are needed by the Person screen:
   - `headline`, `organisation_name` and `photo`
   - `is_minor` together with `hidden_from_me` (under-18 and not connected), so the app shows "This profile is private." instead of a full profile
   - `connection: none | pending | connected`, so the button shows Request sent / Connected
   - `mutual_count`
   - `can_message` (false for under-18s and people with requests off, when you're not connected)

   A real build today shows a full profile with Connect and Message and lets the server refuse.
2. **Highlights.** No model or endpoint. Needs `GET /api/members/{id}/highlights` and the same for me → `[{id, title, image: {w480, w1440, alt}, link}]` (max 6), plus a way to pin them (`PUT /api/me/highlights`). Profile and Person. Mock mode only.
3. **Someone's circuits.** `GET /api/circuits` is mine only. The Person screen's Circuits tab needs "circuits we closed together" → `GET /api/members/{id}/circuits` → `[{id, month, completed}]`. In a real build the tab is left out on other people's profiles.
4. **`headline` and `organisation_name` on `MeOut`, and `headline` on `MePatch`.** Own profile line and Edit profile. Today the line is role · city, and the headline step is left out of the strength meter.
5. **Paging on `GET /api/members/{id}/posts`** (`cursor`, `limit`). The grid loads everything today.
6. **Typed `GET /api/me/export`.** It answers an untyped object in openapi.json; the app casts it to `ExportStatus`.
7. **Avatar upload** (repeats the global item): `POST /api/media/uploads` needs a `purpose: avatar`, then Edit profile gets a photo row.
8. **Read receipts setting** (F5 #4): not shown in Privacy until the member has a `read_receipts` field.
9. **Alt-text suggestion** (DESIGN.md §10 "the composer suggests it"). Nothing suggests one; the author always types it. Could come back from `/complete` (`suggested_alt`).
10. **Link card metadata** (title, image) for a build log's link. The card shows the host name only.
11. **Notification channel `push`, quiet hours and the daily cap** (DESIGN.md §8). `NotificationPrefsOut` has in-app and email only; the screen says the push rules in a note.

### Shared UI changes needed (F6)
1. **`GroupedList` double-indents rows after the first.** Each `li` after the first gets `ml-4` (for the hairline) and `ListRow` brings its own `px-4`, so the text sits 32px in instead of 16px (visible on every grouped list, F1's `/design` sample too). Worked around with `ROW_INSET` (`[li+li>&]:pl-0`) on each row in F6 screens (`components/sheets.tsx`). Fix in GroupedList (e.g. `[&>*]:pl-0` on inset rows), then remove `ROW_INSET`.
2. **`Avatar` has no 72px or 88px size** (Profile.dc.html 72, Person.dc.html 88). The screens use 64 and 96.
3. **`AccentPicker` preview** has the Live wire node and dot but not the "View role" link and the "Bridge match" pill that Appearance.dc.html shows, and its swatches are a 3×2 grid of 64px where the reference uses one row of six 44px swatches. Used as is.
4. **`PostCard` hides reactions on your own post** (right), but the post view also needs the author's private totals under it; drawn by the screen below the card.
5. **`PushScreen` has no `h1` unless `largeTitle`**: the post view adds a screen-reader-only "Build log by …" heading for axe.

### Decisions and things to know (F6)
1. **Resize target is 1440px** (DESIGN.md §11 and PRODUCTION.md §14), not the 2000px PROGRESS B6 mentions, because the server keeps 1440 and 480 anyway. Output is JPEG at quality 0.86, which also drops EXIF/GPS and turns a HEIC the browser can read into JPEG. A HEIC the browser can't read says "Couldn't read that photo. Try a JPEG or PNG."
2. **One frame per build log.** All photos in a post share 4:5 or square (set from the first photo, changeable), because the media pager draws one shape. Changing the frame or a crop uploads that photo again.
3. **Photos upload when added** (not on Post), so progress and Retry happen while you write. Post waits until every photo is up and described.
4. **Descriptions are required** before Post (the API refuses media without `alt_text`). The tile says "Add description" until there is one.
5. **The strength meter** counts bio (20+ characters), offers, needs, a skill with a proof link, and a first build log (only with `pulse` on). It uses neutral colours (it isn't a score to chase, §8) and hides at 100%.
6. **A hidden under-18 profile doesn't say why** it's private, so strangers don't learn the person's age.
7. **Block from a profile goes Home** with "Blocked Asha." (the profile can't be shown any more).
8. **Legal pages** show the same holding text as the landing site until the lawyer-approved text is published (`docs/legal` are drafts).
9. **Sign out** clears the session and the cache; the sign-in screen follows. **Delete** signs out after the 202.
10. **Settings rows navigate inside the app** (not plain links), so the cache and the mock's in-memory changes survive moving between screens.

## F5 — Circuits and Inbox (branch `frontend-f5`, from `main` after F4): done, waiting for your OK
Frontend only, mock mode only (no backend, keys or login). Screenshots per screen in `screenshots/f5/<screen>/` (375px dark and light, 1280px, and `side-375-dark.png` with the reference on the left where one exists); `node screenshots/f5/shots.mjs` makes them again.

**What it is, in plain language.** **Circuits** is where you answer this week's exchange circuit: three people on a ring, each helping the next. Each person's piece of the ring lights up when they say yes, live, without reloading. When the third yes comes in, the ring closes with the one signature animation (the three pieces draw one after another, a bright stretch of the gradient runs once around, the faces pulse once: 1.6 seconds, once per circuit). After that you mark your part done and rate what you received; finished circuits become a row of small rings. **Inbox** has two folders: Chats (people you know) and Requests (first messages from people you don't, which wait until you accept); under-18 members have no Requests at all. A **conversation** shows your messages in emerald on the right and theirs on the left; sending shows your message at once and offers Retry if it didn't go; you can send a picture; Report and Block sit in the "…" menu, each behind a sheet that asks first.

- **Circuits** (`components/circuits/Circuits.tsx`, Circuits.dc.html): Large title; one card per proposed or active circuit (title, time left in Geist Mono, the ring, "You help Priya with **fundraising**" and the other two lines with "· accepted" / "· done"), then by what the API says to do next: `Accept` (primary, only on the first card that needs an answer, so one primary per screen) and `Decline` (text button → "Decline this circuit?" sheet), "You said yes. Waiting for Arjun.", "Circuit closed. You help Priya with fundraising. We'll check in next week.", `Mark my part done` (→ "Done helping Divya?" sheet), and five stars for "How was Rohan's help with pitch deck?". A completed circuit stays a card until you've rated, then joins **Completed** (small rings, "2 circuits closed"). Empty: the open ring and "Add what you need and what you can offer to join this week's round."; under-18: "Exchange circuits are for members 18 and over." (the backend never puts minors in a round).
- **CircuitRing** (new in `packages/ui`, DESIGN.md §6): the 240×210 ring from the reference, avatars on the three nodes, lit pieces in the signature gradient (`current → bridge`, so it follows the member's accent and the Indigo swap), unlit in `surface-3`. `closing` plays the §7 moment; with reduced motion it is a static closed ring with a checkmark that fades in over 150ms. `MiniRing` for the history. It plays only when the hook *sees* a ring close (a live answer, or your own Accept) and remembers on the device that it played, so it never replays on reload.
- **Inbox** (`components/inbox/Inbox.tsx`, Inbox.dc.html): Large title, `Chats · Requests` segmented control (hidden for under-18s), rows with the circuit-pattern avatar, name (semibold when unread), time ("3:33 pm", "Yesterday", "Fri", "12 Oct", IST), the last message ("You: …" for yours, "Photo" for a picture) and the unread dot (decoration; screen readers hear "Unread"). The Inbox tab (and the desktop rail) gets a dot when anything is unread. `New message` (pencil in the bar on a phone, a row above the list on desktop) lists your connections: one you already talk to opens that chat, anyone else opens a draft (`/inbox/new?to=<id>`, also where a Live wire `Reply` now goes) whose first send starts the conversation.
- **Conversation** (`/inbox/[id]`, `components/inbox/Conversation.tsx`, Chat.dc.html): back to Inbox, the name, "…" → `Report Meera` (sheet with four reasons, `Send report`) and `Block Meera` (sheet: "This conversation closes, and you won't see each other's messages, posts or intro requests any more."). The person (avatar, name, "Mentor · Chennai") sits just above the first message; a short thread sits at the bottom near the composer. Day labels, bubbles (own `primary`, theirs `surface-2`, 18px corners, 75% wide), pictures with alt text. Composer: picture button (JPEG/PNG/WebP up to 5 MB, checked before anything is sent), "Message", round Send. Sending is optimistic: the bubble shows at once, "Sending", then either settles or says "Not sent. Retry". A request someone sent you shows "Rohan isn't one of your connections. Accept to reply." with `Accept` (and `Decline` in mock mode only, see API needed) and no composer until you accept; your own request says you're waiting. Read receipts: none are shown (the API never tells senders; DESIGN.md says off by default). Opening a conversation marks it read and clears the row's dot.
- **Realtime** lives only in the data hooks: `data/realtime.ts` (`useChannel` / `useChannels`, private Broadcast as the backend sends it). `useCircuits` listens on `circuit:<id>` (`status`) and refetches; `useInbox` on `conversation:<id>` for every listed conversation (plus the minute poll for new ones); `useConversation` on `conversation:<id>` (`message`), fetches the one message, adds it and marks it read. In mock mode the same hooks listen to an in-memory bus (`data/mocks/bus.ts`) that the mock handlers emit on: Arjun says yes about 4 seconds after Circuits loads, Farhan writes about 5 seconds after Inbox loads, and the other person answers about 2 seconds after you send in a chat. **Not tried against real Supabase** (no keys here).
- **Data layer:** `data/circuits.ts` (`useCircuits`, `useRespondCircuit`, `useMarkDone`, `useRateHandover`, `toCircuitView`), `data/inbox.ts` (`useInbox`, `useInboxDot`, `useConnections`, `useFindConversation`, `useStartConversation`), `data/conversation.ts` (`useConversation`, `useDraftConversation`, image upload: signed URL → PUT → complete), `data/realtime.ts`. `features.ts` now counts `circuits` as built, so the tab shows when the flag is on; `/circuits` with the flag off is the 404 screen. `links.ts`: circuit notifications → `/circuits`, message notifications → `/inbox/<id>`, Live wire Reply → `/inbox/new?to=<id>`.
- **Mock mode:** `data/mocks/circuits.ts` (this week's proposal with Priya and Arjun, last week's active circuit with Divya and Rohan, two completed) and `data/mocks/inbox.ts` (five chats, two requests, uploads that really show the picture, connections, `GET /api/members/<id>` for the draft). New scenarios: **Circuits and Inbox loading**, **Circuits and Inbox fail to load** (only those calls hang or fail, so the screens' own states show inside a working app, as F4 did for Discover) and **Messages fail to send** (the first try of each message fails, Retry works). The mock notification "sent you a message" now points at a mock chat (Farhan, 502).
- **Tests:** `tests/circuits.spec.ts` (18 tests) and `tests/inbox.spec.ts` (19 tests), each at 375px and 1280px: the card and its lines, the live segment (no reload), Accept → closed with the checkmark (reduced motion), Accept first then closing live, Decline sheet, one primary button, the closing moment with motion on (runs once, ends in about 1.6s, no replay after reload), mark done, rating, history; Chats/Requests, unread weight and dots, the tab dot, a live message, New message (existing chat and draft), opening marks read, bubble colours, no read receipts, optimistic send and live reply, Retry, image share, a refused file type, Accept a request, Decline, Report, Block, a 404 for someone else's conversation; every scenario (empty, loading, error, slow 3G, under-18, features off) and axe in dark and light on every new screen and sheet. `premium.spec.ts` now also checks Circuits. Updated because Circuits is now a real tab and links go somewhere real: `notifications.spec.ts` (circuit → `/circuits`, message → `/inbox/502`), `home.spec.ts` (Live wire Reply → the draft to Arjun; the desktop rail now has five rows), `foundation.spec.ts` (the 404 deep link to `/circuits` now uses the Features off scenario) and the header comment in `tabpager.spec.ts`.
- **Test results.** Type check, the boundary rule and ESLint are clean. The whole mock Playwright suite (both projects): **416 passed, 0 failed** (411 in one full run, then the 5 it caught fixed and their four spec files run again: 160 passed). Fixed along the way: the premium check flagged the Inbox's unread dot as accent inside a link (it is now decoration, with "Unread" for screen readers) and a 39px gap above Completed. `tabpager.spec.ts` passed this time (F4 noted one flaky scroll test there). `make check` (backend) was not run: this session touched no backend code. As in F4, Playwright ran with the pre-installed Chromium through a local, uncommitted config.

### Frontend → API needed (F5)
Served from clearly marked mocks; never an invented endpoint in a real build.
1. **Decline a message request.** There is accept and block, but no "no thanks". Needs `POST /api/conversations/{id}/decline` → 204 (the request disappears for the person who declined; the sender isn't told). Inbox conversation screen. Mock mode shows `Decline`; a real build only offers Accept and (in the menu) Block. — **done in B7**: `POST /api/conversations/{id}/decline` → 204 (a `declined_by` marker; the sender is not told and cannot pile on).
2. **New conversations live.** The backend only broadcasts on `conversation:<id>`, so the Inbox can't hear about a conversation it hasn't listed yet (a new request) until its minute poll. Needs an event on the member's channel: `member:<id>`, event `conversation`, payload `{conversation_id}`. Inbox. — **done in B7**: `member:<id>` event `conversation` `{conversation_id}` for a new request, every new message and an accepted request, so the Inbox needs one subscription.
3. **Unread count for the tab dot.** The dot is worked out from the two folder lists (100 newest each). A `GET /api/conversations/unread-count` → `{chats: int, requests: int}` (or the same on `GET /api/me`) would be exact and cheaper. Tab bar and desktop rail (this also closes F3's "Unread conversations"). — **done in B7**: `GET /api/conversations/unread-count`.
4. **Read receipts (optional, off by default).** None are shown today. If members can turn them on: a `read_receipts` setting on the member (Settings, F6) and `read_at` on `MessageOut` for my own messages when both people have it on. Conversation. — **done in B7**: `read_receipts` setting (default off) on privacy/settings; `read_at` on my own messages only when both people have it on.
5. **Photos.** `AuthorOut` / `PersonOut` have no photo URL, so every avatar in Inbox, the conversation and the ring is the circuit pattern. Needs `photo` (signed URL or null). Inbox, conversation, Circuits. — **done in B7**: `photo` on `PersonOut`/`AuthorOut`, `logo` on startups and pins.
6. **Circuits empty state's action.** "Add what you need and what you can offer…" has no button because Profile editing is F6 and `GET /api/me` doesn't say whether I opted in to circuits (`circuits_opt_in`) or why I'm not in this week's round. With `circuits_opt_in` (and ideally `has_needs_and_offers`) on `MeOut`, the empty state can say the right thing and link to the right place. — **done in B7**: `circuits_opt_in` was already on `MeOut`; added `has_needs_and_offers`.
7. **Message images:** the app only reads `image.w480` (then `w1440`), `width` and `height` from the untyped `image` object on `MessageOut`; please type it as a schema so the client is generated, not guessed. — **done in B7**: typed `MessageImageOut {width, height, w1440, w480}`.

### Shared UI changes needed (F5)
1. **`PushScreen` title slot.** Chat.dc.html puts the avatar, name and "Mentor · Chennai" left-aligned in the bar; `PushScreen` only takes a centred text title. Worked around: name centred in the bar, the person shown above the first message. A `titleSlot` (or `titleNode`) prop would match the reference.
2. **`Avatar` has no 48px size** (Inbox.dc.html rows use 48). The rows use 44 until `AvatarSize` gets 48.
3. **`Screen` hides its top bar on desktop**, so a bar action (Inbox's `New message`) needs its own desktop placement. Worked around with a row above the list on desktop; a `desktopActions` slot on `Screen` would make this one pattern for every tab.

### Decisions and things to know (F5)
1. **Message previews are clamped to two lines** in the Inbox. This is the one place a cut is normal (every messaging app does it); the premium check would flag a long preview. The mock previews are short, so the check passes on mock data; tell me if you want a different rule.
2. **Section header "Completed" is Title 3** (DESIGN.md §5), not 17px semibold as in Circuits.dc.html.
3. **The circuit card's title reads "Circuit closed" once all three said yes** (as the reference's closed state), also for last week's circuit while its handovers are being done; "Circuit complete" once everyone has marked done and you still have to rate.
4. **Decline sheet copy** says "One no ends it for all three of you, and they're told it won't go ahead." (the backend ends it for everyone; please confirm the other two get a notice).
5. **Report reasons** are four fixed lines ("Spam or a scam", "Harassment or hate", "Pretending to be someone else", "Something else") sent as the report's `reason` text.
6. **Live wire Reply** now opens a message to that person (the draft opens the existing chat if there is one), instead of the Inbox.

## F4 — Discover (branch `frontend-f4`, from `main`): done, waiting for your OK
Frontend only, mock mode only (no backend, keys or login). Screenshots per screen in `screenshots/f4/<screen>/` (375px dark and light, 1280px, and `side-375-dark.png` with the reference on the left where one exists); `node screenshots/f4/shots.mjs` makes them again.

**What it is, in plain language.** Discover is where you look for people, startups and roles near you. One search field at the top looks through all of them. Under it, four segments: **People** and **Startups** are two-column picture grids, **Jobs** starts with one sentence about the skills most asked for within 10 km and then lists the roles that fit your skills best, and **Map** is a full-screen map of startups. Filters open in a bottom sheet and only offer what that segment can use. Tapping a role opens its **job page**, where one tap applies with your profile. Tapping a startup opens its **Startup page**. Founders get a ranked list of their applicants.

- **Discover** (`components/discover/Discover.tsx`): Large title, search, `People · Startups · Jobs · Map` as a full-width segmented control (Discover.dc.html). Students start on Jobs (a role nearby is what they came for), everyone else on People; `/discover?s=jobs` picks a segment and the choice is kept for the session. Matches are in words ("Strong match", "Bridge match", "Strong skill match"), never percentages. The one promoted slot sits at the top of Startups and Jobs (flag `promotions`, mock stand-ins only, "Why am I seeing this?" and "Hide this"). People tiles open the intro sheet (profiles are F6); under-18 members get no intro from a tile.
- **Job page** (`/discover/jobs/[id]`, Job.dc.html): startup line (links to the Startup page), the role as a Large title, Stipend / Type / Where, "You match 3 of 4 skills" (the ones you lack are dashed), About the role, and a sticky `Apply with your profile` that turns into "Applied · We'll tell you when Aravind Pathology replies." The startup's own team sees `See applicants` instead; a closed role says so.
- **Your applications** (`/discover/applications`): newest first, status in plain words (Sent, Shortlisted, Not selected, Hired). Reached from a row on Jobs (only when you have applied somewhere) and from application notifications (the link map now points here).
- **Founder applicant view** (`/discover/jobs/[id]/applicants`): founders of that startup only (anyone else gets the 404 screen). Ranked by skill match, best first, with skills and their level, proof-of-work links, and `Shortlist · Not now · Hired` (changes at once, put back if the call fails). Nothing about colleges.
- **Map** (`MapView.tsx`, Map.dc.html): MapLibre with OpenStreetMap tiles, loaded only when the segment is first opened. Pins are real buttons ("Aravind Pathology, hiring"): hiring = `current`, not hiring = a muted dot, the selected one grows. A tap only selects and opens the sheet (name, sector, distance, "Hiring · Frontend intern · Strong skill match"); `See open roles` opens the job page when there is one role, otherwise the Startup page at Hiring; not hiring shows `Follow`. The map owns every gesture (tab swipe is locked). The map is hidden, not destroyed, while a pushed screen shows, and its place, zoom and pin are kept for the session, so Back lands on the same pin and zoom. If the device has no WebGL the same startups show as a list. In the dark theme the tiles are dimmed and greyed so pins stay the loud thing. Hiring chip and "Within 10 km" sit over the map, the rest in Filters.
- **Startup page** (`/startups/[id]`, no reference file, built in the Job page's style): square mark, name as a Large title, sector · stage · team size, place · distance, "Claimed by its team" or "Unclaimed · from public sources"; one primary `Follow` / `Following`; **Hiring first** (`#hiring` scrolls there) or "Not hiring right now" with `Follow for updates`; About with tech stack and website; build logs grid (only with `pulse` on); founders with `Intro via Lakshmi` when a warm path exists ("Connected" when you already are; nothing for under-18s); "…" → Report. The team sees its own views and interest privately; founders on an unclaimed page see "23 students looked at this page and 6 are interested" and `Claim this startup` (work email on the startup's domain → 6-digit code → claimed).
- **Under-18:** roles and promotions only from verified startups (verified = claimed through its company email), everywhere: the Jobs list, search, job pages (404 otherwise), the map sheet and the Startup page (an unverified startup shows as not hiring). No intros from People tiles or to founders.
- **Data layer:** `data/discover.ts` (`useDiscoverPeople`, `useDiscoverStartups`, `useDiscoverJobs`, `useSkillsInDemand`, `useDiscoverSearch`, `usePromotion`), `data/jobs.ts` (`useJob`, `useApply`, `useMyApplications`, `useApplicants`, `useSetApplicantStatus`, `useStartupJobs`), `data/startups.ts` (`useStartup`, `useFollows`, `useFollow`, `useStartClaim`, `useVerifyClaim`, `useMapPins`); `links.ts` now has real role, startup, applicants and applications paths (Live wire "View role" and notifications use them).
- **Mock mode:** `data/mocks/discover.ts` (seven Chennai startups, five roles, applicants, follows, claim). New scenarios: **Founder** (signed in as Priya, on Aravind Pathology's team), **Discover loading** and **Discover fails to load** (only Discover's calls hang or fail, so the screen's own loading and error states show inside a working app; the existing Loading and Error scenarios stop the whole app at the gate).
- **packages/ui:** `SegmentedControl` gained `stretch` (equal segments across the width); `PushScreen` gained `bleed` (rows run edge to edge on a phone). Nothing else changed shape.
- **Tests:** `tests/discover.spec.ts`, 45 tests at 375px and 1280px (89 runs; the touch test is phone only): segments, keyboard, filters, search, promoted slot, every scenario (features off, under-18, empty, Discover loading, Discover error), apply → Your applications, founder applicants and the 404 for anyone else, the map (pin sheet, one role → job, two roles → Startup page at Hiring, Follow, Back to the same pin and zoom, Hiring chip, a sideways touch drag pans the map and never changes tab), the Startup page (order of sections, Follow, intro via a mutual, private counts, claim flow, Report), and axe in dark and light on all 11 new screens and states. `premium.spec.ts` now also checks Discover's People and Startups segments (Jobs was already the default).

- **Test results.** Type check, the boundary rule and ESLint are clean. The whole mock Playwright suite: 339 passed, 1 failed. The failure is `tabpager.spec.ts` "each tab keeps its scroll position across swipes" on `/design/pager`, which **also fails on `main` without my changes** (3 of 6 runs), so it is an existing flaky test, not left by F4; I didn't change it. Three F3 tests were updated because their links now go somewhere real: Live wire "View role" opens the job page, the application notification opens Your applications, the startup notification opens the Startup page; the "Intro me in Discover" test now uses the People grid. `make check` (backend) was not run: this session touched no backend code. Playwright here ran with the pre-installed Chromium (`/opt/pw-browsers/chromium`) through a local, uncommitted config, because the repo's Playwright version wants a browser build this container doesn't have.

### Frontend → API needed (F4)
Served from clearly marked mocks (`data/missing.ts`, `data/mocks/discover.ts`); never an invented endpoint in a real build.
1. **Search.** No search endpoint: the field searches what the People, Startups and Jobs lists already loaded (first 40 matches, 40 nearby startups, 50 roles). Needs `GET /api/search?q=` → `{people: MatchOut-like[], startups: PinOut[], jobs: JobOut[]}`. — **done in B7**: `GET /api/search?q=` → `{people, startups, jobs}` (10 each; hidden, under-18, blocked and deleted people never appear; under-18 searchers find only connections).
2. **People filters.** `MatchOut` has no distance, capabilities, headline or photo, so People can only be filtered by role and "verified" (on what came back). Needs `capability`, `max_distance_km`, `role`, `verified` on `GET /api/matches` (or `distance_km`, `capabilities`, `headline` on `MatchOut`). — **done in B7**: `role`, `verified`, `capability`, `within_km` (5/10/25/50) on `GET /api/matches`; `MatchOut` gained `headline`, `capabilities`, `photo`. Safe version: no distance is ever returned, only the coarse filter.
3. **Is a role's startup verified?** Needed for the under-18 rule. `JobOut` doesn't say, so the app treats a role without `startup_verified: bool` as unverified: **in a real build under-18 members see no roles until this field ships.** Better still, filter server-side for minors on `/api/jobs`, `/api/jobs/{id}`, `/api/startups/map` and `/nearby` (the backend has no `is_minor` check in `apps/jobs` today). — **done in B7**: `startup_verified` on `JobOut`, and the server filters for under-18s everywhere (jobs, job page 404, apply 404, map, nearby, search, skills in demand, Pulse, Live wire).
4. **Startup page extras.** `StartupOut` has no team size, founders or build logs. Needs `team_size`, `founders: [{id, display_name, role, verification_level}]` and `GET /api/startups/{id}/posts` (or the first images on `StartupOut`). Mock mode fills them from `STARTUP_EXTRAS`; a real build leaves those parts out. Also a `logo` URL (we draw the circuit pattern until then). — **done in B7**: `team_size`, `founders` (with the warm path built in, so no call per founder), `build_logs` (first pictures, replaces a posts endpoint), `logo`.
5. **Promoted items for Discover.** The Startups and Jobs slots need `GET /api/promotions?slot=discover_startups|jobs` (one item, with its "why" sentence and the startup's verified state) and a "hide this promotion" call. Same gap as the Pulse slot in F3. — **not built, on purpose**: needs the promotions tables (Stage 4d). See the Home entry above.
6. **Skills in demand** is worked out in the app from the first 100 roles within 10 km. A small `GET /api/jobs/skills-in-demand` would make it exact. — **done in B7**: `GET /api/jobs/skills-in-demand?within_km=`.
7. **Job page:** Job.dc.html shows Duration and Starts; `JobOut` has neither. And the founder's first name for "We'll tell you when Divya replies" (the app says the startup's name). — **done in B7**: `duration_weeks`, `starts_on`, `contact` (the founder who claimed the startup), `is_team`, `startup_verified`, `startup_logo`.
8. **Founder's own startup.** `GET /api/me` doesn't say which startup a founder is on, so founders reach their applicants through their startup's role page. A `startup_id` on `/api/me` would let Profile (F6) link straight there. — **done in B7**: `startup_id` on `MeOut`.
9. **Views.** The map sheet never calls `GET /api/startups/{id}` (it uses `/api/jobs?startup_id=`), so a pin tap doesn't count as a page view. Please confirm that endpoint counts a view only once per member per day. — **done in B7**: confirmed and tested: one view per member per day on `GET /api/startups/{id}`; the map sheet (`GET /api/jobs?startup_id=`) counts none. Also fixed a real leak: `view_count` and `interest_count` used to go to every viewer; they are now null unless you are on the team (or a founder on an unclaimed page, and then not under 5).
10. **Applicant skills:** `ApplicantSkill.capability` is read as a slug and named from `/api/capabilities`; say if it is already a name. — **done in B7**: `ApplicantSkill.capability` is the slug; `name` is new.

### Decisions and things to know (F4)
1. **The map sheet says `See open roles` / `Follow`**, as DESIGN.md §4 and this brief say, not "I'm interested" (Map.dc.html and CLAUDE.md F2). The interest endpoints are not used yet; tell me if you want "I'm interested" back somewhere.
2. **Students land on Jobs, everyone else on People.** Decided (your OK): written into DESIGN.md §4 "Discover".
3. **Discover's section headings are 17px semibold** as in Discover.dc.html and People.dc.html; the pushed pages use Title 3. Decided (your OK): written into DESIGN.md §4 "Discover" as the one exception to Title 3 headers.
4. **Verified startup = claimed** (claiming needs the company email domain, CLAUDE.md F3). There is no separate startup verification level in the API.
5. **Map tiles:** `NEXT_PUBLIC_MAP_TILES_URL` (default: the OpenStreetMap tile server, as CLAUDE.md names it). It is read in `lib/env.ts`; please add it to `.env.example` (I don't edit env files). OpenStreetMap's own tile servers are for light use only: before public launch pick a tile provider (or self-host) and set this variable. Attribution "© OpenStreetMap contributors" is on the map.
6. **MapLibre 6 needs its worker file**; the app points MapLibre at it with `new URL("maplibre-gl/dist/maplibre-gl-worker.mjs", import.meta.url)`, which the bundler copies. Works in the dev server (all the map tests); `next build` emits the worker and references it, but I have not opened a production build in a browser.
7. **No network here**, so tiles never loaded in my runs: screenshots show the map's plain background with the pins. The tests block tile requests on purpose.
8. **Noticed, not changed:** Notifications passes `className="px-0"` to `PushScreen`, which doesn't remove the 16px side padding (the class order makes `px-4` win), so its rows sit 32px in on a phone. `bleed` fixes it if you want me to switch it over.

## F3 — Home (branch `frontend-f3`, from `frontend-F2`): done, waiting for your OK
Merge F2 before F3: this branch contains F2's commits. Five parts, each with screenshots next to the reference in `screenshots/f3/<part>/` (`side-*.png`: reference left, app right; the references are rendered by `screenshots/f3/ref-render.mjs`, a small stand-in for the `support.js` the reference files expect).
- **Part 1, Home on mobile.** Live wire (52px nodes, verb-only labels, inner outline, current dot once per session), Daily Drop (header "Your drop · 1 of 3", reason in 22/500, Intro me and Skip inside the card, swipe 1:1 with the 30% / 800px/s throw), Pulse (visible header, text reactions, build logs without boxes, "You're caught up."), `+` and the bell with its dot. Flags: Pulse off = only the drop (and no "Worth meeting", which is removed from Home), Daily Drop off = wire and Pulse, both off = calm empty state. Under-18: no drop, no Intro me. Partner and promoted slots only when their flag is on (never first; promoted 1 per 8, partner 1 per 10; promoted has "Why am I seeing this?" and "Hide this"); their items are mock-only stand-ins (see "API needed").
- **Part 2, Update view.** Picture 66% of the height, Close and "1 of N" over it, tap zones on the picture edges, who and when, what, why, one action; swipe sideways or down, arrow keys, Esc. Under-18 members get no intro action.
- **Part 3, Notifications.** `/notifications` pushed from the bell: grouped by IST day, unread dots, a tap marks read (optimistic, bell count drops) and opens the target through the one link map (`data/links.ts`). Realtime nudge hook `useNotificationNudges` (`member:<id>`, event `notification`) written but **not tested against real Supabase** (no keys here); the bell also polls each minute. The shell used to draw a pushed screen below a full screen of hidden tab panes; fixed.
- **Part 4, Desktop Home.** Rail with the logo lockup, 48px rows (current filled), New build log (Pulse on only) and a Notifications row; 600px column, 340px Daily Drop rail 56px apart; no empty rail when the drop is off; the drop is the centre column when Pulse is off; in a post the words come before the picture on desktop.
- **Part 5, intro request flow.** Every Intro me (drop button and swipe, Update view, build-log reaction, Discover's People list) opens one confirm sheet: the path ("Lakshmi, mentor, will introduce you to Asha." or already connected), what happens next, Send request / Cancel. The card waits and flies off only once the request is sent. One-sentence results for weekly limit, person full, no shared connection, under-18. The sheet never says how many intros are left (the API doesn't).
- **Also fixed on the way:** reactions now show pressed at once (they only updated after a reload); `Sheet` kept its full height under reduced motion and ignored its detent; the Bridge badge and chips follow the reference (12px outlined, 15px).
- **Data layer:** `useHome`, `useSkip`, `useRequestIntro` / `useIntroPath` (`data/intros.ts`), `useNotifications` / `useMarkRead` / `useNotificationNudges`, `links.ts`, `useFeatures().raw()`. Mock scenarios added: Pulse off, Daily Drop off, Pulse and Daily Drop off, Intros used up.
- **Tests:** `tests/home.spec.ts` and `tests/notifications.spec.ts` (Home, Update view, desktop, flags, under-18, intro flow, swipes with real touch, axe at both widths in both themes and for all six accents). The Home axe run leaves out the translucent tab bar: the green Intro me button scrolling under it dips its labels below 4.5:1 in the light theme (DESIGN.md §5 Materials); the bar is still checked over plain content in `foundation.spec.ts`.
- **Where Home differs from the references, on purpose:** 16px (not 24 / 32px) between the title and the Live wire, because DESIGN.md §5 and the premium check allow 16; circuit-pattern art in wire nodes, system-notification avatars and the Update view (DESIGN.md §5 Imagery); a Notifications row in the desktop rail; pictures in a build log keep their own shape on desktop instead of 16:9; build-log pictures come first on a phone (DESIGN.md §4) and after the words on desktop (Desktop.dc.html), done in CSS, so a screen reader reads picture first.
- **For you to decide:** (1) DESIGN.md §3 says Home without Pulse shows the Daily Drop "followed by matches and nearby roles"; the F3 brief says only the Daily Drop, which is what is built: update §3 or tell me. (2) The desktop post order and screen-reader order above. (3) The Notifications "Mark all as read" the API supports but the reference leaves out.

## F2 — Sign-up and access (branch `frontend-F2`): done, waiting for your OK
Built and tested: `/join`, Welcome (matches the reference), email code, consent, invite code, waitlist, and the data layer for the rest (`useOnboarding`, `useCapabilities`, `useWhere`, `useOrganisationSearch`; not yet drawn). `tests/signup.spec.ts`: 9 tests at 375px and 1280px (18 runs), axe, no overflow, one primary button, ≤5 font sizes, dark and light. Screenshots: `screenshots/f2/`. Mock mode has two new scenarios, "New member" and "New member, AI down" (stateful mock of the API and of Supabase sign-in; code `000000` is refused, `CIRCUIT-0001` lets anyone in, `SVIT-2026` also joins the mock college).
- **Part 2 (done):** Name (prefilled from Google), Role (three rows; investor and partner rows appear with their flags), Age, the under-18 safety screen, Where (location rounded to ~1 km, or a chosen city). Tests: 13 more in `signup.spec.ts` (role link skips Role, under-18 path, location allowed and denied, resume after reload, Back, edge swipe, a failed save). Progress counts steps we already knew as done, so the bar reads the same after a reload. Screens after Where show a temporary "Almost there".
- **Part 3 (done):** Work (one large text field, Skip top-right; Enter makes a new line and Ctrl/⌘+Enter continues, the one exception to "Enter submits"), Offers and Needs (one shared `ChipPicker`), Organisation. With the AI's suggestions the chips start chosen, tap to remove or add back, and "+ Add" opens a search sheet; with no suggestions (Skip, AI down, nothing found) it is the whole capability list with a search field and no error shown. Limits 5 and 3, shown as "3 of 5"; at the limit "+ Add" or a new chip says "Up to 5. Remove one to add another." At least one pick is needed to go on ("Pick at least one.") because matching runs on offers and needs. Organisation (students only, skipped when the college email already joined one): a tap on a result saves the college and moves on; a college that isn't listed is used as typed ("Use “…”"). New in `packages/ui`: `TextArea`, `AddChip` (both in `/design`, with the large Chip). Tests: 12 more in `signup.spec.ts` (bio → chips, remove/add back, search sheet, the limits, at least one, Skip, AI down, the three Organisation paths, college email skip, founder skip, Back and reload). The "one primary button" check no longer counts chosen chips (they wear the brand fill but are choices). Screens after Organisation show the temporary "Almost there".
- **Part 4 (done):** Photo (step 12), Colour (13), Ready (14).
  - **Photo:** the circuit-pattern avatar is a button that opens the file picker; a chosen JPG, PNG or WebP previews in the circle, anything else gets one sentence ("That isn't a photo…", "…over 10 MB…"). Continue waits for a photo; Skip is top-right. Mock mode only, and the file is only noted (type and size), never sent: see "API needed". Bringing the photo back once later is the Profile screen's job.
  - **Colour:** the existing `AccentPicker` (six swatches, arrow keys, live preview). A tap recolours the whole app at once and saves in the background; Skip puts back the colour the person started with.
  - **Ready:** the logo mark, "You're on the circuit." and the first unanswered card from today's drop in a new compact `DropCardFace` (reason, "via …", person; no picture, chips or badge, as in Ready.dc.html). No drop yet (or it can't load) says "Your first drop arrives tomorrow at 8." and never blocks the button. "See today's drop" finishes sign-up and opens Home. `Step` gained a `lead` slot for the logo.
  - **Tests:** 12 more in `signup.spec.ts` (photo, colour with axe on all six accents, ready, ready with no drop, role link, under-18 start to finish, reload on Colour) plus the **timed sign-up: Welcome (Google) to the first drop card in about 3 seconds in mock mode, asserted under 120 s** (the time is attached to the test report). Test helper: font sizes now ignore the dev banner and SVG text, as `premium.spec.ts` does, and the failure message names the element behind each size.
  - **/design** now shows AccentPicker, TextArea, AddChip, the large Chip and both DropCardFace forms.
  - The temporary "Almost there" screen is gone.
  - **Replay onboarding** (banner, mock mode only): signs out, forgets the fake new member and restarts at Welcome. It used to link to an `/onboarding` page that never existed (404). Outside mock mode the link is hidden: a real server keeps a finished sign-up, and replaying would overwrite a persona's data.
- **Landing: set NEXT_PUBLIC_JOIN_LIVE=true after the app deploys.**
- Changed in F1's tests: "beta access missing" now expects the invite screen instead of the old placeholder.
- Google in mock mode returns straight to `/auth/callback` (the real call now uses `skipBrowserRedirect` and navigates itself; same URL in production).

## F1 — App foundation (branch `frontend-F1`, from the landing work): done, waiting for your OK
`make test-web` is green (type check, the architecture rule, 76 Playwright tests on mock mode at 375px and 1280px). `make check` is green too: ruff, mypy, 2,396 backend tests (Stories 1–5 PASS), 361 landing tests. Screenshots: `screenshots/f1/` (shell at 375 dark and light and at 1280, `/design` at both widths, 404, 500, the five-tab pager).

**What it is, in plain language.** Everything the screen sessions F2–F7 stand on: the theme and accent system, the shared components, the shell around the tabs, the data layer rules, a way to run the app with no backend, installable-app basics and a page that shows every component. Most of it already existed in rougher form; F1 corrected it to DESIGN.md and added what was missing. No backend files changed.

- **ThemeProvider** (`packages/ui/src/ThemeProvider.tsx`): theme (system / dark / light) and the six accents, applied from the member's saved appearance. The last known choice is cached on the device and an inline script puts it on `<html>` before first paint (a test blocks every app script and checks the colours are already there). An accent change crossfades all `current` colours over 250ms with two registered CSS properties (no per-element code); a theme change goes through a view transition; reduced motion makes both instant. The theme-color tag follows (black, or `#C2BCC8` in light). `tokens.css` colour sets now apply to any element with `data-theme`, so `/design` shows both themes side by side; the Logo's dark/light switch follows too. The landing site imports the same file (see decisions).
- **Components** (`packages/ui`), against DESIGN.md §5 and §6:
  - New: `ListRow` (56px, 64px with a subtitle), `GroupedList`, `ErrorState`, `Sheet` (detents medium and large, grabber, drag between detents or dismiss by distance or flick, page behind scales to 0.94 on phones; on desktop a centred dialog), `TopBar` and `LargeTitleHeader` (split out of `Screen`, which composes them as before), `CircuitsIcon`, `memberTabs()` and `partnerTabs()` presets for the bar, `useTabSwipeLock()`.
  - Corrected: `Card` has no border; `Button` variants are primary, secondary, text (was "ghost") and destructive; the selected segment is `surface-3` and arrow keys move the choice; the bar matches TabBar.dc.html (label colour, spacing, 24px icons); `TabPager` also stays still while a menu or a text field has focus, and a screen can lock it (the Map segment in F4); `Toast` has an error tone.
  - Replaced: `BottomSheet` → `Sheet`.
- **Shell** (`apps/app`): tabs come from the preset, so Circuits is not in the bar until its screens exist (four tabs, and swiping follows them); safe-area padding on the bars and the content; `404` (also what `/circuits` and any off or missing screen shows), `500` (route boundary and global boundary), `/design/crash` to see the 500. The **environment banner** shows in every environment where PRODUCTION.md §2 gives it a label (Dev, Demo — sample data, Staging, Beta while BETA_MODE is on in production, Mock — scenario) and sits above the gate, so it is on the sign-in, loading and error screens too. In dev and demo it also holds the **persona switcher** (switches without a sign-out), a theme switch and links to `/design`; never in staging or production.
- **Data layer** (`apps/app/src/data`): `useAppearance()` (replaces `useSaveAppearance` and `useApplyAppearance`; optimistic, rolls back on failure), `useFeatures()` and `useMe()` as before, one query client whose error mapping lives in `provider.tsx` (session ended → sign out; consent or beta needed → refetch who you are so the gate moves you; network → no retry), `useProblem()` for screens. `packages/api-client` regenerated (no change: the committed client already matched openapi.json). The ESLint rule is now in packages/ui too, and `apps/app/tests/boundary.test.mjs` proves it bites in screens, components and ui and lets `src/data` through.
- **Mock mode** (`make mock`, `pnpm --filter @circuit/app dev:mock`, only when `NEXT_PUBLIC_ENV=dev`): Mock Service Worker with handlers for every endpoint the hooks call (anything else answers 404 and logs a warning). Fixtures are **temporary** and typed `satisfies` the generated API types, so `tsc` fails when they drift from openapi.json. Marked "replace with B7 contract fixtures". Scenarios: default, empty, loading, error, slow 3G, beta access missing, features off, under 18 — switch in the banner or with `?scenario=`. Not in the normal build.
- **PWA basics:** `manifest.webmanifest` (name, standalone, black ground, 192/512 and maskable icons from docs/brand), favicon, apple-touch icon, theme colour, `noindex`. No service worker yet (F7).
- **`/design`** (dev only, 404 elsewhere): every component in its states in both themes at once, with an accent row that recolours both; `/design/pager` is the five-tab TabPager on its own.
- **Tests** (`make test-web`, part of `make check`; mock mode, no backend): `premium.spec.ts` (DESIGN.md §13 item 5, now **max 5 font sizes** as §13 says, on Home, Discover, Inbox, Profile, 404 and 500, both widths, both themes), `tabpager.spec.ts` (19 touch tests with real touch input: commit, snap-back, 35% rule, vertical scroll wins, sideways rows, segmented control, the Map lock, sheets, text fields, scroll position, tap-current-to-top, the toggle, reduced motion, the sheet detents), `foundation.spec.ts` (first paint, contrast for all six accents in both themes, the 250ms crossfade, 404/500, banner, every scenario, the manifest, `/design` with axe). `make e2e` (needs `make dev`) keeps the sign-in and shell journeys.

**Decisions and things to know**
1. **Circuits tab is hidden until F5** (your choice). The five-tab bar is shown in `/design` and `/design/pager`; the app itself has four.
2. **Accent names.** The API says `mint`; the UI says Emerald. See "Frontend → API needed".
3. **Axe found real contrast problems in the components, now fixed:** the destructive button in light (4.4:1), unselected segments in light (4.4:1), the Hiring, Bridge and Private badges in light (3.8–4.4:1; they now sit on `surface-3` / `surface-2`), and the new environment banner. Where the DESIGN.md token table puts `text-muted` on `surface-2` in the light theme, it is just under 4.5:1 for small text, so small text on `surface-2` uses `text` there. Worth a look when DESIGN.md next changes.
4. **tokens.css selectors are no longer tied to `<html>`** and `current`/`bridge` are registered colour properties. `make test-landing` is part of `make check` to prove the landing site is unaffected.
5. **The sheet's "page behind scales" only scales `<main>`** (marked `data-page-behind`), not the bars: `position: fixed` bars would jump if their parent had a transform. Phones only; reduced motion keeps the dim and skips the scale.
6. **msw 3.0.3** is the installed version (approved library). Its browser entry has no Node build, so `next.config.ts` aliases it to an empty stand-in for the server pass; the worker file is `public/mockServiceWorker.js` (ships in the build, inert unless mock mode registers it).
7. **Partner and investor mock scenarios** (named in LAUNCH.md) are not built: their screens are out of scope until Stages 4f/4g.
8. **Not done on purpose:** a real-phone test (DESIGN.md §13 item 4); service worker (F7); the `AccentPicker` (F6 with Settings); `PostComposer`, `ReplyThread`, `CircuitRing` (their screens).
9. **`make e2e` against `make dev`:** 22 of 24 pass; the two failures are `Home in the new shell`, which expects a Live wire and your dev database has no updates from the last 24 hours (the seed is days old). `make reset-demo` refreshes it; I did not wipe your data without asking.
10. **Unrelated, noticed:** the latest commit on this branch (`feat changes`) added `apps/landing/.out-after/` (a build output folder that `.gitignore` already lists). I left it alone.

## B0 — Feature flags and commands (branch `backend-b0`): done, waiting for your OK
`make check` is green: ruff, mypy, 1,716 backend tests (Stories 1–5 PASS), frontend type check.
- **Flags:** `core/flags.py` with the seven flags. `FEATURES` sets defaults per environment; a super admin overrides them in Django admin (Core → Feature flags, audit-logged, cached 60 s in Redis, Postgres if Redis is down). `flags.enabled(name, member)` for services, `@require_flag(name)` on each operation of a flagged router (Ninja has no router-wide hook), `flags.enabled(name)` in jobs. Off → 404 `feature_off`. The app refuses to start with a flag on whose dependency is off, with a Razorpay live key outside production, or with `payments` on in production without a live key.
- **Wrapped today:** `pulse` (posts, reactions, replies, Pulse, Live wire), `daily_drop` (drop + swipe, `build_daily_drops`), `circuits` (all circuit endpoints, `run_circuit_round`, closed-circuit items in Pulse/Live wire, `circuit.*` notifications). Switched-off notifications are hidden, not deleted. `expire_items` still expires in-flight circuits when `circuits` is off (the spec says in-flight work finishes).
- **New:** `GET /api/config` (public; a bad token counts as anonymous), `manage.py flags [list|set]`, `members.is_tester`, `feature_flags` table, `manage.py admin_user` (for `make admin-user`).
- **Retired:** the Today strip (`/api/today`, `/api/today/seen`, `today.py`, `StoryView` table, `today.viewed` event). Live wire replaced it.
- **Makefile:** all COMMANDS.md targets plus `make help`. Not-yet targets (`mock`, `smoke`, `build`, `build-api`, `build-api-multiarch`, `run-prod-local`, `deploy`, `rollback`, and `reset-demo`/`flag` with `ENV=demo|staging`) print "not available until Stage N" and exit 1. `reset-demo ENV=staging|production` refuses. No production deploy target. README.md added.
- **Migrations (all additive except the dropped view-tracking table):** `accounts.0006`, `core.0004`, `social.0003`.

### Targets run once (local)
Worked: `help, doctor, setup, up, dev (API, app and landing all answered), api, migrate, migrations, reset-demo, flags, flag, job, jobs, daily, circuit-round, eval, test, lint, fmt, check, api-client, openapi, test-web, build-web`. Guards confirmed: `reset-demo ENV=staging` refuses; `smoke`, `reset-demo ENV=demo` exit 1 with the Stage 5 message. Live check on the dev API: `make flag NAME=circuits TO=off` → `/api/circuits` 404 `feature_off` and `/api/config` shows `circuits: false`; `flag pulse off` was refused because `promotions` needs it; restored to everyone.
Not exercised: `admin-user` interactively (unit-tested with a mocked password prompt), `logs`, `shell`, `dbshell`, `down`, `mock`.

### Things to know
1. **Dev `.env` now has `FEATURES` with everything on** (it is gitignored). Production at beta start must use PRODUCTION.md §2b values: copying a dev `.env` to production with `payments` on is refused at startup, on purpose.
2. **Money-in-flight block** (cannot switch off `promotions`/`payments` with a paid campaign or open order) is not coded: those tables arrive in Stages 4d/4e. It must be added there.
3. **Make variables:** `make admin-user` takes `USER_NAME=` (not `USER=`, which is your login name). `ENV=` in make means the deployment (local, demo, staging) and is not passed to Django.
4. **Not done on purpose:** prettier/Playwright are not installed, so `fmt` is Python-only and `test-web` is a type check. `make check` now includes `pnpm typecheck`/`pnpm lint`, so it needs `node_modules`.
5. I ran `migrate`, `reset-demo`, `compute_matches`, `build_daily_drops` (0 built: already built for today), `run_circuit_round` (one circuit proposed for Asha, Priya, Arjun) and `expire_items` on your dev database. `make reset-demo` clears it.
6. Frontend: the app does not call the removed Today endpoints; `useFeatures()` (reads `/api/config`) is still to be built (Stage 4). Listed under "Frontend remaining".

### Frontend remaining (from B0)
`useFeatures()` hook over `GET /api/config`; hide tabs, entry points and routes for off flags (DESIGN.md §3); 404 screen for off-flag URLs; mock-mode "features off" scenario.

## B2 — Invite-only beta, backend (branch `backend-b2`): done, waiting for your OK
`make check` is green: ruff, mypy, 1,848 backend tests (Stories 1–5 PASS), frontend type check. The branch starts from `backend-b0` (B0 is not merged into `main` yet and B2 needs its flags and config), so merge B0 first.

**What it does (plain language).** With `BETA_MODE=true`, a signed-in person who has not been let in gets `403 beta_required` on every endpoint except `GET /api/me`, `POST /api/beta/redeem` and `/api/onboarding/*`. Public routes (`/api/health*`, `/api/config`, `/api/waitlist`) never needed a login. There are three ways in: an invite code, an email on the allowlist, or a waitlist entry a super admin approved. `/api/me` and `/api/config` carry `beta_access: bool` so the app knows whether to show the "Got an invite code?" screen.

- **One gate, one place:** `SupabaseAuth.authenticate` (`core/auth.py`) calls `apps/beta/gate.py`. Every protected route goes through it, so a new endpoint is gated without its author doing anything. A test loops over **every operation in the OpenAPI schema** and proves that exactly the three exempt routes are open. `/api/config` uses a new `identify()` (same sign-in check, no gate), which is how the app learns it is gated.
- **Redeem** (`POST /api/beta/redeem`): unknown, expired, used-up and revoked codes, and a revoked member, all get the identical `400 invalid_code` (a test compares the raw response bytes). The code row is locked inside a transaction, so two people racing for the last use give exactly one success (threaded test). Limits: 10/hour per member and 30/hour per address. An org code also joins the organisation (unless the member already has one). Someone already in gets 200 and nothing is used up.
- **Allowlist and approved waitlist** are matched against the Supabase-verified sign-in email only (`core/codes.plain_email`, the same strict ASCII check as organisation auto-join). Tests: an unverified provider, `user_metadata`, an email sent by the client, a demo token and a Unicode look-alike all fail. A match writes a `beta_access` row, so access does not depend on the list afterwards.
- **Waitlist** (`POST /api/waitlist`, public): always `202 {"status":"ok"}`, also for an email already on the list; 5 per hour per address (repeats count too, so it is not a free probe). The landing origin (`LANDING_URL`) is allowed by CORS for this one path only. A test asserts no email, note, college or IP appears in the captured logs.
- **Member invites** (`GET /api/invites`): 3 single-use codes per member, created on first call, tied to the inviter, logged as `invite.created`; the redeemer's `beta.access_granted` event records the inviter. The count is the env setting `INVITES_PER_MEMBER` (your choice); raising it tops everyone up. Members share **links only** (your choice): there is no "email a friend".
- **Email** (`core/email.py`): an email is written to an outbox table and sent after the transaction commits. If Resend is down or slow the request still succeeds, the row stays pending, and the `send_emails` job retries (1 min, 5 min, 30 min, 2 h, 12 h, then gives up). `EMAIL_BACKEND=resend` is now a real backend (5 s timeout, one quick retry); dev prints to the console, demo drops mail, tests use the in-memory outbox. The invite email links to `APP_URL/join?code=…&src=invite`.
- **Django admin:** invite codes (create, revoke, who used them; never deleted), waitlist (approve and send invite / reject), allowlist (normalised emails), beta access (grant, revoke, restore). Every action writes an audit_log row with ids only.
- **Commands:** `make invite-codes N=10 [USES=] [DAYS=] [ORG=] [NOTE=]`; `make job NAME=send_emails`. COMMANDS.md updated.
- **Migrations (all new tables):** `beta.0001` (invite codes, beta access, waitlist, allowlist), `core.0005` (email outbox). No existing table changed. Event types added: `beta.access_granted`, `invite.created`, `waitlist.joined`.
- **Seed:** `reset_demo` gives every seeded member access, so turning `BETA_MODE` on locally does not lock the personas out.

### Things for you to decide or know (B2)
1. **Exempt routes.** `GET /api/me` only (not PATCH): DESIGN.md puts the invite screen (step 3) before name and role (steps 4–5), so profile edits happen after access. `/api/onboarding/*` is exempt as you asked, which today means one route, the LLM bio extraction. That lets any signed-in person without an invite use up LLM calls (10/hour each, Google sign-up is free). If you would rather not pay for that before someone is invited, remove it from `EXEMPT_PREFIXES` in `apps/beta/gate.py`; the frontend is unaffected because extraction comes after the invite step.
2. **Admins skip the gate.** `partner_admin` and `super_admin` members pass without an access row, because a super admin appointed them. A revoked row still locks them out.
3. **Revoking sticks.** A revoked member is not re-granted by a code, the allowlist or an approved waitlist entry; use "Restore" in admin (Beta → Beta access). Revoking a code stops new uses only; people who already got in stay in.
4. **Approving a waitlist entry does two things:** sign-in with that verified email passes the gate, and a single-use code (30 days) is emailed. The code matters because it carries the `src=invite` link and skips the invite screen.
5. **Allowlist matching is exact after lower-casing.** `a.b@gmail.com` and `ab@gmail.com` are different entries; plus-addresses too.
6. **New env settings:** `INVITES_PER_MEMBER` (3) and `TRUSTED_PROXY_HOPS`. Per-address limits read `X-Forwarded-For`; with 0 hops only the socket address counts. **Staging and production refuse to start with 0**, otherwise everyone behind Cloud Run would share one bucket. Cloud Run should be 1; confirm with a real request at the Stage 5 smoke. Addresses are hashed before they reach Redis or the Postgres fallback.
7. **New startup rules:** `EMAIL_BACKEND=resend` needs `RESEND_API_KEY`; production refuses an `EMAIL_FROM` at `@resend.dev` (staging keeps the test sender, PRODUCTION.md §2). I edited the config builders in `test_config.py`, `test_audit_stage2.py` and `test_startup_refusal.py` to pass these, and `test_suspension.py` to skip `/api/waitlist` in its "public routes with no body" loop.
8. **Not tested against real Resend** (no API key here): the HTTP call is tested with a mocked client only. The Stage 5 smoke must send one real invite email.
9. **Schedule `send_emails` every 5 minutes in Stage 5** (added to `make jobs`). It uses row locks, so two overlapping runs do not double-send.
10. **Work-email codes still send directly.** `core/codes.send_code` (work-email and startup-claim verification) was not moved to the outbox, so with `EMAIL_BACKEND=resend` a Resend outage would make those two endpoints fail. Suggest moving them in B3 with the email notifications.
11. **`/api/me` change:** `beta_access` added to the response (PATCH `/api/me` and work-email confirm return `true`, since they were let through). Also on `/api/config`: `true` when `BETA_MODE` is off, `false` for anonymous visitors while it is on.
12. **Dev database:** I ran `make migrate` on it and exercised the live API with `BETA_MODE=true` on port 8011 (gate, redeem, invites, waitlist, the console invite email), then deleted the rows that check created. Your dev members have no access rows: run `make reset-demo` before you set `BETA_MODE=true` locally.
13. **Landing waitlist form and the app's invite screen are the same endpoint.** `src` accepts lower-case letters, digits, `-` and `_` (max 40), for example `landing-students`.

### Frontend remaining (from B2)
- **Invite code screen** (DESIGN.md §4 step 3): shown when `beta_mode && !beta_access` (from `/api/me` or `/api/config`); "Got an invite code?" field → `POST /api/beta/redeem`; `/join?code=…&src=invite` prefills it and skips the screen; on `invalid_code` show one inline sentence; handle `rate_limited`.
- **Waitlist screen** (secondary action on step 3): email, role, city, college, note → `POST /api/waitlist`, then the one-screen confirmation (same answer whether or not the email was already listed, so never say "already on the list").
- **Landing waitlist form** (all five audience pages and the investors fallback): same endpoint, `src` = the page (`landing-students` …). It calls the API from the landing origin, so the API's `LANDING_URL` must match the deployed landing site.
- **"Invite friends" screen** (no DESIGN.md screen yet; needs one): shows `GET /api/invites` (code, link, available/used) with a share button.
- App-wide: treat `403 beta_required` from any call as "send to the invite screen", and `useFeatures()`/config should expose `beta_access`.

## B3 — Settings, notifications, privacy and legal, backend (branch `backend-b3`): done, waiting for your OK
`make check` is green: ruff, mypy, 2,252 backend tests (Stories 1–5 PASS), frontend type check. `packages/api-client/openapi.json` and the client are regenerated.

**What it does (plain language).** A member can now change their settings, choose which notifications reach them and where, report and block people, download their data, delete their account, and accept a versioned privacy policy. Every email has a one-click unsubscribe. Bad input is refused, under-18 rules cannot be bypassed, and nothing personal goes into logs. The legal drafts for the lawyer are in `docs/legal/`.

- **Settings** (`apps/accounts/settings_api.py`): `GET /api/me/settings` returns the whole Settings screen in one call. `PATCH /api/me/privacy` (profile visibility, visible to org, circuits opt-in, allow requests), `PATCH /api/me/appearance` (theme, one of six accents, swipe between tabs), `PATCH /api/me/notification-preferences`. All reject unknown fields and values with 422, and booleans must be real `true`/`false` (a test caught `"yes"` and `1` being accepted by Pydantic's lenient mode; fixed with `StrictBool`). **Under-18:** public profile or `allow_requests: true` gives 403 `under_18_restricted`, whatever the client sends. `allow_requests` is enforced for strangers only (connections and same-organisation members are unaffected). `GET /api/me` now also returns `appearance`, `allow_requests`, `needs_consent` and `policy_version`.
- **Notifications** (`apps/notifications/services.py`): one `notify()` path. Nothing is sent when the recipient is suspended or deleted, when the actor and recipient blocked each other, when the feature flag is off for the recipient, or when that type is switched off for that channel. In-app rows are nudged over Supabase Realtime (`member:<id>`, id only). Email goes through the outbox with `List-Unsubscribe` and `List-Unsubscribe-Post`; under-18 email outside 09:00–19:00 IST waits for 09:00. A failing provider never fails the request (the existing retry job sends it later; Resend now receives the headers). The list endpoint gained `actor`, `text` and `target`, so the notification centre needs no follow-up calls.
- **Unsubscribe** (`apps/notifications/unsubscribe*.py`): signed, 90-day token holding only a member id and a type. `GET /api/unsubscribe` only reads (mail scanners are harmless); `POST` turns off that one type's email, signed out, safe to repeat. Tampered, expired, foreign or deleted-member tokens are 400 `invalid_token`. Rate limited per address.
- **Realtime security** (`core/realtime_sql.py`, migration `core.0007`): policies so a member hears only `member:<their id>`, conversations they are in, and circuits they are part of. `tests/unit/test_realtime_rls.py` proves it against the local Postgres with two members' real signed JWTs (it builds stand-ins for Supabase's `authenticated` role, `auth.uid()`, `realtime.topic()` and `realtime.messages`, and applies the same SQL the migrations apply). I checked the test fails if the SQL is broken (see "bugs found").
- **Report and block:** reports now cover startups too. The Django admin queue has Hide, Remove, Warn, Suspend and Dismiss (`apps/moderation/actions.py`), all audit-logged, each closing the report with what was done. Warn emails the author regardless of email preferences. Hidden startups disappear from the map, nearby, detail, jobs, Pulse and Live wire. **Block** (`POST/DELETE /api/members/{id}/block`, `GET /api/me/blocks`, and the chat's block button, now one service) removes the connection and pending requests, closes the chat, stops pending intros, and ends shared circuits (the others get the plain "declined" notice with no names). Added read-time filters that were missing: intros inbox, conversation list, circuits list, Daily Drop swipe, notifications. An end-to-end test blocks through the API and checks ten surfaces both ways, after first proving each surface did show the person.
- **Export** (`apps/accounts/export.py`): `POST /api/me/export` (one at a time, 3 a day) → `build_exports` job builds a zip in the private bucket with only that member's rows (other people as ids, and no text other people wrote to them) plus their pictures → email with a signed 24-hour link → `GET /api/me/export/download?token=` returns a 5-minute storage link only to the same signed-in member.
- **Delete account** (`apps/accounts/deletion.py`): `POST /api/me/deletion {"confirm":"DELETE"}` locks the account at once (403 `account_deleted` on every call); the `delete_accounts` job deletes the Supabase auth user (service role), files, profile data, needs, offers, connections and queued mail, ends circuits and intros in flight, hands startups to a teammate or unclaims them (the profile is never wiped, roles the member posted close), and leaves a "Deleted member" tombstone that old posts, replies and messages point at. Idempotent; a Supabase or storage failure leaves the account locked and the next run finishes.
- **Consent** (`core/gate.py`): `POST /api/me/consent`. A member who has not accepted the current `POLICY_VERSION` gets 403 `consent_required` everywhere except `GET /api/me`, consent, export, delete and support. It is the same single place as the beta gate (the old `apps/beta/gate.py` moved to `core/gate.py`); consent is checked before beta. A test loops over every operation in the OpenAPI schema.
- **Data requests:** correction is the normal profile edit; `POST /api/support` (question, correction, data request, grievance; 5 a day) emails the right inbox with a Reply-To and sends the member a reference; `GET /api/support/contact` (public) returns the grievance officer details from settings.
- **Retention** (`manage.py retention_cleanup`, `make retention`): removes accounts that never accepted the terms for 30 days, expired export files and rejected waitlist entries older than 90 days. Counts only in the log. RUNBOOK.md (new) has the Retention and Data requests sections.
- **Errors:** every path now gets our one error format: JSON handlers for 400/403/404/500, and a small middleware turns Ninja's bare "405 Method not allowed" into the same format (it kept `Allow`). Dev keeps Django's debug page on purpose (DEBUG is on there).
- **Circuits:** `GET /api/circuits` and `/{id}` now return, in one call, the three members with consent and done, `you_help` and `helps_you`, `time_left_seconds`, `next_step`, `can_mark_done` and `can_rate` per handover, and ratings only on handovers the viewer is part of. Every change nudges the Realtime channel `circuit:<id>`.
- **Legal drafts** (`docs/legal/`): privacy policy (every processor from PRODUCTION.md §5 and what it receives), terms, cookie notice, refund and cancellation policy, community guidelines, grievance officer page, and a README with the open questions for the lawyer. All start with "DRAFT — for lawyer review", with `<PLACEHOLDERS>` for the legal name, address, GSTIN and grievance officer.
- **Commands:** `make retention`, `make export MEMBER=<id>` and `make delete-account MEMBER=<id>` (both dev only). COMMANDS.md updated. New jobs for Stage 5 to schedule: `build_exports` and `delete_accounts` every 5 minutes, `retention_cleanup` daily (also in `make jobs`).
- **Migrations (all additive):** `accounts.0007` (Member: email, appearance, notification_prefs, allow_requests, deletion_requested_at, deleted_at; new table `accounts_dataexport`; one data step that sets `allow_requests=False` for existing under-18 members), `core.0006` (outbox: headers, member), `core.0007` (Realtime functions and policies), `moderation.0002` (report action, handled_at), `startups.0002` (hidden_at). I ran `make migrate` on your dev database; nothing else on it was changed (I set one demo persona's appearance and put it back).
- **New settings** (documented in `.env.example`): `POLICY_VERSION`, `GRIEVANCE_OFFICER_NAME`, `GRIEVANCE_EMAIL`, `GRIEVANCE_ADDRESS`; constants in `settings.py` for unsubscribe, export and retention periods and `FINANCIAL_RECORD_RETENTION_YEARS = 8` (**accountant to confirm**).

### Where I did something different from the plan, and why
1. **Sign-in and claim codes still send mail directly** (`core/codes.send_code`), not through the outbox. The outbox keeps the recipient address and the message for 30 days, which would break the rule that these addresses and codes are never stored. Instead a provider failure is now a clean 503 `email_unavailable` (the person retries) rather than a 500.
2. **The tombstone keeps its `auth_user_id`** (the plan said a fresh random one). With a fresh id, a token that is still valid for up to an hour would create a brand-new student account for the deleted person (the "suspend, don't delete" problem in the Stage 2 notes). Kept, the token just gets 403 `account_deleted`. The id is a pseudonymous UUID of a user that no longer exists at Supabase.
3. **Privacy fields left `PATCH /api/me`.** They live on `PATCH /api/me/privacy`; sending them to `PATCH /api/me` is a 422 (not silently ignored). Under-18 now gets a 403 instead of a silent downgrade to "members". I changed the three existing tests that used the old behaviour. The frontend did not use these fields.
4. **Flag-off notifications are no longer written** (before they were written and hidden). If you switch a flag on later, notifications from while it was off are gone. The read-time hiding stays for flags switched off after the fact.
5. **No production startup check for the grievance placeholders** (I considered one and left it out as outside the brief). The RUNBOOK checklist lists it; Stage 8/9 could enforce it.

### Bugs found by my own tests while building (all fixed, each with a test)
- A SQL function parameter called `circuit_id` had the same name as the column, so SQL read `l.circuit_id = circuit_id` as column = column and would have let anyone listen to any circuit. Renamed; the cross-circuit RLS test fails if it comes back.
- Hiding notifications from blocked people used `exclude(payload__actor_id__in=…)`, which in SQL also dropped every notification that has no actor (circuit and status updates) for anyone with a block. Now guarded with `has_key`.
- Pydantic accepted `"yes"` and `1` as booleans in the settings bodies (see Settings).
- A wrong HTTP method on a real route returned a bare HTML "Method not allowed" (now the standard JSON).
- A deleted member could still appear as a card in someone else's same-day Daily Drop (now excluded).

### Things for you to decide or know (B3)
1. **"Every notification type can be turned off" (DESIGN.md §8)** is true for the six types in the table (intros, applications, circuits, messages, Pulse replies, announcements). Two account notices cannot be turned off and are in-app only: moderator warnings (safety) and the startup notices (`startup.interest`, `startup.claimed`). Say if you want the startup ones to be switchable.
2. **Email addresses** are now stored on the member (your choice), copied from the verified sign-in email on each request. Demo personas have none, so dev and demo never send mail (the console backend prints it in dev).
3. **Email copy** names the other person by first name (`Sneha would like to meet you`) unless they are under 18, then it says "Someone". Say if you would rather never name anyone in an email.
4. **Under-18 quiet hours** apply to email only (there is no push yet). In-app notifications are not delayed.
5. **Unverified accounts** means "never accepted the terms for 30 days" (your choice). Real members who signed in before this ships and never see the consent screen would be purged after 30 days, so the consent screen must be live in the app before real users sign in. Seeded demo members have consent rows.
6. **Nothing was tested against real Supabase or Resend** (none here): the Realtime test uses stand-ins for Supabase's roles and functions; the auth-user deletion and the email provider are mocked. The Stage 5 smoke must: send one real notification email and check the `List-Unsubscribe` header in Gmail, delete a throwaway Supabase user through the app, and join a `member:<id>` channel with two real users.
7. **Request-log retention (30 days) is a Cloud Logging setting, not code.** Noted in RUNBOOK.md. It is a `[YOU]` step on cloud resources; I ran nothing there.
8. **Export limits:** the zip is built in memory and holds at most 200 MB of pictures (the rest are listed as skipped). Recommendations Circuit computed (matches, Daily Drop) are not in the export; the README inside the zip says so. The lawyer may want them in.
9. **Block cleanup ends a pending intro as `expired/stopped`** (quietly) so it does not skew the decline numbers on the partner dashboard. There is still no people-search endpoint, so "search" is covered by the surfaces that exist (profile, matches); add the block filter when search is built.
10. **DPDP s.9 (verifiable parental consent for under-18s) is not built.** The privacy policy draft flags it for the lawyer; the pilot may need to admit 18+ only.
11. **Stages 4d and 4e now have a box each** for what B3 could only hook: pausing a campaign when a claimant is deleted (`on_startup_unclaimed`), and keeping orders and payments through deletion (the Member row is never deleted, so those foreign keys will hold).
12. **Existing tests I edited:** `test_accounts` (privacy moved), `test_reports` (`take_down` is now `remove`; `staff_request` moved to `conftest.py`), `test_access_matrix` and `test_beta_gate` (new routes and exempt list), `test_suspension` (public loop), and payload assertions in `test_intros`, `test_posts`, `test_messaging` (payloads now also carry `actor_id`, an id).

### Frontend remaining (from B3)
- **Settings screens** (DESIGN.md has no Settings screen spec yet; it needs one): one screen from `GET /api/me/settings`: profile summary with the email hint, privacy toggles (with the under-18 rows locked and explained), notification preferences (type × in-app/email), blocked people with Unblock, Your data (Export, Delete), policy version accepted, Help and support contact.
- **Appearance picker:** theme (system/dark/light), the six accents with live preview, swipe-between-tabs toggle (`PATCH /api/me/appearance`); apply `appearance` from `GET /api/me` before first paint; offer the accent once at the end of onboarding (step 13).
- **Notification centre** over `GET /api/notifications` (`text`, `actor`, `target` are ready to render); subscribe to the private Realtime channel `member:<id>` (an event means refetch); bell dot from `/unread-count`.
- **Report and block sheets** on profiles, posts and messages (`POST /api/reports` now also takes `startup`; `POST /api/members/{id}/block`). Treat 404 on a blocked person as "gone".
- **Export and delete flows:** request, "preparing" state from `GET /api/me/export`, a `/settings/export?token=` page that calls the download endpoint (handle 404 and 410 `export_expired`); delete with a typed confirmation, then sign out (every later call is 403 `account_deleted`).
- **Consent screen** (Welcome screen's legal line becomes a real accept): show when `needs_consent`; `POST /api/me/consent {policy_version}`; treat any `403 consent_required` as "send to the consent screen". Consent comes before the invite screen.
- **Unsubscribe page** `/unsubscribe?token=`: call `GET /api/unsubscribe` to show which type, a button that `POST`s, and a link to notification settings. Needs no sign-in.
- **Help/FAQ** (with the support form → `POST /api/support`, grievance officer from `GET /api/support/contact`) and the legal pages from `docs/legal/` once the lawyer has approved the text (landing and app footer links).
- **404 and 500 pages** (the API now returns the standard JSON error everywhere, so the app can map `not_found` and `internal_error` to them).
- **Circuit screen and completion moment** from the single circuit response (`members` in ring order, `you_help`, `helps_you`, `next_step`, `time_left_seconds`); listen to `circuit:<id>` and refetch.

## B4 — Matching ML pipeline + onboarding state, backend (branch `backend-b4`): done, waiting for your OK
`make check` is green: ruff, mypy, 2,396 backend tests (Stories 1–5 PASS), frontend type check. `packages/api-client/openapi.json` and the client are regenerated (only the two new onboarding routes were added).

**What it does (plain language).** Circuit can now learn from what happened after it showed someone a match, without putting real members at risk. Every match shown is logged with the exact numbers the matcher saw (`feature_snapshots`). A weekly job (`train_ranker`) turns those logs plus the intro outcomes into a candidate model and tests it against the rule formula. A super admin then promotes it in Django admin: first **shadow** (its scores are logged, members still see the rule's order), then **A/B** (it orders the lists of 20% of members), then **active** (everyone). The rule formula is always the fallback, and a model only changes the **order** of a list: who is eligible, the Strong/Good words and the 0.55 cut still come from the rule.

- **Ranker package** (`apps/matching/ranker/`): `features.py` (the one fixed, ordered list of 21 features), `base.py`/`rule.py`/`model.py` (the Ranker interface, RuleRanker, ModelRanker over LightGBM LambdaRank), `registry.py` (the only code that changes a model's status), `serving.py` (which model orders which member), `guard.py` (the production rule), `snapshots.py`, `training.py`, `simulation.py`, `report.py`, `college_tiers.json`. lightgbm and numpy are imported inside functions, so the web process never loads them.
- **No banned inputs.** `Profile` (what the feature builder may know about a person) holds only role, verification level and location. A test checks no feature or Profile field name contains a banned word (college, tier, gender, religion, caste, language, name, organisation, email …), that changing a member's college, name, email and organisation leaves every feature identical, and that `features.py` never touches the college-tier file. The tier file is read only by the fairness check in `training.py`.
- **Snapshots.** `GET /api/matches` and `GET /api/drop/today` log what was shown (one row per viewer, candidate, surface and IST day, so a refresh adds nothing; best effort, a failure never breaks the page). The drop keeps the features with each card when it is built, so the snapshot is exactly what the ranker saw even if matches were recomputed since. Deleting an account deletes the snapshots on both sides; `retention_cleanup` removes snapshots older than a year; the data export leaves them out (like matches).
- **Training** (`train_ranker`): labels 0/1/2/3 (shown only / intro asked / accepted / met and rated 4–5 stars) credited to the latest snapshot of the same pair up to 14 days before the intro. Deterministic split by member (20% held out), LightGBM lambdarank with a fixed seed and one thread. Offline metrics for the model and for the rule on the held-out lists: NDCG@10, acceptance proxy (share of the top 3 that were accepted), eval-set agreement on `tests/eval/pairs.json`; fairness (below). It skips (exit 0) with too little data, no positive labels, or data it already trained on; otherwise it saves a **candidate**. Model files and metrics go to the private bucket under `ml/models/<version>/`, with a SHA-256 checked on every load.
- **Promotion** (Django admin → Matching → Model versions, read-only page with four actions): candidate → shadow → A/B → active, any step to retired. A/B and active need `beats_rule` (better NDCG@10 and acceptance, eval agreement not lower) and `fairness_passed`. A new model entering a slot retires the one in it, but a model can shadow while another is active. Every move writes an audit_log row and an event; a refusal shows the reason and changes nothing.
- **The production rule, and its proof.** In production only a model **trained in production on real data alone** may be in shadow, A/B or active. It is enforced in four places: `registry.promote`, `ModelVersion.save()`, the admin action (through `promote`) and `load_serving()` (which re-checks every time `compute_matches` runs, so a status forced with a raw `queryset.update` is ignored and the rule serves). `tests/unit/test_ranker_registry.py` takes a simulated model, a mixed one, one with any simulated rows, and one trained in staging, each with perfect metrics, and shows all of them refused for shadow, A/B and active in production, plus the three bypasses; it also shows a real production-trained model can be promoted (so the guard blocks the wrong models, not all models). In production, `train_ranker` also leaves simulated people out of the training set, and `simulate_network` refuses to run.
- **Simulation** (`make simulate`, dev only): synthetic members (city "Simulation", no organisation) with hidden tastes who are shown lists the rule made and answer intros by those tastes. They live in their own world (`members.is_simulated`): real matching, circuits and the kNN candidate search never see them, the retention purge skips them, and the simulation writes only intro rows and snapshots (no events, no notifications), so product analytics stay clean. Idempotent (`--reset` rebuilds).
- **Fairness check.** On the held-out lists, each candidate's place in their own list (0–1) is averaged per group; the spread across college tiers and across Bridge vs local must be ≤ 0.10, and each group needs 20+ rows. A dimension with fewer than two groups of that size **cannot be checked, which counts as a fail** (so a model never passes by default). Tier comes from `college_tiers.json` (your choice): partner college 3, the other seeded colleges 2, the two tier-1 colleges 1; colleges not listed are left out.
- **A/B report:** `make ranker-report` and the model's page in admin: shown, intro requests and accepts per arm and model version (real members only).
- **Onboarding state** (your request, and a Stage 3 gap): `members.onboarding`, `members.signup_source` (additive migration `accounts.0008`, together with `members.is_simulated`). `GET /api/onboarding/state` returns in one call the branch (default / investor / partner, from the Role answer), the screens in order, which to skip (invite when no beta or already in, name/city/organisation when known, the under-18 safety screen for adults), `current_step`, `completed_at` and every saved answer. `PATCH` saves a step, merges answers per step (fixed list of step names, each answer ≤ 2,000 characters), sets `signup_source` once (first touch wins; same pattern as the waitlist, now shared in `core/schemas.py`) and `completed`. Under `/api/onboarding/`, so it stays open while the beta gate is on (consent still applies). Answers are never put in events or logs. Export includes both fields; deleting an account clears the answers and keeps `signup_source` (a landing-page label).
- **Commands:** `make simulate`, `make train`, `make ranker-report`; `train_ranker` added to `make jobs` (weekly). COMMANDS.md updated. New event types: `ranker.trained`, `ranker.promoted`, `ranker.retired`, `onboarding.updated`.
- **Migrations (all additive):** `accounts.0008` (onboarding, signup_source, is_simulated), `matching.0003` (five fields on match_results; new tables feature_snapshots and model_versions). I ran `make migrate` on your dev database.
- **CLAUDE.md** data model and Matching ML text updated to match.

### Where I did something different from the plan, and why
1. **The simulation writes no events.** The plan said it would write `intro.*` events. Events are the product's analytics record (the partner dashboard and pilot metrics read them), and they cannot be deleted, so simulated ones would pollute them for good. Labels are built from `intro_requests` anyway (intro events only carry the intro's id, not the pair), so nothing is lost.
2. **One model per serving slot, not one in total.** Otherwise putting a new candidate in shadow would have retired the live active model.
3. **Snapshots are not written for under-18s** (viewer or candidate): behavioural training data about children is a DPDP risk. They are also excluded from training.
4. **New columns have database defaults (`db_default`).** I found this by running the pre-B4 code against the migrated dev database: Django drops a new NOT NULL column's default after adding it, so the previous release failed every INSERT into `match_results` (and would have failed the first sign-in on `members`) during a rolling deploy. All new columns now carry a database default and `tests/unit/test_migration_compat.py` fails if one does not. Worth keeping for every later migration (PRODUCTION.md §6, expand then contract).
5. **Postgres JSONB does not keep key order**, so features are stored by name and `to_row()` restores the contracted order; the order itself is asserted at build time.

### Things for you to decide or know (B4)
1. **A real model will rarely pass fairness at first.** Bridge matches are about 3% of the seed (PROGRESS "Matching" note 1), so there may be fewer than 20 Bridge rows in a test set for a long time, and an uncheckable dimension fails. That is deliberate (fail closed). If you want it softer, `RANKER_FAIRNESS_MIN_GROUP` and `RANKER_FAIRNESS_MAX_GAP` are in `settings.py`.
2. **Simulated results mean little.** On the dev simulation (300 members, 14 days) the model matched the rule on NDCG@10 (0.557 vs 0.556) but lost on acceptance and on the eval set (0.64 vs 1.0), so it correctly stayed a candidate and failed the fairness check. The point of the simulation is that the pipeline runs; it says nothing about real members. The first real promotion needs real data (BACKLOG.md).
3. **Eval-set bar is high:** a model must agree with the 14 hand-labelled pairs at least as often as the rule (which gets all 14 with the fake embedder). Those pairs were written by the engineers; replace them with pilot feedback before trusting this gate.
4. **Features that are empty today:** `candidate_response_rate` is unknown until a candidate has answered 3 intros in 90 days, and distance is unknown for members without a location. Both go in as "missing" (LightGBM handles that).
5. **Compute cost:** `compute_matches` now also builds 21 features per candidate and loads every member's friends once (one query). On the 300-member seed it is still a couple of seconds. Real LightGBM scoring happens only when a model is in shadow, A/B or active.
6. **`libgomp1`:** LightGBM needs the OpenMP runtime on the machine that runs `train_ranker` and `compute_matches`. The Dockerfile is still a placeholder: B5 must install `libgomp1` in the image (Debian/Ubuntu: `apt-get install libgomp1`), and check the image on ARM64 and x86_64.
7. **Not tested against real Supabase Storage** (none here): the model file goes through the same `put`/`get` as exports, tested with the in-memory stand-in. The Stage 5 smoke should train once on staging and load the file back.
8. **Dev database:** I ran `make migrate`, `make simulate` (300 members), `make train`, promoted the result to shadow and ran `compute_matches` (all 5,535 rows got a model score and no simulated member appeared), then removed everything. One slip: while rewriting the migrations I rolled `accounts.0008` back, which dropped the `is_simulated` flag and left my 300 test members looking like ordinary members. I checked the rows (exactly 300, city "Simulation", no organisation or email, nothing else in that city) and deleted just those. Your 300 seeded members are untouched and `compute_matches` was re-run.
9. **Compute time:** `compute_matches` on the 298-member seed went from 2.95 s to 3.72 s (+25%) because it now builds 21 features per candidate; the embedding-similarity feature uses numpy matrices (the first version in plain Python made it 6 s). A model in shadow adds one LightGBM call per member.
10. **Existing tests I edited:** `test_access_matrix` and `test_beta_gate` (two new routes) and `test_retention` (the counts dict gained `ranker_snapshots`). Nothing else.

### Frontend remaining (from B4)
- **Onboarding** (DESIGN.md §4): read `GET /api/onboarding/state` on launch to resume at `current_step`; save each screen with `PATCH` (the answer under its step key; e.g. `role: {"choice": "invest" | "partner" | …}` decides the branch); skip the screens in `skip`; send `signup_source` from `/join?src=…` on the first call; send `completed: true` at the end.
- Nothing visible for the ranker: members see no difference except a different order once a model is promoted.

## L5 — Landing cleanup (`landing-remove-old-steps`, from `main`): done, waiting for your OK

Only `apps/landing` changed (plus this file). Before and after screenshots of all six pages (375px and 1280px, dark and light): `apps/landing/screenshots/remove-old-steps/{before,after}/`.

**What was removed, and why.** The one old animated step block: the **"How it works" section** on `/`, `/students`, `/founders`, `/mentors`, `/investors` and `/partners` (three numbered steps, a picture slot each, and the Bridge arch line between them). Of its 18 slots, 11 were empty "screenshot coming" boxes, 4 were the old Daily Drop capture (`public/shots/`, which also showed a real-looking name, "Lavanya Srinivasan"), and only 3 were screens from `public/screens/` (Circuits on home and `/mentors`, Job on `/students`). Every one of those 3 screens is already in the L4 screens section of the same page, so nothing real was lost.
- Code deleted: `components/HowItWorks.tsx`, `components/Shot.tsx` (with its placeholder box), `public/shots/` (4 images), the `steps` field and the `STEPS` list, the Step type and helpers in `content/`, and the arch code in `LandingMotion.tsx` (the only thing that used `stroke-dashoffset`, so the motion rule is now transform and opacity only). A search found nothing else using them. `packages/ui` untouched.
- Kept: hero and logo video, audience tiles, L4 screens sections, proof sections, waitlist, FAQ, calls to action, footer, legal pages, `NEXT_PUBLIC_LAUNCH_MODE` behaviour (all four test builds pass).

**Copy that moved next to its screen** (as captions): Daily Drop "reason and mutual connection" → Home on `/` and the match card on `/founders`; "warm intros and three-way loops" → Circuits on `/`; "each introduction shows the reason" and "nothing starts without your yes" → People and Circuits on `/mentors`; "apply in one tap, ranked by skill match, not by college" → Job on `/students`; "list stays the same all day; the founder decides; unverified investors can browse but can't request" → Today's picks on `/investors`; "members join with your invite link or a verified email on your domain" → Partner home on `/partners`.
**Copy dropped** (no screen to sit next to; the pitch, FAQ and proof still cover it): "paste a bio and confirm skills" (onboarding), "claim your startup", "say what you need", "set your focus", "we verify your organisation" (still in the partners FAQ).

**Tests.** Deleted: the three-steps check, the arch tests (reduced motion, normal motion, no JavaScript), the Daily Drop theme-following test and the placeholder test. Added: no page has a "How it works" heading, a "screenshot coming" box or arch markup. One motion test used the arch's scroll to trigger every reveal; it now scrolls the page itself. Landing Playwright (375px and 1280px, both themes, axe and the spacing rules on every page): 397 passed, 1 skipped (tile hover on phone, as before). Typecheck and lint clean; the static builds in `make test-landing` pass.
**Lighthouse mobile on `/`** (compressing server, 3 runs each): 100 before, 100 after (LCP 1.5–1.7 s, CLS 0). Page weight at load went from 301 to 375 KiB because the screens section now sits closer to the top, so the browser fetches its first pictures sooner; they are still lazy.
**Spacing.** No double gaps or orphaned headings at 375px or 1280px; the spacing rules pass in both themes.

**Things to know**
1. `screenshots/landing-app-shots.mjs` (outside `apps/landing`, so not touched) wrote the deleted `public/shots/` Daily Drop files; it is now dead and can go.
2. The **step 01 onboarding idea** has no picture on the site any more; if you want the sign-up flow shown, an onboarding screen needs adding to the design references first.

## L4 — Landing screenshots (`landing-screenshots`, from `main`): done, waiting for your OK

Real app screens now sit on the home page and all five audience pages. Only `apps/landing` changed, plus `scripts/landing-screens.mjs`, one Make target (`make landing-screens`) and its COMMANDS.md entry. `apps/app`, `packages/` and `backend/` are untouched; nothing deployed.

**Where each screen is** (files `apps/landing/public/screens/<name>.{avif,webp,png}`; 780×1688 px = a 390×844 phone at 2x, each file ≤ 150 KB, largest is the PNG at 139 KB)

| Page | Section | Screens (reference file) |
|---|---|---|
| `/` | new "A look inside" after How it works | Home (Main), Jobs (Discover), Map, Circuits |
| `/students` | the proof section (was two "screenshot coming" boxes) | Jobs (Discover), Map, Job |
| `/founders` | new "What founders see" before the proof | match card with Bridge badge (Main, second card), People, Inbox |
| `/mentors` | new "What mentors see" before the proof | People, Circuits, Chat |
| `/investors` | beside the example pick | **InvestorHome** ("Today's picks", the exact screen, so I used it instead of Main/People) |
| `/partners` | inside the "Demo data" proof (was a "Gap map coming" box) | **PartnerHome** (no gap map or Desktop dashboard exists in the references, so the gap map is still not drawn) |

**How the pictures are made.** The reference files are a mock's template language and their `support.js` is not in the repo, so `scripts/landing-screens.mjs` expands that small syntax itself, runs each file's own sample data, and screenshots the phone in Chromium. It encodes through Pillow (AVIF, WebP, PNG; the PNG is lossless). `make landing-screens [SCREENS="map job"]` redoes them. Nothing from `docs/design-reference` is shipped, only the rendered pictures.

**Content check (item 2).** I changed these in the reference copy before rendering: startup names Tatvagrid, Sutragrid, Zetapulse, Medisetu, Kalam Labs, Neerflow became "Sample Agritech/Logistics/Deeptech/Healthtech/Edtech/Climate Co."; the partner name Kaveri Tech became "Sample Incubator"; people (Sakthi Vel, Kavya Raman, Harini Prasad, Yamini Iyer, Meera Krishnan, Farhan Ali, Divya Subramanian, Arun Prakash, Ishaan Reddy) became first names only; "RSVPs 90% full" became "RSVPs open". Every picture also carries a small "Sample data" label, and each list of phones says so in words. No logos, emails, phone numbers or testimonials were in the references. **Left in on purpose:** the partner dashboard's counts (148 members and so on) and the circuit's "Priya / Arjun / Asha" story names; they are sample data under the label, but you may prefer none on `/partners`.

**On the page.** `<picture>` AVIF → WebP → PNG with width and height, `loading="lazy"` (all of them are below the fold), alt text that says what the screen does (`content/screens.ts`), a CSS phone frame with no brand or notch (the frame follows the page theme). Motion: they use the existing section reveal (fade and rise, staggered), which `prefers-reduced-motion` already turns off; I added no new animation. On a phone the row is a swipeable strip (focusable with the keyboard, the page itself never scrolls sideways); from 1024px it is a grid. `NEXT_PUBLIC_LAUNCH_MODE` and the join switch were not touched (all four builds pass).

**Checks.** Typecheck and lint clean. Landing Playwright (375px and 1280px, both themes, including axe on every page and the premium rules): 401 passed, 1 skipped (tile hover on phone, as before); new `e2e/screens.spec.ts` checks every page's screens (formats, size attributes, alt, lazy, loads as AVIF, strip focusable, no sideways scroll). Lighthouse mobile (simulated slow 4G, brotli-compressed server, 3 runs): home performance 100 (LCP 1.4–1.6 s, CLS 0), `/students` 100, `/investors` 100; page weight 273 KiB because the screens are lazy. A plain unzipped Python server scored 84–89 on the same build; that is the server, not the page.

**Decisions / skipped**
1. **Dark only.** All references are dark (only Appearance previews light, and it is not on the list), so there is no light version of any picture. The dark phone in its frame looks fine on the light theme. A light set would need a light colour pass over the references (the README gives the light tokens): tell me if you want it.
2. **Pasted images:** none arrived in this chat, so `public/screens/source/` does not exist yet.
3. **Step 03 now uses real screens:** home (Circuits), `/students` "Apply in one tap" (Job) and `/mentors` "Join a circuit" (Circuits), as the top of the screen cropped into the step's frame (`Step.screen`). On home and `/mentors` the Circuits picture therefore appears twice (step and tour). **Still placeholders:** home step 01, students steps 01–02 are fine (02 is the Daily Drop), founders steps 01 and 02, mentors step 01 (no onboarding or claim reference screens were on the list).
4. `next build` on its own needs the `NEXT_PUBLIC_*` variables (same as before); the static builds in `make test-landing` are the build check.
5. The sandbox's Playwright browser was one version behind the repo's: I linked it locally outside the repo; nothing to do on your machine.

## L3 — Landing motion (`landing-pages`): done, waiting for your OK

`make check` is green (ruff, mypy, backend tests, frontend types, landing Playwright: 361 passed, 1 skipped = tile hover, which needs a pointer, on the phone project). Screenshots and recordings: `screenshots/landing-motion/` (script: `screenshots/landing-motion.mjs`).

**What was built (all six pages: `/`, `/students`, `/founders`, `/mentors`, `/investors`, `/partners`)**
- **Hero word stagger:** each headline word rises 16px and fades in, 60ms apart (the gap shrinks on long headlines so the total stays ≤ 700ms). It is a **CSS animation, not JavaScript**: it starts at first paint, so the headline never waits for the script bundle (that would cost Lighthouse LCP), and it ends visible with JavaScript off. The hero video now starts after the 700ms.
- **Bridge arch:** a thin `current` line drawn between the three "How it works" steps (1 → 2, then 2 → 3, 450ms each, 900ms in all), when each step comes into view, once. Steps in a row: it arches over the empty part of the number row. Steps stacked (phone): it bows through the page's left gutter. It is built by JavaScript and positioned absolutely, so with reduced motion or without JavaScript it simply does not exist and the layout never changes.
- **Section reveals:** sections below the fold fade and rise 12px when they come into view (once, 40ms stagger over the first 6 items). Only sections that start off-screen are ever hidden, and only by JavaScript, so without JavaScript everything is visible.
- **Audience tiles:** hover or keyboard focus lifts 2px and nudges the arrow 4px; press scales to 0.98. **Buttons:** press scales to 0.97. Both use the default spring (`duration: 0.35, bounce: 0`). When the motion code runs it turns off the old CSS press scale so two scales never stack (`html[data-motion]`).
- **FAQ:** the answer fades in and rises 8px as it opens, and fades out before it closes; the + turns to × (350ms). See decision 1.
- **Rules kept:** only `transform`, `opacity` and `stroke-dashoffset` are animated (a test checks every animation and every CSS keyframe); everything plays once; `prefers-reduced-motion: reduce` runs none of it (no animation, nothing hidden, no arch, `getAnimations()` is empty).
- **Library:** `motion` (`motion/mini` for the animations, plus its small `inView`, `hover`, `press` helpers). One client component, `LandingMotion.tsx`, mounted in the layout; the page components only gained `data-*` hooks. Landing JavaScript: +9.3 KB brotli (165.8 → 175.1 KB across all chunks).

**Lighthouse (mobile, simulated slow 4G, brotli-compressed server, 3 runs per page, 25 Oct 2026)**

| Page | Performance before | Performance after | A11y / best practices / SEO | CLS |
|---|---|---|---|---|
| / | 99–100 | 98–100 | 100 / 100 / 100 | 0 |
| /students/ | 99 | 98–99 | 100 / 100 / 100 | 0 |
| /founders/ | 99–100 | 98–99 | 100 / 100 / 100 | 0 |
| /mentors/ | 99 | 98–99 | 100 / 100 / 100 | 0 |
| /investors/ | 96–98 | 96–98 | 100 / 100 / 100 | 0 |
| /partners/ | 96–98 | 98–99 | 100 / 100 / 100 | 0 |

Every score stays ≥ 96, so ≥ 95 holds, though investors is the tightest (it is the same before and after: its Total Blocking Time was already the highest). Real-host numbers still need the Stage 5 deployment.

**Tests (`apps/landing/e2e/motion.spec.ts`, every page, 375px and 1280px)**
- Reduced motion: no animations running after a full scroll, nothing hidden or offset, no arch, FAQ opens with no animation, tiles stay still on hover.
- Normal motion: hero words end at rest; a below-the-fold item starts hidden and reveals; both arch lines end fully drawn; FAQ opens and closes; scrolling down, up and down again starts **no** new animation; only the three allowed properties are animated; layout shift is exactly 0 during load and a full scroll; tile hover and focus; button and tile press without a stacked CSS scale.
- No JavaScript: headline and every section fully visible, FAQ still opens.

**Decisions / things to know**
1. **FAQ height does not animate.** DESIGN.md said "height animates", but the rule for this work is transform, opacity and stroke-dashoffset only, and animating height moves the layout. So the answer fades and rises while the height changes at once. DESIGN.md §7 now says so. If you want the smooth height back it is a different trade-off (layout work every frame): tell me.
2. **The hero is CSS, not `motion`**, for the LCP reason above. It uses a fixed ease-out curve close to the default spring (a spring without overshoot), not the spring itself.
3. **The first scroll-reveal frame:** a section is hidden only after the page's JavaScript runs, and only if it is below the fold, so nothing flashes; a visitor who scrolls extremely fast before that moment just sees the content.
4. **Phone arch:** on a phone the steps are stacked about 700px apart, so the arch is a long thin line in the left gutter. It reads as a connector but you may prefer something else there; the desktop arch is the intended look.
5. **Spring fix after first push:** `motion/mini` rejects `type: "spring"` as a string (a development-only error, "Mini animate() doesn't support type as a string"); in a production build it was silently turned into a plain 300ms ease-out, so my first push was not using the spring. It now passes the `spring` generator from `motion`. A test checks the animations carry a CSS `linear()` spring curve, and I confirmed the dev error is gone on all six pages (and that putting the string back brings it back). The Lighthouse table was measured before this one-line change (+1.4 KB JS); I did not re-run it.
6. Not done on purpose: a real-phone test (DESIGN.md §13) and Lighthouse on the deployed site (Stage 5). `make test-landing` leaves a stale mock on port 3201 if one is already running (yours from `make dev`); harmless, the builds use it.

## L2 — The five audience pages (`landing-pages`, from `frontend-landing`): done, waiting for your OK

`/students`, `/founders`, `/mentors`, `/investors` and `/partners` are built; you approved the first four from their screenshots, `/partners` is waiting for your OK. Screenshots: `screenshots/landing-pages/<page>/{375,1280}-{dark,light}.png`, and `screenshots/landing-pages-flag-off/{investors,partners}/` for the flag-off versions. The branch is based on `frontend-landing` because L1 is not merged into `main` yet; a PR can follow once it is.

**What was built**
- **Shared pieces (the home page looks the same):** `Header` (marks the current page with `aria-current="page"`), `Hero`, `HowItWorks`/`Shot`, `Faq`, `Waitlist`, `Footer` (now also lists the five pages), tiles. Copy for every page lives in `src/content/pages.ts`; a page is added to `BUILT` there when its route ships (header, footer and sitemap follow it).
- **Each page:** its own headline and call to action (DESIGN.md §4 table), a one-line subhead, ONE primary button, three steps, one proof section, 5–6 honest FAQ answers, a text link to the same call to action after the FAQ, and its own title, description, canonical and Open Graph image (`/og.png`, the on-dark logo on black). All six URLs are in `sitemap.xml`.
- **Calls to action (switch `NEXT_PUBLIC_JOIN_LIVE`, below):** with it on, `APP_URL/join?role=<role>&src=landing-<page>` with roles student, founder, mentor, investor, partner. A valid `?src=` in the page address replaces the `src` in every link and in both forms (home too); an invalid one is ignored. Without JavaScript the page's own `src` is used.
- **Proof sections (no fake numbers or people):** students: two labelled placeholder frames (Jobs, Job page); founders: an **Example** "claim your startup" card; mentors: an **Example** anonymised circuit (marketer, founder, mentor); investors: an **Example** "Today's picks" card; partners: a **Demo data** gap-map frame (a placeholder: the dashboard isn't in the app yet). No "real roles near you" list (no public data source).
- **Feature flags at build time** (`src/lib/features.ts`): `GET /api/config` with a 3 s timeout and one retry; any failure means every flag is off, with a warning in the build log.
  - `investor_mode` off: `/investors` replaces the app button with a waitlist form (email, city; `role=investor`, `src=landing-investors`) and the line "Investor access opens soon."; the home investor tile opens `/investors/`.
  - `partner_mode` off: on `/partners` the "Bring Circuit to your campus" button jumps to a short form (name, organisation, city, email, note) sent to the public waitlist endpoint with `role=partner`. The endpoint has no name or organisation field, so the organisation goes in `college` and `note` starts with `Name: <name>`. No other API is called.
- **Tests (`make test-landing`, in `make check`):** two builds, flags on (:3101) and off (:3102), with a mock `/api/config`. 310 tests at 375px and 1280px, on three builds (flags on with the switch on, flags off with the switch on, flags on with the switch off): per page (headline, title, current page, one primary, steps, proof label, FAQ count, role and `src`, `?src=` carry-through, SEO, sitemap), both flag-off fallbacks with forms (success, carried `src`, duplicate, 422, 429, 500 with retry, only the waitlist endpoint called), axe and premium rules on every page in both themes (and on the flag-off versions), no numbers or placeholder text on any page.

**Lighthouse (mobile, simulated slow 4G, brotli-compressed server, 25 Oct 2026)**

| Page | Performance | Accessibility | Best practices | SEO |
|---|---|---|---|---|
| /students/ | 98–99 | 100 | 100 | 100 |
| /founders/ | 98 | 100 | 100 | 100 |
| /mentors/ | 98 | 100 | 100 | 100 |
| /investors/ (flag on, off) | 97, 97 | 100 | 100 | 100 |
| /partners/ (flag on, off) | 98, 96–98 | 100 | 100 | 100 |

**App screenshots still to come (labelled placeholders, "App screenshot coming: …")**
- Students: You offer, Apply, Jobs, Job page
- Founders: Claim, You need
- Mentors: You offer, Circuit ring
- Investors: Investor focus, Today's picks, Introduction request
- Partners: Organisation page, Invite, Partner home, Gap map (Demo data)
- Real screenshots used: the Daily Drop (students 02, founders 03, mentors 02, home 02). Replace a placeholder by adding `public/shots/<name>-{dark,light}.{avif,webp}` (780×1280) and setting `shot` in `src/content/pages.ts`.

**Things to know**
1. **Flags are baked into the static pages**, so changing `investor_mode` or `partner_mode` needs a landing redeploy (RUNBOOK.md, new "Landing site" entry).
2. **`/join` doesn't exist in the app yet, so there is a switch (`NEXT_PUBLIC_JOIN_LIVE`, default `false`).** Off: every button keeps its label but scrolls to a waitlist form on the same page and puts the cursor in it (home: the role you pressed is preselected in the form; audience pages: the form's role is the page's audience; /partners: the contact form). The form says "Circuit is invite-only right now. Join the waitlist and we'll send you an invite." and sends `role` and `src` (`landing-<page>`, or a valid `?src=`), so each sign-up shows its page and audience. Nothing links to `APP_URL/join`, so no button can lead to a 404. On: buttons link to `APP_URL/join?role=…&src=…`. A sheet on mobile was not built: an anchor works without JavaScript and needs no focus trap. **Turn NEXT_PUBLIC_JOIN_LIVE on after F2 ships /join and the app is deployed.** Like the feature flags it is baked in at build time, so flipping it needs a landing redeploy (RUNBOOK.md).
3. **Partner role value:** the partners button carries `role=partner` (what the app's join parser, the waitlist API and the home tile accept), not `partner_admin`.
4. Small changes outside the landing folder: `packages/ui/src/tokens.css` (one utility, `t-display-sm`), `scripts/serve-static.mjs` (a static server with brotli, used for Lighthouse runs and the screenshots), `screenshots/landing-pages.mjs`.
5. Not done on purpose: a real-phone test (DESIGN.md §13) and Lighthouse on the deployed site (Stage 5).

## L1 — Landing home page (`frontend-landing`, from `main`): done, waiting for your OK

`make check` is green: ruff, mypy, 2,396 backend tests (Stories 1–5 PASS), frontend type check, and the new landing Playwright suite (68 tests at 375px and 1280px). Screenshots: `screenshots/landing-home/` (`compare-*` has Landing.dc.html on the left, ours on the right; `home-*-{dark,light}.png` are full pages). Scripts: `screenshots/landing-compare.mjs`, `screenshots/landing-app-shots.mjs`.

**What was built**
- **packages/ui:** the Emerald colour tokens from DESIGN.md §5 for both themes (dark default, light follows the system, `data-theme` overrides) and the six accents; a `t-display` size for the landing headline only; a `Logo` component (lockup and mark, inline SVG made from `docs/brand/svg`, picks the on-dark or on-light file with CSS only, so there is no flash); `LinkButton` (a link that looks like the button); subpath exports (`@circuit/ui/Button`, `/Logo`, `/cx`) so the landing page does not pull the app's animation library into its JavaScript. Logo SVGs copied to `packages/ui/assets/logo/`.
- **apps/landing `/`:** header (logo + five audience links), hero ("Build with people near you.", one primary button "Join the beta"), "Who it's for" (five tiles), "How it works" (three steps), the pilot-city section (hidden), "Ask for an invite" (waitlist form), five FAQ answers, footer. `/privacy` and `/terms` are holding pages (not indexed). Favicon, apple-touch icon, brand PNGs and the Open Graph image (`og.png`, 1200×630, the on-dark logo on black) are in `public/`.
- **Hero video:** the poster (the video's last frame) is plain HTML, so the page is complete without JavaScript. The video (re-encoded to 37 KB, 540px, no audio) is added only after the page has loaded and only when it is on screen. Not added when the person asked for reduced motion or Data Saver.
- **Every CTA** goes to `APP_URL/join?role=<role>&src=landing-home` (the hero has no role). The header links jump to the tiles for now (audience pages are L2).
- **Waitlist:** email, role, city to `API_URL/api/waitlist` (8 s timeout, one retry after 1 s on network errors and 5xx). A duplicate shows the same message as a new sign-up (the API answers 202 for both). Nothing typed is logged or sent anywhere else; no trackers.
- **Config:** `NEXT_PUBLIC_APP_URL`, `NEXT_PUBLIC_LANDING_URL`, `NEXT_PUBLIC_API_URL` (a production build fails if one is missing; `next dev` has localhost defaults), plus new optional `NEXT_PUBLIC_CONTACT_EMAIL` and `NEXT_PUBLIC_COMPANY_LEGAL_NAME` (documented in `.env.example`).
- **SEO:** title, description, canonical, Open Graph and Twitter card, `robots.txt`, `sitemap.xml`, `lang="en-IN"`, theme colours.
- **Tests:** `make test-landing` (also in `make check`; COMMANDS.md updated) builds the site with test URLs, serves it on :3101 and runs: CTA links (role and src), the waitlist (success, duplicate, 422, 429, 500 with retry, network retry, browser validation), reduced motion and the video rules, axe and no horizontal scroll in both themes at both widths, no requests to other origins, no placeholder text or numbers, SEO tags, and the DESIGN.md premium rules (`apps/landing/e2e/premium.spec.ts`).
- **Housekeeping:** `apps/landing/out/` (a build folder that had been committed) is now untracked and gitignored.

**Lighthouse (mobile, simulated slow 4G, run 25 Oct 2026):** performance 99–100, accessibility 100, best practices 100, SEO 100 when served with brotli compression like a real host (269 KiB transferred). Served by Python's plain `http.server` (what `pnpm start` uses, no compression) performance is 83–90 only because the JavaScript is sent uncompressed; that is not what visitors will get on Vercel. Please re-run it on the real deployment (Stage 5).

**Remaining differences from Landing.dc.html**
1. The hero has the video square beside the headline (the mock is text only), so the headline breaks over two lines on desktop ("Build with people / near you.").
2. **App screenshots:** step 2 is a real screenshot of the Daily Drop (demo data, from `make dev`; dark and light versions). Steps 1 ("You offer", onboarding) and 3 ("Circuit ring", Circuits tab) are labelled placeholder frames reading "App screenshot coming: …", because those screens are not built yet. Replace them when onboarding and Circuits exist (add files in `public/shots/` and set `shot` in `src/content/home.ts`). Step frames are 39:64 (phone shape) instead of 4:5 so the whole card fits.
3. The pilot-city section is hidden (the mock shows bracketed placeholder text). `PilotCity` renders only when real numbers are passed; there is no public stats endpoint yet.
4. New "Ask for an invite" section (the waitlist form); the mock has none.
5. Footer: the company name and the Contact link appear only when the two new variables are set (the mock shows `[COMPANY LEGAL NAME]`).
6. The header uses the real brand lockup; nav links are 44px tap targets, so spacing is a little wider. Section spacing is 80px on a phone (120px on desktop as in the mock).
7. There is no light-theme version of the mock; light was built from the tokens.

**Things to know / decide**
1. **The token change reaches the app.** `packages/ui/src/tokens.css` was still the old palette, so I moved it to Emerald (the app now shows emerald primary buttons and the lavender light theme). No app screen file changed. I made one change to `apps/app/tests/premium.spec.ts`: in the light theme `primary` and `current` are the same green, so the accent check counted every primary button as accent use; it now ignores a primary fill. App premium specs pass (8/8).
2. **Waitlist without JavaScript:** the form is switched off in the server HTML and switched on once the page runs, and "Join the beta" works without JavaScript. A real no-JS submit would need a form-encoded waitlist endpoint with a redirect (backend, not done).
3. **`/privacy` and `/terms`** only say the documents are coming (the drafts in `docs/legal/` are not lawyer-approved). Replace them when approved. [YOU]
4. **Investor tile:** it links to the app with `role=investor` regardless of the `investor_mode` flag. L2 adds the build-time `/api/config` read (DESIGN.md §3) together with `/investors`.
5. The LAUNCH.md landing box stays unticked (it also covers the five audience pages, per-page SEO and the footer legal pages).
6. Not done on purpose: a real-phone test (DESIGN.md §13 item 4) and Lighthouse on the deployed site.

## Stage 4 — Frontends (branch `frontend-v2`): round 2 of Home done, waiting for your OK
Round 2 redoes Home for the new DESIGN.md (taken from `main`; CLAUDE.md F16 and LAUNCH.md Stage 3b/Home lines updated to match).
- **Removed:** TodayStrip, StoryViewer, the gradient story rings. `ring-signature` now exists only in tokens (for the circuit ring).
- **Built in `packages/ui`:** `Avatar` (photo or a circuit pattern from the member id, initial small in a corner; `PatternArt` for large areas), `LiveWire` (trace + 44px nodes, verb labels, accent outline for unseen, current-dot animation once per session) and `UpdateView` (full screen; swipe or buttons; picture, one line, why it matters, one action), `MatchStrength` (words only), reason-first `DropStack` card. Role cards hide "N% match" under 55.
- **App:** `LiveWireSection` replaces `TodaySection`. Rail shows words, not percentages. Sr-only "Pulse" heading fixes heading order.
- **Seed images:** `backend/seed/mockups.py` rewritten: 13 specific screens (lab dashboard, investor update with ₹, hiring board, assay chart, phone apps, code, SQL, serial monitor, Figma, email). No grey bars. `build.py` maps each post to a scene and writes real alt text. New `tests/unit/test_mockups.py`. `make reset-demo` run on dev.
- **Backend done on `stage-3c-livewire` (branch off `frontend-v2`), so the app uses the real endpoints and the temporary adapters are deleted:**
  - `GET /api/livewire` and `POST /api/livewire/seen` (`apps/social/livewire.py`). Five kinds, last 24h, ranked by shared capabilities, mutual connections and distance, unseen first, at most 6 of one kind and 12 in all. Same visibility rules as Pulse; under-18s never appear as needs or joins. New table `social_updateview` (additive migration `social.0002`). `StoryView`, `/api/today` and its tests stay until you decide to retire them (you chose additive).
  - Daily Drop: only Strong (0.75 or more) and Good (0.55 or more) are dropped. Cards add `strength`, `help_with`, `offers_you_need` (up to 3), `via` (the mutual who knows them) and `image` (their newest build log image). No raw score in the response.
  - `/api/matches`: `strength` replaces `score_percent`. Circuit cards still return `score_percent` (the weakest handover of a loop; not a person match). Thresholds are settings `MATCH_STRONG` and `MATCH_GOOD`.
  - Seed tuned: students trade skills in pairs (each needs what the other offers), some founders and mentors need what students can do and offer mentoring, needs are spread over the last days, two classmates "joined" just now. With the dev seed 248 of 292 members now have a Good or better match (52 Strong), up from 6.
  - Tests: `tests/api/test_livewire.py`, drop and strength tests, access matrix entries, seed test checks that cards are Strong or Good. 1,705 pass; ruff and mypy clean; OpenAPI and client regenerated.
- Checks: `pnpm typecheck`, `pnpm lint`, both builds pass; backend ruff, mypy, 1,672 tests and Stories 1–5 pass; axe clean at 375 and 1280, dark and light, no horizontal overflow. Screenshots: `screenshots/v2-home-r3/` (real endpoints; r2 was the adapter version) (`screenshots/shots-v2.mjs`).
- Known gaps: the seed gives few "via" lines and drop images (they depend on 2-hop connections and a build log with an image); seen nodes dim only the picture (text stays full strength for contrast); "Intro me" in the Update view sends the intro straight away; not tested on a real Android phone.
- Not started: landing, shell/sign-in, onboarding, composer, Discover, Circuits, Inbox, Profile, partner views, Playwright. LAUNCH.md Stage 4 boxes stay unticked.

## What exists (Stage 2)
- `core/auth.py`: `SupabaseAuth` is the API-wide default (an endpoint is protected unless it says `auth=None`). Checks signature (ES256 pinned), expiry, audience, issuer, `role=authenticated`, no anonymous users. Keys come from Supabase's JWKS (cached, throttled, served stale only up to 6 h). First login creates a `student` Member.
- `core/demo.py`: persona tokens, only when `DEMO_AUTH` (dev, or demo with `DEMO_PUBLIC`); the public demo never issues the `admin` persona. The app refuses to start with `DEMO_AUTH` in staging/production (config check + a second guard in `core/apps.py`, both tested).
- `core/permissions.py`: `require_role`, `require_level`, `require_org_admin`, `in_org`. No super-admin bypass.
- Organisations (`apps/organisations`): join by code or by verified email domain, leave, partner admin lists opted-in members and removes members. Everything is under `/api/organisations/mine`, so there is no org id in a URL to tamper with. Organisations are created in Django admin (join code auto-generated; "Regenerate join code" action; domains validated). Partner admins are appointed on the Member page.
- `core/ratelimit.py`: per-member limits, Redis first, Postgres fallback.
- RLS: on every table (migration `core.0002` + after every migrate); `core.0003` also revokes table privileges from Supabase's `anon`/`authenticated`. Documented in PRODUCTION.md §3a.
- CORS (`django-cors-headers`, approved by you), CSP and other security headers, HTTPS/HSTS/secure cookies for every non-dev env, 1 MB body limit (413 in the standard error format), `Cache-Control: no-store` on API responses.
- Tests: `tests/api/test_access_matrix.py` lists every route × every role and fails if a new route is not added to it. Stage 3 must extend it.

## finecomb audit (auth and permissions) — findings, all fixed with regression tests
Each regression test failed before its fix (67 red), and all pass now. Names are in `tests/unit/test_audit_stage2.py`.

| ID | Severity | Finding | Fix |
|---|---|---|---|
| F-01 | Medium | Placeholder or weak `SECRET_KEY` (e.g. the one in `.env.example`) was accepted in demo/staging/production. Demo tokens are signed with a key derived from it, so anyone could mint a token for any persona, including `admin`. | Config refuses weak/placeholder keys outside dev |
| F-02 | Medium | "Visible to my organisation" consent carried over to a different organisation (joining, or a super admin moving the member) | Reset on every join/move |
| F-03 | Medium | One lock was held during the JWKS download, so a slow Supabase stalled every sign-in, and an anonymous random-`kid` token could trigger it once a minute | Download happens outside the read path |
| F-04 | Medium | A table RLS could not secure was skipped silently, and nothing stopped Supabase's public API reading it with the anon key | `migrate` fails outside dev; client roles lose table privileges |
| F-05 | Medium | Demo (public) had DEBUG allowed and no HTTPS/HSTS/secure-cookie settings | Same rules as staging/production |
| F-06 | Low | Domain auto-join trusted any email string Supabase handed over (quoted, encoded-word, Unicode such as the Kelvin sign) | Only plain ASCII addresses count. Whether Supabase's mailer could be fooled by such an address is unverified; the check removes the question |
| F-07 | Low | Postgres rate-limit fallback stored every request, even refused ones | Refused requests are not stored |
| F-08 | Low | Public `/api/health/deps` made a live Supabase call per request | Result cached 15 s |
| F-09 | Low | Old signing keys were trusted forever if Supabase stayed unreachable | Trusted at most 6 h |
| F-10 | Low | Config accepted `http://` Supabase URL, `*` hosts, loose CORS origins, an unanchored preview regex | Rejected at startup |
| F-11 | Low | A domain claimed by two organisations joined an arbitrary one | Joins nobody, logs a warning |
| F-12 | Low | Join codes could not be rotated | Admin action, audit-logged |
| F-13 | Low | Client-supplied `X-Request-ID` was logged and echoed unchecked | Kept only if short and plain |
| F-14 | Low | CORS preflight and other early responses missed security headers; API responses had no `no-store` | Middleware moved outward; header added |
| F-15 | Info | The "docs hidden in production" test only exercised dev | Real production-config test |

Also found and fixed while writing tests: `remove_member` would have matched every org-less member if called with an org-less admin (the router blocked it; the service now refuses too).

Checked, nothing found: algorithm confusion (alg none, HS256 with the public key), forged/expired/not-yet-valid tokens, wrong audience/issuer, malformed claim types and hostile tokens (always 401, never 500), IDOR on member ids, role bypass on every route, PII in logs.

## Decisions for you / not changed
1. ~~No way to suspend a member~~ **Done (you approved it).** `Member.suspended_at` (migration `accounts.0003`, also added to the CLAUDE.md data model). A suspended member gets `403 account_suspended` on every authenticated route, checked against the database on each request, so it bites immediately even though their token lives ~1 h. Super admins suspend/reinstate from the Member list in Django admin (audit-logged; suspending also clears "visible to my organisation"). Suspended members are hidden from partner admins' lists. To remove someone, **suspend, don't delete**: a deleted Member is re-created as a fresh student by their next valid token.
2. **Under-18 members** who tick "visible to my organisation" show up in the partner admin's list. CLAUDE.md does not say whether to exclude them. I did not change it.
3. **Django admin login has no password-attempt limit** (TOTP is throttled by django-otp; the password step is not). Low risk with 2–3 staff and a hidden path, but a proper fix needs a trusted client-IP rule or `django-axes` (not approved). Suggest Stage 8.
4. **Assumptions about Supabase** (can't be tested offline): only Google + email OTP enabled, password sign-up off, "Confirm email" on, asymmetric JWT signing keys on. The API trusts the `email` claim only for those providers. Tokens can't be revoked before they expire (~1 h).
5. **Vercel preview CORS regex**: once the Vercel team slug is known, put it in `CORS_PREVIEW_REGEX` (see `.env.example`); otherwise another Vercel account could register a matching project name. Impact is small (bearer tokens, no cookies).
6. Not checked: the admin UI under the new CSP in a real browser; Supabase-side settings; the unused-but-installed PostGIS/pgvector functions in `public` being callable through Supabase's API (consider installing extensions in the `extensions` schema in Stage 5).

## Decisions / things to know (earlier)
- Dev DB is `circuit_dev` (not `circuit`): the `circuit` database in the docker volume already held an older Circuit build (24 tables, 300 members). It was left as it was.
- GDAL/GEOS/PROJ installed on the host; Django + pytest run on the host, Postgres + Redis in docker.
- No Supabase yet: dev uses DEMO_AUTH personas; tests use a locally signed JWT and a fake JWKS. GROQ key empty, so onboarding uses manual pickers in dev.
- `MemberSkill`/`MemberTrait` live in `matching` (not `accounts`) to avoid a circular app dependency.
- `Need` also has an embedding (spec only says offers).
- Cache fallback: Redis errors act as a miss and log a warning; callers read Postgres.
- `docker/backend/Dockerfile` is a placeholder; it needs a production server (gunicorn) that is not on the approved list. Ask in Stage 5.
- `/api/docs` and `/api/openapi.json` are not served in production (CLAUDE.md says OpenAPI is at `/api/openapi.json`; the committed `packages/api-client/openapi.json` is unaffected).
- `.env` got new dev defaults; `.env.example` documents all.

## Next
After your OK on B4: merge `backend-b4`, then B3b (promotions, Stage 4d; fill the `on_startup_unclaimed` hook and the money-in-flight block), B3c (payments), B3d, B3e, B5 (deploy: install `libgomp1`, job advisory locks, schedule `train_ranker` weekly and the other jobs), and the frontend sessions from the "Frontend remaining" lists (B0, B2, B3, B4). Block-from-profile, settings, export and delete now exist in the backend (B3).

## Social API (Stage 3b): what exists
- **Two new apps:** `social` (build logs, reactions, replies, follows, Pulse, Today, Daily Drop, connections, image uploads) and `messaging` (conversations, messages, Realtime nudges). `moderation` gained `POST /api/reports`. New tables: `social_*`, `messaging_*`, `accounts_connectionrequest`, plus `members.pulse_seen_at`. Migrations are additive.
- **One rule file:** `apps/social/relations.py` decides connected / blocked / same organisation, who can see a post (`can_see_post` and the list version `visible_posts`, tested against each other) and who may message or ask to connect (`may_message`, `may_request_connection`). Anything not allowed is a **404**, so a stranger cannot tell a minor from a missing member.
- **Visibility:** Everyone = any member; Connections = the author's connections; My organisation = the same organisation. Blocked (either way), suspended, hidden and removed posts are invisible. A hidden-profile author's "Everyone" posts reach only their connections.
- **Under 18:** can post to their organisation only (and only if they have one). Messages only with connections or staff of their own organisation, checked on **every send**. Connection requests to or from a minor stay inside one organisation. No Daily Drop, never dropped to others.
- **No public counts:** the API returns reaction totals and reply count only on your own posts (`private_stats`). Nothing returns follower, connection or view counts. A test scans the responses.
- **Images:** `POST /api/media/uploads` returns a signed upload URL (one JPEG/PNG/WebP, 5 MB); `.../complete` checks the real file type and size, strips EXIF/GPS by re-encoding, stores 1440 px and 480 px WebP and deletes the original. Alt text is required on every image. An upload belongs to its owner and can be attached once. Private buckets `posts` and `messages`; reads use signed URLs (cached 50 min).
- **Pulse:** `GET /api/pulse`: build logs from connections, organisation and followed startups' teams; new roles (followed startups, plus student skill matches within 25 km, at most 5); circuits closed by people you know, your intros that worked, startups newly claimed nearby; one "skills in demand" card a day. Newest first, 7 days, cursor paging. It shows what is new since you last called `POST /api/pulse/seen`, then `caught_up: true`; `include_seen=true` shows earlier items.
- **Today strip, Daily Drop:** `GET /api/today` (+ `POST /api/today/seen`), `GET /api/drop/today`, `POST /api/drop/today/{id}/swipe` (records intro/skip; the app then calls the intros endpoint). The drop "day" starts at 08:00 IST.
- **Messaging:** connected people chat directly; others send a request (the sender gets one message until answered; replying accepts). Block closes the chat and also blocks the person everywhere. Realtime uses **private Broadcast**: after saving, the backend sends only `{message_id, conversation_id}` to `conversation:<id>`; the app fetches the message from our API. Our tables stay closed to Supabase clients. One unread "new message" notification per conversation. Read receipts are stored but not shown to senders.
- **Admin:** Post and Reply have Hide / Remove / Restore actions; the Report page shows the reported content and has "Take down" and "Dismiss"; all audit-logged. Messages cannot be browsed in admin: a moderator reads a message only when it is reported.
- **Rate limits (per member):** posts 10/day, replies 60/day, reactions 300/hour, uploads 40/day, messages 300/day, new conversations 10/day, connection requests 20/day, reports 10/day.
- **Seed:** `reset_demo` adds about 35 build logs (drawn "screenshots" from simple shapes in `seed/mockups.py`: no photos, no people), replies, reactions, follows, 2 connection requests and 3 chats (one request: Ravi to Divya). Spread over the last week. Still idempotent (tested).
- **Jobs to schedule in Stage 5:** `build_daily_drops` at 08:00 IST, after `compute_matches`.

### Things for you to decide or know (Stage 3b)
1. **Pulse is calm on purpose, and may look empty on the second visit.** It shows only what is new since `POST /api/pulse/seen`. Stage 4 must call that when the person reaches the end and offer "See earlier this week" (`include_seen=true`). If you would rather it always show the whole week, say so; it is a small change.
2. **Cursor paging** (Pulse and messages) instead of limit/offset, because offsets skip items on a live feed. CLAUDE.md says "one pagination style"; lists elsewhere stay offset-based.
3. **Daily Drop contains people only**, not startups (match results are people). Startups reach Home through Pulse and the Map.
4. **Minors get no Daily Drop and no intro-style discovery.** My reading of "under-18: no appearance in public Discover until age is verified". Say if you want a drop of people from their organisation.
5. **Minor ↔ organisation staff:** a partner admin can message a minor of their own organisation (as a request the minor accepts). Partner admins can message members of their own organisation only. An org-mate who is not connected cannot message a minor.
6. **Alt text is required** (DESIGN §10 says images "require" it). The composer should pre-fill a suggestion.
7. **Browser uploads need Supabase Storage.** In dev (local files) the API works and the seed fills images, but the signed upload URL step answers 503 `uploads_unavailable`. Frontend work in Stage 4 should use a Supabase dev project's storage, or I can add a dev-only upload route.
8. **Not tested against real Supabase** (no project here): the Storage endpoints (`upload/sign`, `object/sign`), the Broadcast endpoint and the `realtime.messages` policy. The policy migration is skipped when the `realtime` schema is absent. Stage 5 smoke must send one real image and one real chat message. In Supabase: create private buckets `posts` and `messages` (5 MB, image types only) and turn off public access on Realtime channels.
9. **Config rules added:** staging/production refuse to start unless `STORAGE_PROVIDER=supabase` and `SUPABASE_SERVICE_ROLE_KEY` are set. `.env.example` updated. Existing config tests were adjusted for this.
10. **CLAUDE.md and PRODUCTION.md edited** (committed in the first commit): your new CLAUDE/LAUNCH/BACKLOG/DESIGN files; `PRODUCTION (2).md` became `PRODUCTION.md` with the Stage 2 text it had lost (database roles/RLS, rate-limit line) put back; `suspended_at` restored in the data model; `pillow` added to the approved libraries (you approved it); data model lists the tables I added (`media_uploads`, `connection_requests`, `story_views.startup`, `messages.removed_at`, `members.pulse_seen_at`).
11. **The `apps/` folder at the repo root** (Next.js build output and `node_modules` only) is not committed. Stage 4 creates its real contents.
12. **Declined connection requests:** the sender cannot ask the same person again for 30 days (they are told "recently declined"). Say if you would rather that stayed silent.
13. I ran `migrate`, `reset_demo`, `compute_matches` and `build_daily_drops` (twice: 191 drops, then 0) on your dev database. Re-run `make reset-demo` any time.
14. A real bug caught by my own test run: I had written a call to the chat broadcaster that passed `conversation_id` twice (mypy found it), and Pulse first showed only roles because the seed created every job "now". Both fixed (roles are capped at 5 in Pulse; the seed spreads job dates).

## Warm intros, circuits, dashboard: how they work and what to know (part 4)
- **Intros (F5):** a request goes to the best mutual connection (the broker) first. If they agree, it reaches the person; if not, the person never sees it. New field `IntroRequest.stage` (broker / target / done / stopped; additive migration `intros.0002`). Already-connected people skip the broker. Limits: 3 new requests per sender per rolling week, the target's `open_intro_slots` as their weekly capacity, a per-member rate limit, 7-day expiry. Under-18s cannot send intros (my choice: a 2-hop intro means contacting a stranger; say if you want it different). People who are hidden, blocked, suspended, minors or admins cannot be reached (404).
- **Circuits (F6):** edges between opted-in members (the giver offers what the receiver needs; same visibility and block rules as matching; under-18s excluded). Every 3-person loop is scored by its weakest handover, and a handover must score at least 0.2. OR-Tools CP-SAT picks the best set where nobody is used twice (one worker and a fixed seed, so it is repeatable; greedy fallback if the solver gives up). `run_round` is idempotent per ISO week and only places people not already in a proposed or active circuit. Consent lasts 72 h (one no ends it for all), the giver marks done, the receiver rates, and all three done means completed.
- **Dashboard (F8):** `/api/dashboard/{gaps,heatmap,network,acceptance}`, partner admins only, scoped to their own organisation with no id in the URL. Counts under 5 come back as `{value: null, hidden: true}`, small heatmap cells are left out, and the acceptance rate appears only when both counts are at least 5. Cached 5 minutes in Redis.
- **F7:** levels 1 (first sign-in), 2 (work email or claiming a startup) and 3 (super admin in Django admin, audit-logged) were already built; part 4 added tests that the badge shows on every surface. **LinkedIn as a level-2 proof is not built** (it needs LinkedIn OAuth).
- **Jobs to schedule in Stage 5:** `compute_matches` (daily), `run_circuit_round` (weekly), `expire_items` (every 15 minutes: expires intros and circuit proposals).

### Things for you to decide or know
1. **Partner counts include under-18 members** (aggregates cover the organisation's members). Earlier open question #2 (whether minors who tick "visible to my organisation" should be left out of the member list) is still open.
2. **Dashboard acceptance will often read "hidden" in a small pilot**, because both the asks and the accepts must reach 5. That is on purpose: a rate with a tiny accepted count would point at individuals.
3. **A circuit needs three opted-in people whose needs and offers form a loop.** The seed has exactly one (story 2). On real data loops will be rare until more people opt in, and the weekly job will simply propose nothing.
4. **A person with 0 free intro slots is also left out of circuits** (they share the visibility rules with matching).
5. **I ran `migrate`, `compute_matches`, `run_circuit_round` and `expire_items` on your dev database** to check them. Migration `intros.0002` applied, 1,142 matches were stored, and one proposed circuit for Asha, Priya and Arjun now exists there. `make reset-demo` clears it.
6. Two real bugs found by my own tests and fixed, each with a regression test: an intro's "expired" mark was rolled back by the error that reported it, and the heatmap merged members standing at the same point.

## Matching: how it works and what to know (part 3)
- **Pipeline:** `compute_matches` backfills missing embeddings, then for each member finds candidates (same capability in need/offer, plus pgvector nearest neighbours on the need/offer text), applies the hard filters, scores, ranks and replaces that member's `match_results` rows and Redis copy. The API only reads. At read time suspended, hidden and blocked people are filtered out again, so they vanish without waiting for the next run.
- **Score:** `0.5*complementarity + 0.2*affinity + 0.15*trust_path + 0.1*timing - 0.05*load_penalty` (weights in settings). Complementarity counts both directions: two people who help each other score 1.0, one-way help at most 0.6. Trust path uses the existing `core.graph.neighbours` (weakest link). Reasons are one sentence with no names.
- **A fit is shown to both sides.** If Priya needs SEO and Sam offers it, Priya sees Sam ("They offer seo, which you need") and Sam sees Priya ("You offer seo, which they need").
- **A match needs a real need/offer fit** (complementarity at least 0.05). Same-city or shared-trait people with no fit are not shown; "A possible fit" would not help anyone. The local/bridge split is therefore only a label and a ranking rule.
- **Hard filters:** self, blocks (either way), hidden profiles, candidates with 0 free intro slots, partner/super admins, and any pair involving a student who is farther than 25 km (or in another city when a location is missing). Under-18s match only people in their organisation or already connected.
- **Ranking:** top 20, at most 5 per sector, about 25% Bridge when enough exist, and nobody appears in more than 30 lists.

### Things for you to decide or know
1. **Bridge share is about 3% on the seed, not 25%.** Bridge needs two known, different sectors, and only founders have one (taken from their startup). Mentors, investors and students have none, so they are never Bridge. Story 1 works. If you want mentors and students to count (for example by the sectors they say they know), that is a data-model decision; I did not change it.
2. **The appearance cap depends on processing order** (members by id), so later members are more likely to miss a popular mentor. Fair enough for v1; a fairer split is a BACKLOG item.
3. **The eval set was written by the engineers, not real users.** 14 pairs, 100% agreement on the fake embedder. It guards against regressions; it cannot tell us whether the weights are right. Replace and extend it with pilot feedback. There is no baseline for the real `fastembed` model yet (it needs a model download): run `manage.py eval_matching --update-baseline` once with `EMBEDDING_PROVIDER=fastembed`. `MATCH_MIN_SIMILARITY` (0.8) is a guess until then.
4. **Heads-up on a slip I made and fixed:** I overwrote the existing `core/graph/__init__.py` with a new file, noticed when the old tests failed to import, restored it from git and used the existing `neighbours()` instead. Nothing was lost.

Note: Stage 3 part 1 was committed on `backend-core`, the branch Stages 1–2 were merged from. Say if you want a fresh `stage-3` branch from here.

---

## Status check 2026-10-24

Read-only check of the backend against CLAUDE.md, LAUNCH.md and PRODUCTION.md. Judged by code and tests, not ticked boxes. Branch `main` (clean, no unmerged branches).

### Sessions
_Update: B0 has since been built; rows marked FIXED below are resolved by it. Everything else is as found._
| Session | Status | What's missing or wrong | Size |
|---|---|---|---|
| Stages 1–3 (foundation, auth, core API) | DONE (boxes in LAUNCH.md are unticked) | Tick Stages 1, 2, 3. Gaps inside Stage 3: no `members.onboarding` (resumable state), no `signup_source`, no LinkedIn level-2 proof | S |
| B0 Stage 1b flags + commands | MISSING at check time; **FIXED in B0 (branch `backend-b0`)** | No `core/flags.py`, `feature_flags` model/admin, `members.is_tester`, `@require_flag`, `/api/config`, `manage.py flags`. Makefile has 9 targets (up, down, migrate, run, test, check, reset-demo, openapi, lint); no `make help` and about 25 COMMANDS.md targets are absent | M |
| B1 Stage 3b social API | WRONG at check time; **flags and Today-strip removal FIXED in B0** (boxes ticked, code and tests exist) | Pulse, Daily Drop, Live wire and circuits are not behind flags. Legacy `/api/today`, `StoryView` still present (replaced by Live wire) | S |
| B2 Stage 4b beta gate | MISSING at check time; **FIXED in B2 (branch `backend-b2`)** | No invite_codes, beta_access, waitlist, `BETA_MODE`, gate, waitlist endpoint, invite emails (no resend) | M |
| B3 Stage 6+7 backend | PARTIAL | Only `Consent` and in-app notifications exist. Missing: settings and appearance endpoint, notification prefs, export, delete, email notifications, block from profile, data requests, retention job, `docs/legal/` | L |
| B3b Stage 4d promotions | MISSING | Nothing built | L |
| B3c Stage 4e payments | MISSING | No razorpay dependency, models, webhook, live-key startup check | L |
| B3d Stage 4f investor mode | MISSING | `Startup.sector` and `stage` are free-text CharFields (spec: sector FK, stage enum); no team_size, open_to_investors, fundraising_status, sectors table, investor profiles/picks | L |
| B3e Stage 4g partner mode | MISSING | `Organisation` lacks website, logo, about, verified_at; no cohorts, calls, events, RSVPs, announcements | L |
| B4 Stage 4c ML | MISSING | No Ranker interface, feature_snapshots, model_versions, lightgbm, simulate/train commands | L |
| B5 Stage 5 deploy | MISSING | Dockerfile is a placeholder, no `make smoke`, no advisory locks on jobs, no scheduler | M |
| B6 Stage 8+9 | MISSING | No Sentry, CI, backups | M |
| B7 Stage 10+11 + handoff | MISSING | No FRONTEND_HANDOFF.md, `tests/contract/`, RUNBOOK.md, frozen/versioned openapi, funnel query | L |

### Features F1–F22 (backend parts)
- DONE: F2, F3, F4, F5, F7 (except LinkedIn), F8, F10, F11, F17 (minors' rules tested in `test_social_minors.py`).
- PARTIAL: F1 (extraction + manual fallback yes; no resumable state, no `signup_source`), F9 (persona tokens yes; no `reset-demo ENV=demo`), F12 (export, delete, settings, appearance, email notifications missing), F13 (admin exists; no flags, waitlist, campaign, refund admin), F14 (no waitlist endpoint, no role/src on join).
- WRONG: F6, F15, F16 (work exists, but no feature flags; F16 still has the old Today strip).
- MISSING: F18, F19, F20, F21, F22.

### Checks
1. **Data model.** Missing fields: `members.is_tester`, `appearance`, `onboarding`, `signup_source`; `organisations.website/logo/about/verified_at`; `startups.team_size/open_to_investors/fundraising_status`, sector as FK. Missing tables: sectors, cohorts (+ startups/members), calls, call_applications, partner events, rsvps, announcements, investor_profiles, investor_picks, invite_codes, beta_access, waitlist, campaigns, campaign_stats_daily, hidden_promotions, promotion_packages, orders, payments, refunds, webhook_events, feature_snapshots, model_versions, feature_flags. Extra (not in the spec list): RateLimitHit, ClaimRequest, WorkEmailVerification, CircuitRound, MediaUpload, ConnectionRequest, StoryView, UpdateView (some are already noted in earlier PROGRESS entries). Name clash to resolve: the spec's partner `events` table versus the existing append-only `events` app.
2. **Feature flags.** `core/flags.py` does not exist; no feature is wrapped.
3. **Endpoints.** 100 operations in `openapi.json`; the committed file matches a fresh export (no drift). `tests/api/test_access_matrix.py` fails if any route is missing from the role matrix, so no endpoint is without a test. DESIGN.md §4 screens with no endpoint: landing waitlist, onboarding resume, Investor home, Partner home, Organisation page, calls and events, Settings/Appearance, Promoted items, `/api/config`.
4. **Safety rules.**
   - DEMO_AUTH blocked in staging/production: **proven** (`test_startup_refusal.py`, `test_config.py`).
   - Counts under 5 hidden: **proven** (`test_dashboard.py`).
   - Under-18 rules (messages, connections, drop): **proven** (`test_social_minors.py`).
   - Razorpay live keys only in production: **not built**.
   - Webhook signature on the raw body: **not built**.
   - Promotions never affect ranking: **not built** (no test possible yet).
   - No banned ML features: **no ML yet**; `scoring.py` documents that college is never an input but no test asserts it. Not tested.
5. **Commands.** Working: `up`, `down`, `migrate`, `run`, `reset-demo`, `openapi`, `lint`, `test`, `check`. Missing: everything else in COMMANDS.md (`setup`, `dev`, `doctor`, `help`, `flags`, `flag`, `job(s)`, `daily`, `circuit-round`, `eval`, `smoke`, `build*`, `deploy`, `rollback`, `admin-user`, `shell`, `dbshell`, …).

### Test results
`make check`: ruff and mypy clean. **1705 passed, 0 failed, 0 skipped** (171 s). Stories 1–5 all PASS. Not run: Playwright and frontend checks (backend scope).

### Next 3 sessions, in order
1. **B0** (PROMPTS.md "B0 — feature flags + commands"): flags, `/api/config`, full Makefile; also wrap pulse/daily_drop/circuits and retire `/api/today` + `StoryView` (the leftover B1 work).
2. **B2** (PROMPTS.md "Backend sessions (B1–B7)" template, `<SESSION>` = B2, `<STAGES>` = Stage 4b): beta gate and waitlist. Needed before any real invite.
3. **B3** (same template, B3, Stages 6+7, with the legal-drafts extra line): settings, appearance, export/delete, consent versions. Also add `members.onboarding` and `signup_source` here or in B2.
Then B3b, B3c (use the "Payments" prompt), B3d, B3e, B4–B7.

### Changed in the spec since this was built
- Feature flags (seven flags, `/api/config`, `is_tester`) — nothing was flagged.
- Today strip and story rings replaced by Live wire (old endpoint and table still in code).
- Daily Drop / matches show strength in words; raw scores hidden (done).
- Resumable onboarding, `signup_source`, role pre-set from landing links.
- Appearance settings stored on the member.
- Sectors as a fixed table; investor fields on startups; investor mode (F21).
- Partner mode (F22): organisation verification, cohorts, calls, events, announcements.
- Invite-only beta (F18), promotions (F19), Razorpay payments (F20).
- Under-18 members see only promoted roles from verified startups.

---

## Status check 2026-10-24 (after B3)

Read-only check against CLAUDE.md, LAUNCH.md, PRODUCTION.md and COMMANDS.md, judged by code and tests, not ticked boxes. Run on branch `backend-b3` (tree clean). B3b–B3e are intentionally not built and are not counted as missing.

### 1. Sessions
| Session | Status | Branch / merged? | What's missing or wrong | Size |
|---|---|---|---|---|
| B0 Stage 1b flags + commands | DONE | `backend-b0`, PR #9 + #10, merged | `core/flags.py` (7 flags, dependency check, Redis→Postgres), `@require_flag` on every pulse / daily_drop / circuits operation, `/api/config`, `manage.py flags`, 43 Makefile targets, on/off/testers tests. Small: the box "blocks switching off promotions/payments while money is in flight" is ticked, but only a comment exists in `set_audience` (the tables arrive in 4d/4e; B3b/B3c must build it and have no box for it yet). The `/api/config` "contract test" is a shape test in `tests/api/test_flags_api.py`; there is no `tests/contract/` yet (B7) | S |
| B1 Stage 3b social API | DONE | `backend-core` / `stage-3b` / `stage-3c-livewire`, PRs #4, #6, #8, merged (flags wrapped in B0) | Posts, Pulse, Live wire, Daily Drop (strength in words), messaging, Realtime RLS, reports, rate limits, minors' rules all have code and tests. Today strip retired on purpose | S |
| B2 Stage 4b beta gate | DONE (backend) | `backend-b2`, PR #11, merged | Gate in `core/gate.py` called only from `SupabaseAuth.authenticate`, redeem, waitlist, allowlist, member invites, outbox email, admin. The two frontend boxes stay unticked correctly | S |
| B3 Stage 6 + 7 backend | DONE (backend) | `backend-b3`, PR #12, merged on GitHub (local `main` not fetched yet) | Settings, appearance, notification prefs, unsubscribe, Realtime policies, report/block, export, deletion, consent, support, retention, `docs/legal/`. Open on purpose: Help/FAQ, 404/500 screens, circuit moment (frontend), lawyer review [YOU] | S |
| B4 Stage 4c ML | NOT STARTED | – | No Ranker interface, `feature_snapshots`, `model_versions`, lightgbm, `simulate_network`, `build_training_set`, `train_ranker`, banned-features test | L |
| B5 Stage 5 deploy | NOT STARTED | – | `docker/backend/Dockerfile` is a placeholder (CMD `manage.py check`; gunicorn is not approved yet, ask first). `make smoke`, `build*`, `deploy`, `rollback` print "not available". No scheduler, no job locks | M |
| B6 Stage 8 + 9 | NOT STARTED | – | No `.github/`, no CI. `sentry-sdk` is in `pyproject.toml` but never imported. No backups, no restore drill | M |
| B7 Stage 10 + 11 + handoff | NOT STARTED | – | No `FRONTEND_HANDOFF.md`, no `tests/contract/`, no versioned openapi, no funnel query. RUNBOOK.md exists but only has Retention and Data requests | L |

Gaps outside B0–B7 that will block B7:
- **Stage 3 box still open:** `members.onboarding` (resumable state) and `members.signup_source` do not exist on the Member model. The B7 per-source funnel query and the frontend `/join` flow need them. Do this before B7, in B4 or as a small fix.
- Boxes ticked without full code: only the "money in flight" block in B0 (above). Nothing else found.
- Ticked boxes that match code and tests: all other B0–B3 boxes.

### 2. Tests
`make check` (ruff, mypy, pytest, frontend type check): **2,252 passed, 0 failed, 0 skipped** (3 min 19 s). Stories 1–5 all PASS. `pnpm typecheck` passes for api-client, ui, app and landing. `packages/api-client/openapi.json` matches a fresh export (no drift). Not run (not set up yet): Playwright, axe.

### 3. Safety items
| Item | Result | Evidence |
|---|---|---|
| Beta gate on every non-exempt endpoint | **tested** | `tests/api/test_beta_gate.py` loops over every operation in the OpenAPI schema and asserts exactly the exempt routes are open |
| Consent gate | **tested** | `tests/api/test_consent_gate.py` (same loop, version change, ordering before the beta gate, privacy rights stay open) |
| DEMO_AUTH refused in staging / production | **tested** | `tests/unit/test_startup_refusal.py` (config check and the second guard in `core/apps.py`) |
| RLS on every table | **tested** | `tests/unit/test_core.py` (no public table without RLS), `tests/unit/test_rls.py`, `tests/unit/test_realtime_rls.py`; `migrate` fails outside dev if a table is open |
| Export and delete touch only the member's own data | **tested** | `tests/api/test_export.py` (zip holds only the requester's rows, others as ids, foreign link = 404), `tests/api/test_delete_account.py` (other people's data untouched), `tests/api/test_account_idor.py` |
| Block hides both ways | **tested** | `tests/api/test_blocks.py` (every surface checked before and after, both directions), plus `test_posts`, `test_social_idor`, `test_notification_service` |
| No names / emails / tokens in logs | **tested** | `tests/api/test_logging_pii.py`, `test_logging_pii_b3.py` (new endpoints and jobs, export zip) |
| Feature flags off → 404 | **tested for the 3 flags that have code** | `tests/api/test_flags_api.py` (pulse, daily_drop, circuits; on, off and testers). The endpoint list in that test is a hand-written sample, not every operation. Flags `investor_mode`, `partner_mode`, `promotions`, `payments` have no code yet, so nothing to test |

Nothing is broken. Weak spots to remember: (a) none of the Supabase / Resend / storage calls were tested against the real services (stand-ins only; Stage 5 smoke must do it); (b) the flag-off test could miss a new flagged endpoint that is not added to its sample list.

### 4. What to run next
1. **Housekeeping first (5 minutes):** `git fetch && git checkout main && git pull` (local `main` is behind PR #12), then open a small PR for this PROGRESS.md commit (it sits on the already-merged `backend-b3`). Branch `backend-b4` from the updated `main`.
2. **Next session: B4** (Stage 4c, ML pipeline), PROMPTS.md "Backend sessions" template with `<SESSION>` = B4, `<STAGES>` = Stage 4c and the B4 extra line ("Use /effort high. Prove with a test that a simulation-only model can never be promoted in production.").
3. **Fix before B7 (can ride in B4):** add `members.onboarding` and `members.signup_source` (additive migration).
4. **Add two boxes** so they are not forgotten: in Stage 4d and 4e, "block switching off `promotions` / `payments` while a paid campaign or an open order exists" (B0 left only a comment).
5. After B4: B3b–B3e (when you want them), then B5, B6, B7.

### Startup load (one-off, branch `startup-load`)
`manage.py load_startups <csv> [--dry-run]` / `make load-startups`: 148 Chennai + Bengaluru startups from `backend/data/startups_2026-10.csv`, unclaimed, `source=crawler`, extras in the new `startups.details` json. Nominatim pins (cached), none for empty or area-only addresses. Startups without a pin have a page but are not on the map until an address is fixed in Django admin (Startups → latitude / longitude). Tests: `tests/unit/test_load_startups.py`.
