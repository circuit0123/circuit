# Circuit — Progress

Stages 1–2 are merged into `main` (PR #1, from `backend-core`). Stage 3 continued on `backend-core` (you chose to keep it). Stage 3b is on its own branch, `stage-3b` (from `backend-core`). Backend only for now.

## Status
- L2 — landing audience pages (F14): **done, waiting for your OK** (branch `landing-pages`, from `frontend-landing`; not pushed yet) (details in "L2" below)
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

## L2 — The five audience pages (`landing-pages`, from `frontend-landing`): done, waiting for your OK

`/students`, `/founders`, `/mentors`, `/investors` and `/partners` are built; you approved the first four from their screenshots, `/partners` is waiting for your OK. Screenshots: `screenshots/landing-pages/<page>/{375,1280}-{dark,light}.png`, and `screenshots/landing-pages-flag-off/{investors,partners}/` for the flag-off versions. The branch is based on `frontend-landing` because L1 is not merged into `main` yet; a PR can follow once it is.

**What was built**
- **Shared pieces (the home page looks the same):** `Header` (marks the current page with `aria-current="page"`), `Hero`, `HowItWorks`/`Shot`, `Faq`, `Waitlist`, `Footer` (now also lists the five pages), tiles. Copy for every page lives in `src/content/pages.ts`; a page is added to `BUILT` there when its route ships (header, footer and sitemap follow it).
- **Each page:** its own headline and call to action (DESIGN.md §4 table), a one-line subhead, ONE primary button, three steps, one proof section, 5–6 honest FAQ answers, a text link to the same call to action after the FAQ, and its own title, description, canonical and Open Graph image (`/og.png`, the on-dark logo on black). All six URLs are in `sitemap.xml`.
- **Calls to action:** `APP_URL/join?role=<role>&src=landing-<page>` with roles student, founder, mentor, investor, partner. A valid `?src=` in the page address replaces the `src` in every link and in both forms (home too); an invalid one is ignored. Without JavaScript the page's own `src` is used.
- **Proof sections (no fake numbers or people):** students: two labelled placeholder frames (Jobs, Job page); founders: an **Example** "claim your startup" card; mentors: an **Example** anonymised circuit (marketer, founder, mentor); investors: an **Example** "Today's picks" card; partners: a **Demo data** gap-map frame (a placeholder: the dashboard isn't in the app yet). No "real roles near you" list (no public data source).
- **Feature flags at build time** (`src/lib/features.ts`): `GET /api/config` with a 3 s timeout and one retry; any failure means every flag is off, with a warning in the build log.
  - `investor_mode` off: `/investors` replaces the app button with a waitlist form (email, city; `role=investor`, `src=landing-investors`) and the line "Investor access opens soon."; the home investor tile opens `/investors/`.
  - `partner_mode` off: on `/partners` the "Bring Circuit to your campus" button jumps to a short form (name, organisation, city, email, note) sent to the public waitlist endpoint with `role=partner`. The endpoint has no name or organisation field, so the organisation goes in `college` and `note` starts with `Name: <name>`. No other API is called.
- **Tests (`make test-landing`, in `make check`):** two builds, flags on (:3101) and off (:3102), with a mock `/api/config`. 202 tests at 375px and 1280px: per page (headline, title, current page, one primary, steps, proof label, FAQ count, role and `src`, `?src=` carry-through, SEO, sitemap), both flag-off fallbacks with forms (success, carried `src`, duplicate, 422, 429, 500 with retry, only the waitlist endpoint called), axe and premium rules on every page in both themes (and on the flag-off versions), no numbers or placeholder text on any page.

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
2. **`/join` doesn't exist in the app yet**, so every call to action leads to a 404 on a local app until the sign-up flow ships.
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
