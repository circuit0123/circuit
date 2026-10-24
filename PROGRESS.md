# Circuit — Progress

Stages 1–2 are merged into `main` (PR #1, from `backend-core`). Stage 3 continued on `backend-core` (you chose to keep it). Stage 3b is on its own branch, `stage-3b` (from `backend-core`). Backend only for now.

## Status
- B2 — invite-only beta, backend (Stage 4b): **done on `backend-b2` (branched from `backend-b0`), waiting for your OK** (details in "B2" below)
- B0 — feature flags + commands: **done on `backend-b0`, waiting for your OK** (details in "B0" below)
- Stage 1 — Backend foundation: **done and merged**
- Stage 2 — Auth and security: **done and merged** (make check green: ruff, mypy, 321 tests; finecomb audit done, findings fixed)
  - One box stays open on purpose: rate limits on extraction/intros/applications/reports/claims. Extraction, intros, applications, claims and org join now use `check_rate`. Reports now exist too (Stage 3b, `POST /api/reports`, limited to 10 a day), so that box can be ticked.
- Stage 3b — Social API (F15–F17): **done, waiting for your OK** (make check green: ruff, mypy, 1657 tests, Story 1–5 PASS; details in "Social API" below)
- Stage 3 — Core features API: **done, waiting for your OK** (make check green: ruff, mypy, 1109 tests, Story 1–5 all PASS)
  - Part 1 (committed): members/profile, onboarding extraction, work-email verification, startups nearby/map/views/interest, claim flow.
  - Part 2: jobs and applications (F11), in-app notifications, strict list of event types (`EVENT_TYPES`; an unknown type raises).
  - Part 3: matching (F4). `manage.py compute_matches` (1.3 s for the 300-member seed), `GET /api/matches`, `manage.py eval_matching` with 14 hand-labelled pairs, demo story 1 test.
  - Part 4: warm intros (F5), exchange circuits (F6), partner dashboard (F8), verification badge tests (F7), demo stories 2–5, and `make check` printing `Story n: PASS/FAIL` (marker `@pytest.mark.story(n)` plus a summary hook in `tests/conftest.py`).

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
Stage 4 (frontends) and Stage 5 (deploy staging and demo), after your OK. The backend API for every Stage 3 and 3b feature exists and `packages/api-client/openapi.json` is current. Stage 6 still owns "block a person from their profile" (blocking from a chat already works) and settings/export/delete.

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
