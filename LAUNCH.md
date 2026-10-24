# Circuit — Launch plan (fresh build: Django + Next.js)

How to use this file:
- Each session prompt names the stage(s) to do. Do only those; read CLAUDE.md,
  PRODUCTION.md and those stages.
- Each stage ends with: tests pass, commit on the stage branch, tick boxes here, update
  PROGRESS.md, explain in plain language, stop.
- [YOU] items need the human (accounts, money, approvals). Never fake them; ask.
- Scope is frozen to CLAUDE.md features F1–F22. New ideas go to BACKLOG.md.
- Features beyond the core ship behind feature flags (CLAUDE.md "Feature flags"); a
  stage is done when its code is merged and tested with its flag on AND off.

## Build order (backend first, then frontend)
Backend sessions, each on its own branch, merged via PR before the next:
- B0: Stage 1b (feature flags, `/api/config`, Makefile + COMMANDS.md). Short; do first.
- B1: Stage 3b (social API) → then wire ONLY the Home screen on the frontend branch for
  an hour to check the API shape fits DESIGN.md
- B2: Stage 4b backend (beta gate, waitlist endpoint, invite emails)
- B3: Stage 6 + 7 backend (settings, notification prefs, export/delete, email
  notifications, Realtime auth, consent versions, data requests, retention job,
  legal drafts in docs/legal/ for the lawyer)
- B3b: Stage 4d backend (promotions: campaigns, serving slots, caps, stats, admin)
- B3c: Stage 4e backend (Razorpay payments: packages, orders, signature check,
  webhooks, reconciliation, refunds)
- B3d: Stage 4f backend (investor mode: sectors, investor profiles, picks, founder
  opt-in, filtered feeds)
- B3e: Stage 4g backend (partner mode: org verification, cohorts, calls, events,
  announcements, partner home)
- B4: Stage 4c (ML pipeline) — can run in parallel on a second account
- B5: Stage 5 backend (API, jobs, scheduler on staging + demo)
- B6: Stage 8 + 9 backend (monitoring, production env, backups + restore drill,
  backend CI, keyless deploys)
- B7: Stage 10 + 11 backend (API load test, cleanup, RUNBOOK.md) + FRONTEND_HANDOFF.md
  (per screen: hook name, returned shape, endpoints, errors, Realtime, rate limits) +
  contract tests with reusable JSON fixtures (also used by mock mode) + frozen
  openapi.json + per-source funnel query for signup_source
Frontend sessions afterwards: every "Frontend remaining" item recorded in PROGRESS.md,
built against FRONTEND_HANDOFF.md and DESIGN.md.

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

## Stage 1b — Feature flags and commands (session B0, short)
- [x] core/flags.py with the seven flags from CLAUDE.md "Feature flags"; `FEATURES` env parsing; dependency validation at startup
- [x] feature_flags model + Django admin (audit-logged; blocks switching off promotions/payments while money is in flight); members.is_tester
- [x] `@require_flag` for routers; `flags.enabled()` for services and jobs; Redis cache with Postgres fallback
- [x] `GET /api/config` (public) with env, beta_mode, features; contract test
- [x] `manage.py flags` (list / set); on and off tests for every flag that already has code
- [x] Makefile with every target in COMMANDS.md (`make help` prints them); README points to COMMANDS.md
- [x] Existing features wrapped in their flags (pulse, daily_drop, circuits …) with on/off tests

## Stage 2 — Auth and security (Session A)
- [x] Ninja auth class: Supabase JWT via JWKS (signature, expiry, audience, pinned alg); Member lookup by auth_user_id; first-login member creation
- [x] DEMO_AUTH persona tokens in dev/demo; startup refusal in staging/production (tested)
- [x] Permission helpers: require_role, require_level, organisation scoping
- [x] Organisations: create (super admin), join by code or verified email domain, leave, remove
- [x] RLS deny-by-default on every table (migration); app DB role documented
- [x] Rate limits on extraction, intros, applications, reports, claims
- [x] CORS exact origins + staging preview regex; security headers; Django SECURE_* settings
- [x] Tests: expired/forged tokens, every role on every endpoint, IDOR on every ID, org scoping, no PII in logs

## Stage 3 — Core features API (Session A)
- [x] Members, startups, needs, offers; smart onboarding endpoint with LLM + manual fallback (F1)
- [ ] Onboarding state on the member (current step + saved answers) so the app resumes mid-flow; organisation auto-detect from verified email domain; instant first Daily Drop for brand-new members
- [x] Geo: nearby + bbox endpoints; student skill-to-startup score; view/interest tracking (F2)
- [x] Claim flow via company email domain (simulated in dev/demo) (F3)
- [x] Jobs + applications endpoints (F11)
- [x] Matching: scoring, candidates, ranking, reasons, bridge flag; `compute_matches`; Redis cache; eval set + `eval_matching` (F4)
- [x] Warm intros with capacity limits and outcome rating (F5)
- [x] Circuits: edges, cycles, CP-SAT, `run_circuit_round`, consent, expiry, mark done, rating (F6)
- [x] Verification levels (F7); partner dashboard endpoints with counts < 5 hidden (F8)
- [x] Events written for every product action (F10); notifications model + endpoints
- [x] Demo story tests 1–5 pass; `make check` prints PASS/FAIL per story
- [x] OpenAPI spec clean; every endpoint described

## Stage 3b — Social API (Session A)
- [x] social app: posts, post_media (Supabase Storage uploads, size/type checks, server-side resize variants), reactions, replies, follows, update_views
- [x] Pulse endpoint: chronological last 7 days, visibility rules, mixes build logs + nearby matching roles + system activity, cursor pagination, "caught up" marker
- [x] Daily Drop: `manage.py build_daily_drops` (08:00 IST job) using match_results; 3 per member; swipe outcomes logged as events
- [x] Today strip endpoint (authors with posts or roles in the last 24h among connections, follows, organisation) (to be replaced by the Live wire endpoint below)
- [x] Live wire endpoint: up to 12 updates from the last 24h (shipped, hiring, needs, joined, closed a circuit), ranked by relevance to the viewer, each with image, verb, one-line reason and one action
- [x] Daily Drop returns match strength as a label (Strong ≥ 0.75, Good ≥ 0.55) and excludes candidates below 0.55; API never exposes raw low scores
- [x] messaging app: conversations (request | active | blocked), messages, Realtime channel per conversation with RLS; under-18 rules enforced server-side
- [x] Reports on posts, replies, messages and profiles; hide/remove from Django admin; audit-logged
- [x] Rate limits on posting, replies, messages and connection requests
- [x] Seed data: build logs for the demo personas using screenshot-style images of their (fictional) projects rendered from simple SVG/HTML mockups — no stock photos, no AI-generated people; plus follows and conversations
- [x] Tests: visibility (everyone / connections / org), minors rules, IDOR on posts/messages, no public counts in API responses to non-authors

## Stage 4 — Frontends (Session B; follow DESIGN.md exactly)
- [ ] DESIGN.md is final (lifestyle redesign); do not change it without my OK
- [ ] packages/ui components listed in DESIGN.md §6, with dark and light themes
- [ ] packages/api-client generated from the backend OpenAPI spec (script; mock spec until Stage 3 lands)
- [ ] apps/landing: home + /students, /founders, /mentors, /investors, /partners per DESIGN.md §4 "Landing site"; role-aware CTAs (`/join?role=…&src=…`); waitlist form; SEO + OG per page; footer (privacy, terms, contact)
- [ ] App `/join` route reads role, org, invite code and src; onboarding skips the steps they answer; src saved on the member
- [ ] `useFeatures()` hook from `/api/config`; tabs, entry points and routes for an off flag are removed (DESIGN.md §3), and their URLs show the 404 screen
- [ ] Data layer: one hook per screen/action in apps/app/src/data; ESLint rule forbids API client, Supabase or fetch imports outside src/data
- [ ] Mock mode: `pnpm dev:mock` with MSW handlers generated from contract fixtures and scenario switcher (empty, loading, error, slow 3G, under-18, partner, investor, features off)
- [ ] apps/app shell: Supabase sign-in (Google + OTP), auth callback, navigation per DESIGN.md §3 (Home · Discover · Circuits · Inbox · Profile; create in top bar), environment banner, persona switcher (dev/demo)
- [ ] Sign-up and onboarding per DESIGN.md §4 "Sign-up and onboarding": one thing per screen (steps 1–14), resumable, inference before asking, under-18 defaults, measured time-to-first-drop < 2 min (Playwright test with timing)
- [ ] Home: Live wire + Update view, reason-first Daily Drop stack, Pulse feed with build logs and "caught up" end
- [ ] Build log composer and post view (media pager, reactions, replies, report)
- [ ] Discover: People, Startups, Jobs (+ job page, apply), Map
- [ ] Circuits: ring cards, live status, signature closing animation
- [ ] Inbox: Chats + Requests, realtime messages, report/block
- [ ] Profile: header, needs/offers, highlights, build log grid, circuits, about; connect/follow/message/intro via mutual
- [ ] Founder applicants view, my applications, partner dashboard
- [ ] Every screen: loading, empty, error states; works at 375px and 1280px
- [ ] TabPager: swipe between tabs per DESIGN.md §3 gesture rules (Playwright touch tests: swipe commits, vertical scroll wins, no conflict with Live wire, Daily Drop, media pager, map)
- [ ] ThemeProvider + AccentPicker: accent applied before first paint, all six accents pass contrast checks in both themes
- [ ] Playwright tests for the five demo stories at both widths; axe checks

## Stage 4b — Invite-only beta (F18)
- [ ] invite_codes, beta_access, waitlist models; Django admin to create codes, approve waitlist, revoke access
- [ ] Access gate on every member endpoint when BETA_MODE is on (except onboarding, waitlist and redeem-code); tests prove a non-beta member gets 403 everywhere else
- [ ] App: "Enter invite code" + waitlist screen after sign-in; landing: waitlist form (rate-limited, no account needed)
- [ ] Invite emails (Resend) with a one-tap link containing the code
- [ ] Each beta member can invite 3 others (codes tied to the inviter, logged)

## Stage 4c — Matching ML pipeline (backend)
- [ ] Ranker interface: RuleRanker (v1) + ModelRanker (LightGBM LambdaRank); RuleRanker fallback on any error
- [ ] feature_snapshots logged for every candidate shown; banned features test (no college, gender or proxies)
- [ ] `simulate_network` (synthetic members, hidden preferences, simulated responses)
- [ ] `build_training_set` (graded labels from events) and `train_ranker` (offline NDCG@10, eval-set agreement, fairness check by college tier and bridge vs local)
- [ ] model_versions + versioned model files in private Supabase Storage; promotion in Django admin only when it beats RuleRanker and passes fairness
- [ ] Shadow mode and A/B split setting; acceptance-rate comparison report per arm
- [ ] Tests: pipeline runs end to end on simulated data; a simulation-only model can never be promoted to active in production

## Stage 4d — Promoted startups and roles (F19)
- [ ] apps/promotions: campaigns, campaign_stats_daily, hidden_promotions; Django admin to create, pause and end campaigns and record price and invoice reference
- [ ] Serving endpoint per slot (pulse, discover_startups, jobs) applying targeting, dates, caps, frequency rules and hidden campaigns; under-18 only verified-startup roles
- [ ] Server-side aggregate impression/tap counting; applications attributed to a campaign when started from a promoted item
- [ ] "Why am I seeing this?" text generated from targeting only
- [ ] Founder endpoint: promotion results (daily aggregates)
- [ ] Tests: ranker/Daily Drop/Live wire/search/applicant outputs identical with and without campaigns; caps; no promotion in banned surfaces; under-18 rules; no per-member tracking stored
- [ ] Frontend: Promoted label and "…" menu on cards, slot rendering in Pulse/Discover/Jobs, founder "Promotion results" card

## Stage 4e — Payments with Razorpay (F20)
- [ ] [YOU] Razorpay account; test keys + test webhook secret into .env / staging secrets; live activation (KYC) started; accountant confirms GST invoice format
- [ ] promotion_packages, orders, payments, refunds, webhook_events models; packages managed in Django admin
- [ ] POST create order (server computes amount from package; only founders of claimed + verified startups)
- [ ] POST verify checkout (payment signature, constant-time compare) → order shows "processing" until webhook
- [ ] Webhook endpoint: raw-body signature check with webhook secret, event-id idempotency, handles payment.captured, payment.failed, refund.processed; activates the campaign in one transaction
- [ ] `reconcile_payments` job (10 min) + 24h expiry; refunds from Django admin; receipt email
- [ ] Startup check: live keys refused outside production
- [ ] CSP allows Razorpay Checkout only on the payment screen
- [ ] Frontend: package picker on the startup page, Checkout, "processing" → "Your promotion is live" states, payment history
- [ ] Tests: PRODUCTION.md §14 rows 7–9, 18 (payments), plus amount tampering, wrong-startup purchase, duplicate webhooks, out-of-order events, refund flow, all in Razorpay test mode

## Stage 4f — Investor mode (F21)
- [ ] sectors list (seeded), startup fields (sector, stage, team_size, open_to_investors default false, fundraising_status), investor_profiles, investor_picks
- [ ] Investor onboarding endpoints (focus, stages, cheque band, verification link) + Django admin review for verification level 3
- [ ] `build_investor_picks` (08:00 IST, frozen per day, no repeats within 30 days, promotions excluded); investor-filtered Pulse and Live wire endpoints
- [ ] Founder controls: "Open to investor conversations" toggle and fundraising status on the startup page
- [ ] Intro requests from investors require founder consent; unverified investors get 403 on intro requests
- [ ] Tests: startups with open_to_investors=false never appear to investors anywhere; picks stable within a day; minors' posts never in investor feeds; no promotions in investor feeds
- [ ] Frontend: investor onboarding steps 8i–11i, Investor home (Today's picks, filtered Pulse and Live wire), Profile → Investing, founder toggle
- [ ] Seed: 2 demo investors with focus that matches 5–10 seeded startups open to investors

## Stage 4g — Partner mode (F22)
- [ ] Organisation kinds, verification flow (domain OTP or website + super admin review), join requests to existing orgs
- [ ] Cohorts with invite → accept → leave; cohort_startups and cohort_members
- [ ] Calls + applications (partner-defined questions, max 5) + review pipeline (shortlist/accept/decline with notifications)
- [ ] Events + RSVPs (capacity, waitlist, cancel, calendar file)
- [ ] Announcements (1/day per org, members and followers only, under-18 push hours)
- [ ] Partner home endpoint (needs attention, cohort health aggregates, open calls, events, filtered Pulse); Organisation page endpoint
- [ ] Partner items in Pulse for matching members, capped 1 per 10, labelled, never paid
- [ ] Tests: unverified partner has no admin powers; partners never see other orgs' members or non-consenting startups; counts under 5 hidden; announcement and Pulse caps; minors' rules
- [ ] Frontend: partner onboarding 8p–11p, Partner home, `New` sheet, Organisation page, call and event cards/pages, application form, review pipeline, RSVP
- [ ] Seed: one college and one incubator with a cohort, an open call, an upcoming demo day

## Stage 5 — Deploy staging + demo (Sessions A + B together)
- [ ] Backend image builds on ARM64 + x86_64; deployed to Cloud Run (staging, demo); jobs + scheduler created
- [ ] Vercel: landing, app-staging, app-demo deployed with §2a variables
- [ ] Supabase redirect URLs + Google OAuth origins set for staging and demo
- [ ] `make smoke URL=...`: landing loads, app sign-in page loads, CORS preflight passes, one authed read, one write, test email
- [ ] `make reset-demo ENV=demo` + nightly reset job
- [ ] Smoke passes on staging and demo

## Stage 6 — Product basics
- [ ] Account settings: edit profile, notification preferences, privacy, export, delete
- [ ] Appearance: theme, personal accent (six options, validated server-side), swipe between tabs toggle; GET/PATCH endpoint; accent offered once at the end of onboarding
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
- [ ] Every row in PRODUCTION.md §14 has a passing automated test or a dated manual check in RUNBOOK.md
- [ ] PWA for apps/app: manifest, icons, offline shell, update prompt, install prompt (incl. iOS)
- [ ] Lighthouse ≥ 90 mobile (landing, app Home); bundle budget; lazy-load map and charts
- [ ] Load test staging (~1,000 concurrent users); fix top bottlenecks
- [ ] Privacy-friendly analytics for the pilot funnel

## Stage 11 — Cleanup (alone, last)
- [ ] Remove dead code, unused deps, debug code, stray TODOs; consistent patterns
- [ ] README: setup in under 10 minutes on Mac, Linux (Arch/Omarchy) and WSL, using only COMMANDS.md targets
- [ ] Every COMMANDS.md target works from a fresh clone; no command missing from it
- [ ] RUNBOOK.md: deploy, rollback, restore, rotate secrets, outage, data request, takedown
- [ ] All tests and smoke green

## Stage 12 — Go live
- [ ] [YOU] Buy domain; follow PRODUCTION.md §2a switch checklist
- [ ] [YOU] Fresh-eyes test with 5 real students + 1 founder; fix what confused them
- [ ] Production deploy + smoke
- [ ] Production flags set per PRODUCTION.md §2b; switch-ons dated in PROGRESS.md
- [ ] [YOU] Pilot college onboarded
