# Circuit — Progress

Branch: `backend-core` (LAUNCH.md Stages 1–3, backend only)

## Status
- Stage 1 — Backend foundation: **done**
- Stage 2 — Auth and security: **done, awaiting OK** (make check green: ruff, mypy, all tests; finecomb audit done, findings fixed)
  - One box stays open on purpose: rate limits on extraction/intros/applications/reports/claims. The helper and limits exist and org join uses them; those endpoints arrive in Stage 3, and each adds one `check_rate(member.pk, "<action>")` line.
- Stage 3 — Core features API: not started

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
Stage 3 (core features API), after your OK. Demo story tests (`tests/demo/`) and the eval set are still empty; they belong to Stage 3.
