# Circuit — engineering guide

Read this every session. It says WHAT Circuit is and HOW we build it.
- PRODUCTION.md: how it runs in production (infra, security, ops). Wins on infra questions.
- LAUNCH.md: the staged checklist. Do the stage(s) named in the session prompt only.
- BACKLOG.md: work after launch. Never build from it unless it's pulled into a stage.
- PROGRESS.md: current status. Create it in Stage 0; update it at the end of every session.
- DESIGN.md: visual and writing rules. Create it in Stage 4 before building screens.

## Product
Circuit is a startup ecosystem platform for India, starting with one pilot city and one
partner college.

Differentiator: we match people on what they NEED and what they can OFFER, not on sector
or job titles. That enables cross-sector "bridge" matches, warm intros and 3-person
exchange circuits, plus a map of who is hiring nearby.

Users:
- Students (often tier 2/3 colleges): find nearby hiring startups and jobs, matched on
  skills and proof of work, not college name.
- Founders, mentors, investors: matches with reasons, warm intros, exchange circuits.
- Partner admins (colleges, incubators): dashboard of their own organisation's gaps.
- Super admins (Circuit team, 2–3 people): verification, moderation, data review.

## Features (current scope)
F1  Smart onboarding: one question per screen (DESIGN.md §4 "Sign-up and onboarding");
    paste a bio → LLM suggests needs, offers, capabilities, traits from OUR FIXED LISTS
    ONLY → user confirms with chips. Manual pickers if the LLM fails. Resumable
    (onboarding state saved per step); nothing asked that can be inferred.
F2  Startup map: filters (hiring, capability, distance), pins by hiring status, popup with
    match %, open roles, "I'm interested".
F3  Unclaimed startup profiles + claim flow (verify via company email domain). Shows
    student views/interest to motivate claiming. Claimed data is never overwritten.
F4  Matches with one-line reasons; "Bridge match" badge for cross-sector matches.
F5  Warm intros via the best mutual connection (1–2 hops); weekly capacity limits.
F6  Exchange circuits: weekly round + super-admin "Run round now". 3-person loops,
    weakest-link score, CP-SAT selection, 72h consent, live status, mark done, rating.
F7  Verification levels 1–3 as badges (1 email, 2 work email/LinkedIn, 3 admin-verified).
F8  Partner dashboard: gap chart + heatmap, network stats, local vs bridge acceptance.
    Scoped to the partner's organisation; counts under 5 hidden.
F9  Demo mode (dev and demo environments only): persona switcher + `make reset-demo`.
F10 Logging + events: one JSON log line per request; append-only events table.
F11 Jobs and applications: list, filters, job page with skill match, one-click apply,
    statuses, founder applicant view ranked by skill match.
F12 Account basics: sign-up/onboarding, settings, export, delete, notifications
    (in-app + email), report/block, help/FAQ, legal pages. Appearance settings: theme
    (system/dark/light), personal accent (one of six, DESIGN.md §5), swipe between tabs
    on/off; stored on the member so they follow across devices.
F13 Admin: Django admin for super admins (verify members, moderate reports, review
    crawled startups, takedowns, run circuit round, metrics), every action audit-logged.
F14 Landing site: separate public marketing site (own domain), never calls private
    APIs except the public waitlist endpoint. One home page plus five audience pages:
    /students, /founders, /mentors, /investors, /partners — each with its own one-line
    pitch, proof and call to action. Every call to action links into the app with the
    role pre-set (`APP_URL/join?role=student&src=landing-students`); partner and member
    invite links carry role + organisation + invite code. When a link carries a role,
    onboarding skips the role step. `src` is stored on the member for per-audience
    funnel analytics (no third-party trackers).
F15 Build logs + Pulse: members post up to 4 images + 500 chars + up to 3 capability
    tags + optional link, visibility Everyone / Connections / My organisation. Pulse
    feed (chronological, last 7 days, ends with "You're caught up") mixes build logs,
    nearby matching roles and system activity. Reactions Helpful / Intro me / Let's
    talk (no public counts); one-level replies. Every post reportable; moderated in
    Django admin.
F16 Daily Drop + Live wire: 3 matches per day at 08:00 local time as a swipeable
    stack (reason-first cards, match strength in words); Live wire of the most relevant
    updates (shipped, hiring, needs, joined, closed a circuit) from the last 24h.
F17 Connections, follows and Inbox: connect (with note) to people, follow startups;
    1-to-1 messages via Supabase Realtime; Requests folder for non-connections;
    under-18 students receive no Requests from strangers.
F18 Invite-only beta: an access gate. A signed-in user without beta access sees a
    waitlist screen, not the app. Access comes from an invite code (single-use or
    capped multi-use, optional expiry, optional organisation), an email allowlist, or
    a super admin approving a waitlist entry. Landing site has a waitlist form.
    BETA_MODE setting (on in production until public launch).
F19 Promoted startups and roles (revenue): startups pay to promote their profile, a
    role or a build log in clearly labelled "Promoted" slots only. Promotion NEVER
    changes matching, Daily Drop, Live wire, circuits, search ranking or applicant
    ranking. Targeting by city, radius and capability only (never personal data or
    protected traits). Under-18 students only see promoted roles/internships from
    verified startups. Members can hide a promotion and see "Why am I seeing this?".
    Founders of claimed, verified startups buy promotion packages in the app and pay
    with Razorpay; super admins can also create campaigns in Django admin. Startups see
    impressions, taps and applications from their campaign (aggregates only).
F20 Payments (Razorpay): fixed promotion packages priced in ₹ (set by super admins).
    Flow: backend creates a Razorpay Order → app opens Razorpay Checkout → backend
    verifies the payment signature → the campaign activates ONLY when the verified
    `payment.captured` webhook arrives (webhook is the source of truth). Refunds by
    super admins from Django admin. Card/UPI data never touches our servers.
F21 Investor mode: investor onboarding branch (focus sectors, stages, optional cheque
    range, verification link; DESIGN.md §4). Investor Home: 3 "Today's picks" per day
    at 08:00 IST + Pulse and Live wire filtered to startups in their focus that are
    open to investors. Founders opt in per startup ("Open to investor conversations",
    off by default) and control fundraising status. Investor intros go to the founder
    for consent; unverified investors browse but can't request intros. Circuit only
    makes introductions: no deal-making, no investment handling, no success fees.
F22 Partner mode (colleges, incubators, accelerators, coworking spaces, government
    and corporate programmes): partner onboarding branch with organisation
    verification; public Organisation page; Cohorts (startups and members who accept
    an invite to join); Calls (applications to a programme, internship drive or
    challenge, with a simple review pipeline); Events (demo days, meetups, office
    hours with RSVP); Announcements to their own members (max 1 per day, labelled
    "From <org>" in Pulse); Partner home with cohort health, gap map, open calls and
    upcoming events. Partners only see aggregates plus members/startups who opted in.
DESIGN.md defines every screen, component, motion and healthy-habit rule for these.

## Repo layout (one monorepo)
```
backend/                 Django project (Python, uv)
  circuit/               settings (per ENV), urls, asgi/wsgi
  apps/                  accounts, organisations, startups, jobs, matching, intros,
                         circuits, dashboard, notifications, moderation, events,
                         social (posts, reactions, replies, follows, daily drop),
                         messaging
  core/                  auth (Supabase JWT), permissions, cache/, graph/, embeddings/,
                         llm/, logging, errors, pagination
  tests/                 unit, api, demo (story tests), eval (matching pairs)
apps/landing/            Next.js marketing site (static)
apps/app/                Next.js product app (PWA)
packages/ui/             shared design components and tokens
packages/api-client/     TypeScript client generated from the backend OpenAPI spec
docker/                  Dockerfiles (backend, postgres with PostGIS + pgvector)
Makefile                 every command you run (COMMANDS.md explains each one)
docs: CLAUDE.md PRODUCTION.md LAUNCH.md BACKLOG.md PROGRESS.md DESIGN.md RUNBOOK.md
      COMMANDS.md
```
JavaScript workspace: pnpm workspaces (no other monorepo tool).

## Stack
Backend
- Python 3.12, uv; Django 5 + Django Ninja (typed endpoints, OpenAPI at /api/openapi.json)
- PostgreSQL 16 + PostGIS (GeoDjango) + pgvector (pgvector-python Django support); psycopg 3
- Django migrations (the only way schema changes)
- Redis client behind core/cache (cache + rate limits); fakeredis in tests
- fastembed (BAAI/bge-small-en-v1.5, 384 dims) behind an EmbeddingProvider, plus a
  deterministic fake provider for tests
- LLM behind core/llm with a provider setting (LLM_PROVIDER = gemini | groq | anthropic),
  used for onboarding extraction (later the crawler). Output is always validated against
  a strict schema; invalid output falls back to manual pickers. Free tiers allowed in
  dev, demo and staging only; production uses a paid tier whose terms exclude training
  on our data.
- networkx (cycles), OR-Tools CP-SAT (circuit selection)
- structlog JSON logs; pytest + pytest-django
- Background work = Django management commands, run as Cloud Run Jobs in staging/prod

Frontend
- Next.js (App Router) + TypeScript + Tailwind in both apps; shared packages/ui
- apps/landing: statically rendered, SEO metadata, no login
- apps/app: client-rendered product screens, PWA, MapLibre GL (OpenStreetMap tiles),
  Recharts, TanStack Query + packages/api-client (no hand-written fetch calls),
  Supabase JS only for auth, storage uploads and realtime

Approved supporting libraries (no need to ask):
- Backend: lightgbm, scikit-learn, numpy, pandas (matching ML only),
  google-genai (Gemini), groq, anthropic (one active via LLM_PROVIDER),
  PyJWT[crypto] (JWKS), django-otp (admin 2FA), redis, fakeredis (tests),
  httpx, sentry-sdk, resend, razorpay (official SDK), django-environ or
  pydantic-settings (pick one), ruff, mypy
- Frontend: @supabase/supabase-js, @tanstack/react-query, @tanstack/react-virtual,
  openapi-typescript, motion (animations), lucide-react (icons), geist (font),
  maplibre-gl, recharts, serwist (PWA, Stage 10), msw (mock mode), @playwright/test,
  @axe-core/playwright,
  @sentry/nextjs, eslint, prettier

Infra: PRODUCTION.md. Four environments (dev, demo, staging, production) via ENV.
Local dev: docker compose (Postgres with PostGIS + pgvector, Redis). Every image must
work on ARM64 and x86_64. No hard-coded domains: all URLs come from config
(PRODUCTION.md §2a).

Graph queries (warm paths, circuits, 2nd-degree network) use recursive SQL + networkx
behind core/graph. Neo4j is NOT in scope (trigger in BACKLOG.md).

## Architecture rules
- Postgres is the only source of truth. Redis is disposable: if down, read from
  Postgres and log a warning.
- Ninja routers are thin; business logic lives in each app's services.py. React
  components stay thin; data logic lives in hooks.
- Heavy work (matching, circuit rounds, bulk LLM, crawling) never runs in a request;
  it runs as management commands/jobs and users read precomputed results.
- Every external call has a timeout, retries with backoff and a graceful fallback.
- Jobs and important endpoints are idempotent.
- One way to do each thing: one error format, one pagination style, one logging setup.

## Feature flags (ship code dark, switch features on when the pilot is ready)
Code for every feature can be merged and deployed; flags decide what members see.
- Core is never flagged: onboarding, beta gate, profiles, matches, intros, map, jobs and
  applications, connections, Inbox, notifications, settings, partner dashboard (F8),
  Django admin.
- Flags (one name each, defined once in core/flags.py):
  | Flag | Covers | Depends on |
  |---|---|---|
  | `pulse` | build logs, Pulse feed, reactions, replies, Live wire (F15, F16 Live wire) | – |
  | `daily_drop` | Daily Drop (F16) | – |
  | `circuits` | exchange circuits, rounds, Circuits tab (F6) | – |
  | `investor_mode` | investor onboarding branch, investor home, picks, founder opt-in (F21) | – |
  | `partner_mode` | cohorts, calls, events, announcements, org page (F22) | – |
  | `promotions` | promoted slots, campaigns, stats (F19) | `pulse` |
  | `payments` | packages, orders, Razorpay checkout, webhooks (F20) | `promotions` |
- Audience per flag: `off`, `testers` (members with is_tester = true, set by a super
  admin) or `everyone`. Defaults come from the `FEATURES` env variable per environment
  (PRODUCTION.md §2b); super admins override them in Django admin (audit-logged).
  Overrides are cached in Redis for 60s; if Redis is down, read Postgres.
- One check everywhere: `flags.enabled("circuits", member)` in services,
  `@require_flag("circuits")` on Ninja routers, `flags.enabled("circuits")` (no member
  = audience everyone) in jobs.
- When a flag is off for a member: its endpoints return 404 with error code
  `feature_off`; its items are left out of Pulse, Live wire, search and notifications;
  its jobs log `skipped: flag off` and exit 0; nothing is deleted.
- Switching off never breaks what is in flight: active circuits finish their round,
  pending intros and messages stay. `promotions` and `payments` can't be switched off
  in admin while a paid campaign is active or an order is `created` (pause or refund
  first); webhooks are always processed, even with `payments` off.
- Startup validation: a flag on without its dependency → the app refuses to start;
  `payments` on in production requires live Razorpay keys.
- `GET /api/config` (public, cached 60s) returns `{env, beta_mode, features: {name:
  bool}}` for the current member (or anonymous). The app reads it through the
  `useFeatures()` hook; screens hide what is off (DESIGN.md §3). Mock mode has a
  "features off" scenario.
- Tests: every flag has an on and an off test (endpoint 404, feed excludes, job
  no-ops, `testers` audience works); matching and applicant ranking outputs are
  identical whatever the flags.
- `manage.py flags` lists flags and their state; `manage.py flags set circuits
  testers` changes one (logged like an admin change). Make targets in COMMANDS.md.

## Auth and access
- Users sign in with Supabase Auth (Google first, email OTP backup). We never store
  user passwords.
- A Ninja auth class verifies Supabase JWTs via JWKS (signature, expiry, audience,
  pinned algorithm) and loads the Member by auth_user_id.
- members is the source of truth for role, verification_level, organisation_id.
- Roles: student, founder, mentor, investor, partner_admin, super_admin.
- Permission helpers (require_role, require_level, org scoping) on every endpoint; IDOR tests.
- RLS enabled on every table (deny by default); the app's DB role is the only writer;
  the Supabase service role key exists only in the backend.
- Django admin: separate staff login for super admins only (Django staff users with
  mandatory TOTP 2FA via django-otp), served at a non-obvious path, never in demo.
  This is the only place passwords exist, and they are Django-hashed.
- DEMO_AUTH issues persona tokens in dev and demo only. The app refuses to start with
  DEMO_AUTH=true when ENV is staging or production.

## Data model (Postgres)
- members: id, auth_user_id (unique), role, display_name, bio, location (point), city,
  college, organisation_id (nullable), verification_level, open_intro_slots,
  circuits_opt_in, is_minor, is_tester, profile_visibility, visible_to_org,
  appearance (json: theme, accent, swipe_tabs; validated against the allowed values),
  onboarding (json: current_step, completed_at, saved answers), signup_source (src),
  created_at, updated_at
- organisations: id, name, kind (college | incubator | accelerator | coworking |
  government_program | corporate_program), city, website, logo, about, email_domains,
  join_code, verified_at, created_by. A member belongs to at most one organisation. Super admins
  create organisations and appoint the first partner_admin. Members join via invite
  code/link, or automatically after verifying an email on one of the org's domains.
  Partner admins can remove members; members can leave. Partner admins see aggregates
  over their own members only, plus members with visible_to_org = true.
- startups: id, name, website_domain (unique), description, sector, stage, address,
  location, hiring, tech_stack (json), claimed_by (member), source (seed | crawler | user),
  confidence, view_count, created_at
- startup_members; jobs; job_capabilities; applications (unique per student per job)
- cohorts (organisation, name, year, kind: incubation | accelerator | batch | class),
  cohort_startups / cohort_members (invited_at, accepted_at; membership only after
  acceptance)
- calls (organisation, kind: programme | internship_drive | challenge, title, about,
  eligibility, sectors, deadline, status), call_applications (call, applicant member or
  startup, answers json, status: submitted | shortlisted | accepted | declined)
- events (organisation, title, kind: demo_day | meetup | office_hours | workshop,
  starts_at, ends_at, venue or online link, capacity, visibility: public | org),
  rsvps (event, member, status: going | waitlist | cancelled)
- announcements (organisation, author, body, link, created_at; max 1/day per org)
- sectors (fixed list, ~25, e.g. fintech, healthtech, agritech, edtech, climate,
  deeptech, D2C, SaaS, mobility, logistics); startups gain sector (FK), stage (idea |
  pre_seed | seed | series_a_plus), team_size, open_to_investors (bool, default false),
  fundraising_status (not_shared | not_raising | raising | closing)
- investor_profiles (member, sectors, stages, cheque_band nullable, cities,
  verification_link, verified_at); investor_picks (investor, date, startups, outcome
  per pick: requested | passed | ignored)
- capabilities (40–80), traits (20–30); needs; offers (embedding vector(384))
- member_traits, startup_traits, member_skills
- connections; intro_requests; match_results (score, components json, reason, is_bridge)
- circuits; circuit_legs (giver, receiver, capability, consent, fulfilled, rating)
- notifications; reports; blocks; audit_log; consents (policy_version, accepted_at)
- posts (author, body, link, visibility, capability tags, status: visible | hidden |
  removed), post_media (storage path, width, height, alt_text, order),
  reactions (post, member, kind; unique per member+post+kind), replies (post, author,
  body, parent nullable one level)
- follows (member → startup); connections (above) for people; daily_drops (member,
  date, candidate list); update_views (viewer, update, date)
- conversations (two members, status: request | active | blocked), messages
  (conversation, sender, body, image, created_at, read_at)
- invite_codes (code, max_uses, uses, expires_at, organisation nullable, created_by),
  beta_access (member, source: code | allowlist | approved, granted_at), waitlist
  (email, role, city, college, note, status, created_at)
- campaigns (startup, kind: profile | role | build_log, target id, cities, radius_km,
  capabilities, starts_at, ends_at, daily_cap, total_impressions_cap, status: draft |
  active | paused | ended, price_inr, invoice_ref, created_by), campaign_stats_daily
  (campaign, date, impressions, taps, applications; aggregate counts only),
  hidden_promotions (member, campaign)
- promotion_packages (name, kind, duration_days, radius_km, impressions_cap, price_inr,
  gst_rate, active), orders (founder, startup, package, razorpay_order_id unique,
  amount_paise, currency INR, status: created | paid | failed | refunded | expired,
  campaign, receipt_no, created_at), payments (order, razorpay_payment_id unique,
  status, method, captured_at), refunds (payment, razorpay_refund_id, amount_paise,
  reason, created_by), webhook_events (provider, event_id unique, type, received_at,
  processed_at, result) — money is always integer paise, never floats
- feature_snapshots, model_versions (version, trained_at, metrics json, status:
  candidate | shadow | ab | active | retired, file path)
- feature_flags (name unique, audience: off | testers | everyone, note, updated_by,
  updated_at); every change audit-logged
- events (append-only: actor, type, target_type, target_id, payload, created_at)
GIST indexes on locations, HNSW on embeddings, indexes on every foreign key.

## Matching (v1, rule-based)
- Candidates: local (same city, shared traits, 1–2 hop connections) + bridge (whole
  pool, need-to-offer on capability + embedding similarity, ignoring sector).
- score = w1*complementarity + w2*affinity + w3*trust_path + w4*timing - w5*load_penalty
  Complementarity both directions. Weights in settings. Pure, unit-tested functions.
- Ranking: diversity, capacity caps, ~25% bridge share. Students: distance is a hard filter.
- Precomputed by `manage.py compute_matches` into match_results, cached in Redis.
- Eval set (tests/eval/pairs.json) + `manage.py eval_matching`; scoring changes must not
  lower agreement.

## Partner rules (F22)
- A partner_admin gets admin powers only after a super admin verifies the
  organisation (official email domain or website + a human check).
- Startups and members join a cohort only by accepting an invite; leaving is one tap.
- Partners see their cohort's and members' data as aggregates (counts under 5 hidden),
  plus individual profiles only for members/startups with visible_to_org or cohort
  membership. Never other organisations' members.
- Announcements reach only that organisation's members and followers; rate-limited to
  1/day; never sent as push to under-18 members outside 09:00–19:00 IST.
- Calls and events from verified partners can appear in Pulse for matching members
  (by sector/capability/city), labelled with the organisation; this is not promotion
  and is free, but is capped at 1 partner item per 10 Pulse items.

## Investor picks (F21, rule-based v1)
- Candidates: startups with open_to_investors = true whose sector ∈ investor sectors and
  stage ∈ investor stages; city/radius from investor cities (or all if none).
- Score = thesis fit (sector, stage, geography) + momentum (build logs in the last 30
  days, roles posted, verified founders, profile completeness) − already shown in the
  last 30 days. Promotions never affect picks.
- `manage.py build_investor_picks` runs at 08:00 IST with the Daily Drop; picks are
  frozen for the day so the feed stays stable. Outcomes feed the ML training set later.

## Matching ML (learned ranker, behind apps/matching/ranker)
- A Ranker interface with two implementations: RuleRanker (the v1 formula, always the
  fallback) and ModelRanker (LightGBM LambdaRank learning-to-rank model).
- Features are logged for every candidate shown (feature_snapshots: viewer, candidate,
  surface, model_version, features json, position, shown_at), so training data is the
  exact input the model saw.
- Features: complementarity both directions, embedding similarity, shared capabilities
  and traits, distance, mutual connections and best path strength, candidate activity
  recency, capacity left, verification levels, role pair, is_bridge, candidate's past
  response rate. NEVER use college name/tier, gender, religion, caste, language or any
  proxy for them — matching on skills over pedigree is the product.
- Labels (graded): 0 skipped/ignored, 1 intro requested, 2 intro accepted, 3 met and
  rated helpful. Built by `manage.py build_training_set` from events.
- Bootstrapping before real data: `manage.py simulate_network` creates synthetic members
  with hidden preferences and simulated responses; plus the hand-labelled eval set.
  A model trained only on simulation is NEVER served to real users; it exists to test
  the pipeline end to end.
- `manage.py train_ranker` (Cloud Run Job, weekly): trains, evaluates offline (NDCG@10,
  acceptance-rate proxy, eval-set agreement, fairness check: score distributions by
  college tier and by bridge vs local must not diverge beyond a set threshold), writes
  a versioned model file + metrics to Supabase Storage (private), records it in
  model_versions. Promotion to "active" requires beating RuleRanker on all metrics and
  passing fairness, and is done by a super admin in Django admin.
- Serving: shadow mode first (ModelRanker scores logged alongside RuleRanker, users
  see RuleRanker), then an A/B split via a setting (e.g. 20% of members) with
  acceptance compared per arm, then full rollout. Any model error → RuleRanker.
- Inference runs in compute_matches (batch), never per request.

## Privacy and safety
- Never log or send to analytics: names, emails, phones, tokens.
- Under-18 students: hidden profile by default, no messages from strangers.
- Aggregates hide counts under 5; heatmaps use coarse cells.
- Super-admin actions audit-logged.
- Crawling (later): company data only, robots.txt respected, takedown form.

## Seed data and demo stories
Configurable city centre (lat/lng in env). ~150 startups, ~300 members (mostly
students), realistic Indian names, places, roles and stipends. `manage.py reset_demo`
is idempotent. It must contain these five stories:
1. A biotech startup needing marketing, matched to a deep-tech marketer as a Bridge
   match (shared traits: long sales cycle, technical buyers).
2. A circuit: Asha needs marketing, Priya needs fundraising, Arjun needs hiring.
3. A tier-3-college student matched on skills to a nearby hiring startup, applies to its
   internship, and is the founder's top-ranked applicant.
4. A warm intro path through a respected mentor.
5. A visible regulatory-help gap on the partner dashboard.

## Testing
- Unit (scoring, reasons, circuits on known graphs, auth, logging), API (every endpoint:
  one success + at least one failure, IDOR, rate limits, events), demo story tests
  (tests/demo/), Playwright end-to-end for the app at 375px and 1280px, axe checks.
- Tests use a fresh seeded test database, the fake embedding provider, fakeredis and a
  mocked LLM. No live network calls in tests.
- `make check` runs everything and prints PASS/FAIL per demo story.
- `make smoke URL=...` checks a deployed environment. Never deploy on red.

## Frontend architecture (so the UI can change freely)
Three layers in apps/app, and only the middle one talks to the API:
1. `packages/api-client` — generated from openapi.json. Never edited by hand.
2. `apps/app/src/data/` — one TanStack Query hook per screen or action
   (`useHome`, `useDailyDrop`, `useLiveWire`, `usePulse`, `useJob`, `useApply`,
   `useCircuit`, `useInbox`, `useConversation`, `useProfile`, `useAppearance`, …).
   Hooks own fetching, caching, optimistic updates, Realtime subscriptions and error
   mapping, and return plain, UI-ready objects. This is the stable contract.
3. Screens and components (`apps/app/src/app/**`, `packages/ui`) — only call hooks.
   They never import the API client, Supabase or fetch directly (an ESLint rule
   enforces this). Redesigning a screen never requires touching layers 1–2.
- Mock mode: `pnpm dev:mock` runs the app against Mock Service Worker handlers generated
  from the contract-test fixtures, with switchable scenarios (empty, loading, error,
  slow 3G, under-18, partner, investor, features off), so UI work needs no backend or login.
- `/design` (dev only) shows every packages/ui component and every screen state.
- FRONTEND_HANDOFF.md lists, per screen, the hook to use and what it returns, as well
  as the underlying endpoints.

## API contract rules (backend-first build)
- Every endpoint is designed from the screen it serves: read the DESIGN.md section for
  that screen and return everything the screen displays in one call (no follow-up
  requests per card).
- Privacy-sensitive fields (public counts, minors' data, raw low scores) are never in
  responses to people who shouldn't see them; tests prove it.
- FRONTEND_HANDOFF.md lists, per screen: endpoints, request/response shapes, error
  cases, Realtime channels, rate limits. Contract tests (tests/contract/) call each
  endpoint as the handoff describes and assert the shape. Changing an endpoint means
  updating the handoff, the contract test and openapi.json in the same commit.

## Promotion rules (F19)
- Promoted items live in their own slots and are served by apps/promotions, never by
  the ranker; tests prove matching, Daily Drop, Live wire, search and applicant
  ranking outputs are identical with and without active campaigns.
- Every promoted item is labelled "Promoted" (DESIGN.md §4) and links to "Why am I
  seeing this?" (city/capability targeting, never personal data).
- Frequency caps: max 1 promoted item per 8 Pulse items, max 1 per Discover/Jobs
  screen, never the first item, never the same campaign twice in a day per member.
- Impressions are counted server-side in aggregate; no per-member ad tracking or
  third-party ad scripts.

## Payment rules (F20)
- Keys: Razorpay TEST keys in dev, demo and staging; LIVE keys only in production
  (Secret Manager). The app refuses to start with live keys outside production.
- Payment signature: HMAC-SHA256 of `order_id|payment_id` with the API key secret.
  Webhook signature: HMAC-SHA256 of the RAW request body with the webhook secret.
  Never mix them; compare in constant time.
- Webhooks are idempotent (store `x-razorpay-event-id`; duplicates are no-ops), can
  arrive out of order or late, and are the only thing that marks an order paid.
- `reconcile_payments` job (every 10 min) fetches orders stuck in `created` > 15 min
  from Razorpay and fixes their status; orders unpaid after 24h expire.
- Amounts are computed server-side from the package; the client never sends a price.
- Every money state change writes an event and an audit_log entry.

## How to work with me
- I'm learning. Explain what you built and why in plain language.
- Work only on the LAUNCH.md stage(s) named in the session prompt, on its own branch.
- Write tests as you build. Never finish with failing tests.
- At the end: tick LAUNCH.md boxes, update PROGRESS.md, commit, summarise, stop for my OK.
- Approved dependencies are the ones listed in this file. Ask before adding any other.
- Ask before breaking schema changes or deleting data.
- Never commit secrets. .env is gitignored; .env.example documents every variable.
- Keep it simple. Prefer deleting code to adding abstraction.
- Scope is frozen to F1–F22. New ideas go to BACKLOG.md, never into the current stage.
- Every command a human runs is a Makefile target documented in COMMANDS.md. Adding
  or changing one means updating COMMANDS.md in the same commit; `make help` lists them.
