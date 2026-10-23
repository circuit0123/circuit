# Circuit — Progress

Stages 1–2 are merged into `main` (PR #1, from `backend-core`). Stage 3 continued on `backend-core` (you chose to keep it). Backend only for now.

## Status
- Stage 1 — Backend foundation: **done and merged**
- Stage 2 — Auth and security: **done and merged** (make check green: ruff, mypy, 321 tests; finecomb audit done, findings fixed)
  - One box stays open on purpose: rate limits on extraction/intros/applications/reports/claims. Extraction, intros, applications, claims and org join now use `check_rate`; only reports remain, and that endpoint arrives in Stage 6.
- Stage 3 — Core features API: **done, waiting for your OK** (make check green: ruff, mypy, 1109 tests, Story 1–5 all PASS)
  - Part 1 (committed): members/profile, onboarding extraction, work-email verification, startups nearby/map/views/interest, claim flow.
  - Part 2: jobs and applications (F11), in-app notifications, strict list of event types (`EVENT_TYPES`; an unknown type raises).
  - Part 3: matching (F4). `manage.py compute_matches` (1.3 s for the 300-member seed), `GET /api/matches`, `manage.py eval_matching` with 14 hand-labelled pairs, demo story 1 test.
  - Part 4: warm intros (F5), exchange circuits (F6), partner dashboard (F8), verification badge tests (F7), demo stories 2–5, and `make check` printing `Story n: PASS/FAIL` (marker `@pytest.mark.story(n)` plus a summary hook in `tests/conftest.py`).

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
Stage 4 (frontends) and Stage 5 (deploy staging and demo), after your OK. The backend API for every Stage 3 feature exists and `packages/api-client/openapi.json` is current. Stage 6 will add report/block, which also finishes the Stage 2 rate-limit box.

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
