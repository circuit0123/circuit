# Circuit — Launch plan (fresh build: Django + Next.js)

How to use this file:
- Each session prompt names the stage(s) to do. Do only those; read CLAUDE.md,
  PRODUCTION.md and those stages.
- Each stage ends with: tests pass, commit on the stage branch, tick boxes here, update
  PROGRESS.md, explain in plain language, stop.
- [YOU] items need the human (accounts, money, approvals). Never fake them; ask.
- Scope is frozen to CLAUDE.md features F1–F14. New ideas go to BACKLOG.md.

---

## Stage 0 — Accounts ready [YOU] (before any code)
- [ ] GitHub organisation with 2FA required; empty repo created; branch protection on main
- [ ] Supabase demo + staging projects: postgis and vector extensions on; Google + email OTP on
- [ ] Google OAuth client (Web): Supabase callback URLs as redirect URIs; app URLs + localhost:3000 as origins
- [ ] Upstash Redis: demo + staging databases
- [ ] Vercel: projects circuit-landing, circuit-app-demo, circuit-app-staging (repo connected)
- [ ] GCP project (staging) in asia-south1 with billing + budget alert; gcloud logged in on laptop
- [ ] Temporary staging deploy service-account key (Cloud Run Admin, Artifact Registry Writer, Secret Manager Secret Accessor, Service Account User) + short-lived Vercel token, added as secrets
- [ ] Resend test API key; LLM key (Gemini or Groq free tier for dev/demo/staging)
- [ ] All values in the password manager and local .env (never pasted into chat)

## Stage 1 — Backend foundation (Session A)
- [x] Monorepo layout per CLAUDE.md; uv project; pnpm workspace root
- [x] docker compose: Postgres 16 + PostGIS + pgvector (multi-arch Dockerfile), Redis
- [x] Django settings per ENV, validated at startup; .env.example complete
- [x] structlog JSON request logging with request_id; one error format; one pagination style
- [x] All models + migrations per CLAUDE.md data model; GIST, HNSW and FK indexes
- [x] Capability and trait lists; seed generator with the five demo stories; `manage.py reset_demo` (idempotent)
- [x] Django admin registered for all models (read-only where appropriate); TOTP 2FA required; disabled in demo
- [x] `/api/health` and `/api/health/deps`
- [x] core/cache (Redis + Postgres fallback), core/graph (recursive SQL + networkx), core/embeddings (fastembed + fake), core/llm (mockable)

## Stage 2 — Auth and security (Session A)
- [x] Ninja auth class: Supabase JWT via JWKS (signature, expiry, audience, pinned alg); Member lookup by auth_user_id; first-login member creation
- [x] DEMO_AUTH persona tokens in dev/demo; startup refusal in staging/production (tested)
- [x] Permission helpers: require_role, require_level, organisation scoping
- [x] Organisations: create (super admin), join by code or verified email domain, leave, remove
- [x] RLS deny-by-default on every table (migration); app DB role documented
- [ ] Rate limits on extraction, intros, applications, reports, claims (helper `core.ratelimit.check_rate` + limits are built and wired on org join, extraction, verify, claim and applications; still to add: intros and reports, when those endpoints exist)
- [x] CORS exact origins + staging preview regex; security headers; Django SECURE_* settings
- [x] Tests: expired/forged tokens, every role on every endpoint, IDOR on every ID, org scoping, no PII in logs

## Stage 3 — Core features API (Session A)
- [x] Members, startups, needs, offers; smart onboarding endpoint with LLM + manual fallback (F1)
- [x] Geo: nearby + bbox endpoints; student skill-to-startup score; view/interest tracking (F2)
- [x] Claim flow via company email domain (simulated in dev/demo) (F3)
- [x] Jobs + applications endpoints (F11)
- [x] Matching: scoring, candidates, ranking, reasons, bridge flag; `compute_matches`; Redis cache; eval set + `eval_matching` (F4)
- [ ] Warm intros with capacity limits and outcome rating (F5)
- [ ] Circuits: edges, cycles, CP-SAT, `run_circuit_round`, consent, expiry, mark done, rating (F6)
- [ ] Verification levels (F7); partner dashboard endpoints with counts < 5 hidden (F8)
- [ ] Events written for every product action (F10); notifications model + endpoints
- [ ] Demo story tests 1–5 pass; `make check` prints PASS/FAIL per story
- [ ] OpenAPI spec clean; every endpoint described

## Stage 4 — Frontends (Session B, in parallel with Stages 1–3)
- [ ] DESIGN.md first: palette (hex), type scale, spacing, motion rules, circuit line motif, voice; banned list (gradients, glassmorphism, emoji icons, buzzword copy, lorem ipsum, fake stats)
- [ ] packages/ui components: Button, Card, Badge (verification, Bridge, Hiring), Chip, Avatar, BottomSheet, Modal, Tabs, Toast, Skeleton, EmptyState
- [ ] packages/api-client generated from the backend OpenAPI spec (script; mock spec until Stage 3 lands)
- [ ] apps/landing: hero, students / founders / circuits sections, partner CTA, footer (privacy, terms, contact), SEO + OG metadata, links to APP_URL
- [ ] apps/app shell: Supabase sign-in (Google + OTP), auth callback, role-based tabs (mobile bottom bar, desktop sidebar), environment banner, persona switcher (dev/demo)
- [ ] Onboarding: role → paste bio → confirm chips → location → consent (under-18 hidden)
- [ ] Screens: map, jobs list + job page + apply, my applications, founder applicants, matches with reasons + Bridge badge, warm intro request, circuits loop card (accept/decline, live status), partner dashboard
- [ ] Every screen: loading, empty, error states; works at 375px and 1280px
- [ ] Playwright tests for the five demo stories at both widths; axe checks

## Stage 5 — Deploy staging + demo (Sessions A + B together)
- [ ] Backend image builds on ARM64 + x86_64; deployed to Cloud Run (staging, demo); jobs + scheduler created
- [ ] Vercel: landing, app-staging, app-demo deployed with §2a variables
- [ ] Supabase redirect URLs + Google OAuth origins set for staging and demo
- [ ] `make smoke URL=...`: landing loads, app sign-in page loads, CORS preflight passes, one authed read, one write, test email
- [ ] `make reset-demo ENV=demo` + nightly reset job
- [ ] Smoke passes on staging and demo

## Stage 6 — Product basics
- [ ] Account settings: edit profile, notification preferences, privacy, export, delete
- [ ] Notifications in-app (Supabase Realtime) + email (Resend) for intros, applications, circuits; unsubscribe
- [ ] Report and block users; moderation via Django admin
- [ ] Help/FAQ, support contact, 404 and 500 pages
- [ ] Circuit completion moment and live status polished

## Stage 7 — Legal and privacy
- [ ] Privacy policy, terms, cookie notice drafts (landing + app)
- [ ] [YOU] Lawyer review
- [ ] Consent stored with version + timestamp; data request process; retention cleanup job

## Stage 8 — Reliability and monitoring
- [ ] Sentry (backend + app), uptime monitors, alerts to a phone
- [ ] Timeouts/retries/fallbacks audit; job failure alerts; `expire_items` every 15 min
- [ ] [YOU] Production Supabase (Pro), Upstash, Cloud Run, Vercel production project
- [ ] Production backups + PITR; restore drill to staging
- [ ] Budget alerts on all paid services

## Stage 9 — CI/CD hardening
- [ ] GitHub Actions on PR: ruff, mypy, pytest, tsc, ESLint, Playwright, axe; merge blocked on red
- [ ] Merge → staging deploy + smoke; tag → demo; manual approval → production
- [ ] Replace temporary keys with Workload Identity Federation; delete the old key and Vercel token
- [ ] Rollback documented and tried once

## Stage 10 — Quality and performance
- [ ] PWA for apps/app: manifest, icons, offline shell, update prompt, install prompt (incl. iOS)
- [ ] Lighthouse ≥ 90 mobile (landing, app Home); bundle budget; lazy-load map and charts
- [ ] Load test staging (~1,000 concurrent users); fix top bottlenecks
- [ ] Privacy-friendly analytics for the pilot funnel

## Stage 11 — Cleanup (alone, last)
- [ ] Remove dead code, unused deps, debug code, stray TODOs; consistent patterns
- [ ] README: setup in under 10 minutes on Mac and WSL
- [ ] RUNBOOK.md: deploy, rollback, restore, rotate secrets, outage, data request, takedown
- [ ] All tests and smoke green

## Stage 12 — Go live
- [ ] [YOU] Buy domain; follow PRODUCTION.md §2a switch checklist
- [ ] [YOU] Fresh-eyes test with 5 real students + 1 founder; fix what confused them
- [ ] Production deploy + smoke
- [ ] [YOU] Pilot college onboarded
