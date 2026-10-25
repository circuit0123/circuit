# Circuit — session prompts

Use plan mode (Shift+Tab) for every prompt below. One session per prompt; `/clear`
between them. Each runs on its own branch and is merged via PR before the next.

## 0. Repo audit (run first, read-only)
See "Prompt A" at the bottom.

## B0 — feature flags + commands (before B1)
```
Read CLAUDE.md (especially "Feature flags"), PRODUCTION.md §2b, COMMANDS.md, LAUNCH.md
Stage 1b and PROGRESS.md. Do Stage 1b on branch backend-b0. Plan first.
1. Feature flags exactly as CLAUDE.md describes: core/flags.py, feature_flags model +
   Django admin, members.is_tester, @require_flag, /api/config, manage.py flags,
   FEATURES env parsing with dependency validation. Wrap every feature that already
   has code in its flag, with an on and an off test each.
2. A Makefile with every target in COMMANDS.md and `make help`. Where a target needs
   something not built yet (e.g. deploy before Stage 5), make it print "not available
   until Stage N" and exit 1 instead of faking it. Deploy targets must confirm first;
   there is no production deploy target.
3. Run every local target from COMMANDS.md sections 1–8 once and paste the result
   summary into PROGRESS.md. Fix COMMANDS.md if anything differs.
Ask before any migration that changes existing tables. At the end: make check green,
tick Stage 1b, update PROGRESS.md, commit, push the branch and stop.
```

## Backend sessions (B1–B7)
Template — replace <SESSION> and <STAGES>:
```
Read CLAUDE.md, PRODUCTION.md, LAUNCH.md, DESIGN.md and PROGRESS.md. Do the BACKEND
parts only of <STAGES> (LAUNCH.md "Build order", session <SESSION>). Branch:
backend-<SESSION>. Design every endpoint from the DESIGN.md screen it serves. Skip
frontend/Vercel items and list them in PROGRESS.md under "Frontend remaining".
Plan first. Tests for every endpoint (success, failure, IDOR) and every job.
Regenerate packages/api-client/openapi.json. Ask before any command on cloud
resources. At the end: make check green, tick only backend boxes in LAUNCH.md,
update PROGRESS.md, commit, push the branch and stop.
```
Extra lines:
- B1: "After merging, I'll wire only the Home screen to check the API shape."
- B3: "Write legal drafts to docs/legal/ clearly marked as drafts for lawyer review;
  store consent with policy_version so text can change without code changes."
- B4: "Use /effort high. Prove with a test that a simulation-only model can never be
  promoted in production."
- B5: "Deploy only the API, jobs and scheduler. Put the API URLs in PROGRESS.md."
- B6: "Ask me before creating anything in production. Run the restore drill to staging
  and document it in RUNBOOK.md."
- B7: "Write FRONTEND_HANDOFF.md per CLAUDE.md 'API contract rules', add contract
  tests in tests/contract/, and freeze openapi.json with a version."

## Bug fixes (any time)
```
Here are bugs found while testing <env>: <list with steps>. For each: write a failing
test first, fix, run make check. Then redeploy <env> and run make smoke.
```

## Frontend (after B7)
```
Read CLAUDE.md, DESIGN.md, FRONTEND_HANDOFF.md, LAUNCH.md and PROGRESS.md. The backend
is complete and openapi.json is frozen. Regenerate packages/api-client. Build the
"Frontend remaining" items in PROGRESS.md, one screen at a time, following DESIGN.md
exactly with the frontend-design skill. If a screen needs something the API doesn't
provide, stop and tell me instead of working around it. Show screenshots at 375px
(dark and light) and 1280px after each screen and wait for my OK.
```

## Frontend session rules (every F session reads this)
- Read first: CLAUDE.md ("Frontend architecture", "Feature flags"), DESIGN.md (all of §1a,
  §3, §5, §6, §7, §8, §12, §13 plus the §4 sections for this session's screens),
  docs/design-reference/README.md and the reference files for this session's screens,
  docs/brand/README.md, COMMANDS.md, PROGRESS.md ("Frontend remaining", "Frontend → API
  needed"). Don't edit backend/.
- The reference files are the visual target: match spacing, sizes, hierarchy, colours,
  states and interactions. Never copy or import them; rebuild with packages/ui + tokens.
- Screens only call hooks in apps/app/src/data; hooks are the only code that touches the
  API client, Supabase or fetch (the ESLint rule enforces it).
- If a screen needs data the API doesn't return, don't invent an endpoint: add it to
  PROGRESS.md under "Frontend → API needed" and serve it from a clearly marked mock.
- Hide anything whose feature flag is off. Investor and partner screens are out of scope.
- Every screen: loading, empty and error states; 375px and 1280px; dark and light; all
  six accents; keyboard and screen reader labels; reduced motion.
- After each screen: Playwright + axe + premium.spec.ts green, screenshots next to the
  reference, list remaining differences, commit, then wait for my OK.
- End: make check green, PROGRESS.md updated (ticked items, "API needed"), push, stop.

## F1 — App foundation
```
Session F1: app foundation. Follow "Frontend session rules" in PROMPTS.md. Branch:
frontend-f1 (already checked out). Plan first.
packages/ui already has tokens, Geist and the Logo component from the landing sessions:
reuse and extend them, don't duplicate. Build:
1. ThemeProvider: theme (system/dark/light) and accent (six from DESIGN.md §5) applied
   before first paint from the member's saved appearance, with a crossfade on change.
2. Components (DESIGN.md §6): Button (primary/secondary/text), Chip, Card, ListRow,
   GroupedList, SegmentedControl, LargeTitleHeader (collapses on scroll), TopBar,
   TabBar (from TabBar.dc.html; partner variant), TabPager with every §3 swipe rule,
   Sheet with detents, Toast, Avatar (circuit-pattern placeholder), Badge
   (verified, Bridge match), MatchStrength (words only), EmptyState, ErrorState.
3. App shell: routes for the five tabs, safe areas, 404 and 500 pages, environment
   banner, persona switcher in dev/demo only.
4. Data layer: make api-client from the current openapi.json; apps/app/src/data with
   useFeatures(), useMe(), useAppearance() and a query client with error mapping; the
   ESLint rule blocking API/Supabase/fetch imports outside src/data.
5. Mock mode: `make mock` with TEMPORARY fixtures matching openapi.json exactly (marked
   "replace with B7 contract fixtures") and scenarios: empty, loading, error, slow 3G,
   beta access missing, features off, under-18.
6. PWA basics: manifest and icons from docs/brand (installable), favicon, theme colour.
7. /design page (dev only) showing every component in every state, both themes.
8. premium.spec.ts per DESIGN.md §13 item 5, plus TabPager touch tests.
```

## F2 — Sign-up and access
```
Session F2: sign-up and access. Follow "Frontend session rules" in PROMPTS.md. Branch:
frontend-f2. References: Welcome, Invite, Role, Work, Offer, Colour, Ready. DESIGN.md §4
"Sign-up and onboarding" defines all 14 steps; build every student/founder/mentor step
(investor 8i–11i and partner 8p–11p branches only if their flags are on; otherwise the
Role screen hides those rows). Build:
1. /join: reads role, organisation, invite code and src from the URL, keeps them through
   sign-in, skips the steps they answer; src saved on the member.
2. Sign-in: Continue with Google, email OTP (6-digit, paste, resend timer), auth callback.
3. Beta gate: invite code screen, waitlist confirmation; consent screen when
   needs_consent; under-18 safety screen; everything resumable from the saved step.
4. Onboarding steps 4–14 with one thing per screen, progress bar, back/skip rules,
   inline one-sentence errors, LLM chips with manual-picker fallback, accent pick, Ready
   with the first Daily Drop card.
5. Playwright: full sign-up under 2 minutes (timed), resume after reload, invite link
   skips step 3, role link skips step 5, under-18 path, LLM failure path.
Then add to PROGRESS.md: "Landing: set NEXT_PUBLIC_JOIN_LIVE=true after the app deploys."
```

## F3 — Home
```
Session F3: Home. Follow "Frontend session rules" in PROMPTS.md. Branch: frontend-f3.
References: Main (Home), Update, Notifications, Desktop. Build:
1. Home: large title, Live wire (trace, nodes, powered/seen states, current-dot animation
   once per session, edge fade), Daily Drop stack (reason-first card, swipe right/left
   with buttons always present, Intro me primary, Skip text, "That's today's drop"),
   Pulse feed (build logs without borders, roles, activity, "You're caught up", partner
   and promoted slots only if their flags are on).
2. Update view (full screen, swipe between updates, one action) and the Notifications
   screen grouped by day with unread dots and deep links.
3. Desktop Home: rail + centre column + Daily Drop rail exactly as Desktop.dc.html.
4. Intro request flow from Intro me (confirm sheet, weekly capacity message).
```

## F4 — Discover
```
Session F4: Discover. Follow "Frontend session rules" in PROMPTS.md. Branch: frontend-f4.
References: Discover (Jobs), People, Map, Job. DESIGN.md §4 "Discover" and "Startup
page" (no reference file: build it from the spec in the same style). Build:
1. Discover with search and the People · Startups · Jobs · Map segments (filters in a
   bottom sheet; Skills in demand at the top of Jobs).
2. Job page with skill match and sticky Apply; one-click apply; "my applications".
3. Map (MapLibre, OpenStreetMap tiles): pins by hiring status; tapping a pin opens the
   sheet; `See open roles` opens the Startup page at Hiring (or the job page when there's
   one role); non-hiring shows Follow; back restores pin and zoom.
4. Startup page per DESIGN.md: header, Follow, Hiring first, About, build logs,
   founders with intro via mutual, Claim this startup for unclaimed ones.
5. Founder applicant view ranked by skill match (founders only).
```

## F5 — Connect
```
Session F5: Circuits and Inbox. Follow "Frontend session rules" in PROMPTS.md. Branch:
frontend-f5. References: Circuits, Inbox, Chat. Build:
1. Circuits (if the flag is on): proposed/active circuit cards with the ring, who helps
   whom, time left, Accept/Decline, live segment updates via Realtime, the signature
   closing animation (DESIGN.md §7), mark done and rating, completed history, empty state.
2. Inbox: Chats + Requests (no Requests for under-18s), unread states, Realtime.
3. Conversation: bubbles (own messages in primary), send, image share, read receipts
   off by default, report/block in the header menu with confirm sheets.
```

## F6 — You
```
Session F6: profiles, posting and settings. Follow "Frontend session rules" in
PROMPTS.md. Branch: frontend-f6. References: Profile, Person, Composer, Settings,
Appearance. Build:
1. Own profile (profile strength meter for the owner only) and someone else's profile
   (Connect primary, Message, Intro via a mutual, offers/needs, highlights, build logs,
   circuits, about; no public counts).
2. Build log composer: media first (up to 4, crop only, client-side resize per B6),
   text with counter, capability chips, link, who-can-see (under-18 default My
   organisation); post view with media pager, reactions, one-level replies, report.
3. Settings: edit profile, privacy, notifications per type × channel, Appearance
   (theme, six accents with live preview, swipe toggle), export, delete account with
   confirm flow, help/FAQ, legal pages, sign out.
```

## F7 — Web polish and PWA
```
Session F7: desktop, PWA and polish. Follow "Frontend session rules" in PROMPTS.md.
Branch: frontend-f7. Build:
1. Desktop layouts for every tab per DESIGN.md §3 (left rail, centre column ≤600px,
   one right rail on Home only), keyboard shortcuts for tabs.
2. PWA (serwist): offline shell, update prompt, install prompt incl. iOS instructions.
3. Performance: Lighthouse ≥ 90 mobile on Home, lazy-load the map and charts, bundle
   budget; fix the top issues.
4. Full Playwright run of the five demo stories at 375px and 1280px; axe on every route;
   premium.spec.ts on every tab.
5. A "Frontend done" section in PROGRESS.md: every screen, its status, and the final
   "API needed" list for B7.
```

## Prompt A — full repo audit (read-only)
```
Read CLAUDE.md, PRODUCTION.md, LAUNCH.md, BACKLOG.md, DESIGN.md and PROGRESS.md. Audit
the whole repo against them. Do NOT change any code. Use the test-runner agent to run
make check. Report, in PROGRESS.md under "Audit <date>":
1. Status of every LAUNCH.md item: Done / Partial / Missing, with evidence (file paths,
   test names). Fix any box that is ticked but not actually done, or done but unticked.
2. Every feature F1–F18: which backend endpoints, models, jobs, tests and frontend
   screens exist for it.
3. Anything in the code that contradicts the docs (old stack pieces, Neo4j, Today
   strip/story rings, raw low match %, initials-only avatars, hard-coded URLs,
   unapproved dependencies, missing permission checks, PII in logs).
4. Test results: pass/fail per demo story, failing tests and why, untested endpoints.
5. Security quick check: every endpoint has auth + permission + IDOR test; DEMO_AUTH
   blocked in staging/production; RLS on every table; no secrets in git history.
6. The 10 most important things to fix, in order.
Stop after writing the report.
```

## Prompt B — where things need updating (plan only)
```
Read the "Audit" section in PROGRESS.md plus CLAUDE.md, DESIGN.md and LAUNCH.md. Make a
plan, no code changes yet, listing every place that needs updating, grouped as:
1. Docs out of date (which file, which section, what it should say) — propose exact
   edits to CLAUDE.md / PRODUCTION.md / LAUNCH.md / DESIGN.md / PROGRESS.md.
2. Backend code to change (file, what and why), mapped to a backend session B1–B7.
3. Frontend code to change or delete (old design pieces, mock data, hand-written fetch
   calls), mapped to screens in DESIGN.md.
4. Tests to add or fix.
5. Things only I can do ([YOU] items: accounts, URLs, approvals, lawyer).
For each item give effort (S/M/L) and the branch it belongs on. Then wait for my OK;
I'll approve which groups to do and in which session.
```

## Design refinement pass (keep the existing frontend)
```
Read DESIGN.md (§1a philosophy, §3 swipe between tabs, §5 "Emerald" palette and logo,
personal accent, materials and iOS patterns, §7 motion). Keep the existing frontend and
refine it in place; don't rebuild. Plan first, stopping after each step with screenshots
at 375px (dark and light) and 1280px:
1. Tokens + ThemeProvider: replace colour, type, radius and motion tokens in packages/ui;
   theme and accent as CSS variables applied before first paint; remove every old accent
   and orange; grep for hard-coded colours, sizes and radii and replace them with tokens.
2. Components: Button, Card, Chip, Avatar, Sheet (detents), SegmentedControl, Toast,
   inputs, LargeTitleHeader, GroupedList, translucent TopBar/TabBar with fallbacks,
   context menus with "…" buttons, press states, AccentPicker.
3. TabPager: swipe between tabs with every gesture rule in §3; Playwright touch tests.
4. Screens one at a time (Home, Discover, Circuits, Inbox, Profile, Settings → Appearance,
   then the rest): apply iOS patterns and the §1a craftsmanship checklist; each screen
   has one job and one primary action — list anything you removed and why.
If the backend has no appearance endpoint yet, store the choice locally for now and list
the endpoint under "Backend remaining" in PROGRESS.md.
Keep all Playwright tests passing; update snapshots only for intended visual changes.
```

## Premium pass (when the UI feels cramped or "not Apple")
```
Read DESIGN.md §1a, §3, §4 "Home", §5 (especially "Breathing room"), §12 and §13. The UI
feels cramped and not premium. Don't change colours or features; fix space, restraint
and hierarchy. Branch: frontend-premium. Plan first.
1. Write apps/app/tests/premium.spec.ts exactly as DESIGN.md §13 item 5 describes and run
   it on every tab screen. Show me the failures as a table (screen, width, rule, element).
2. Fix packages/ui first: spacing tokens for section gaps, surface padding and row
   heights; feed items without borders; Daily Drop actions (primary `Intro me`, text
   `Skip`); neutral grey placeholder art; LargeTitleHeader with collapse on scroll;
   edge fade for horizontal rows.
3. Then screens one at a time, starting with Home: desktop = centre column + one rail
   with only the Daily Drop; move "People you may know" and nearby roles to Discover and
   "Skills in demand" to Discover → Jobs. For each screen, list what you removed or moved
   and why, and show before/after screenshots at 375px (dark and light) and 1280px. Wait
   for my OK before the next screen.
Done when premium.spec.ts passes on every screen and all other Playwright tests pass.
Commit after each screen, push the branch and stop.
```

## Quick audit after pushing (read-only)
```
Pull the latest from all branches. Read CLAUDE.md, DESIGN.md, LAUNCH.md and
PROGRESS.md. Audit backend AND frontend against them without changing code: run make
check with the test-runner agent, then write "Quick audit <date>" in PROGRESS.md with:
(1) LAUNCH.md items Done / Partial / Missing with evidence, fixing wrong ticks;
(2) features F1–F19: backend endpoints + tests and frontend screens that exist;
(3) anything contradicting the docs (old accent/orange, story rings, raw low %,
hard-coded URLs or colours, mock data still in use, unapproved dependencies, promotions
affecting rankings, missing permission/IDOR tests, PII in logs);
(4) failing tests and why; (5) top 10 fixes in order, each tagged backend or frontend
with effort S/M/L. Stop after the report.
```

## Fix from the audit
```
Read the latest "Quick audit" in PROGRESS.md. Fix items <numbers> only, on branch
fix-<short-name>. For each: failing test first, then the fix, then make check. Update
the audit item to Fixed with the commit, commit, push and stop.
```

## Payments (Stage 4e backend, session B3c)
```
Read CLAUDE.md (F20, "Payment rules"), PRODUCTION.md §2a and §14, LAUNCH.md Stage 4e and
PROGRESS.md. Do the BACKEND parts of Stage 4e on branch backend-b3c, in Razorpay TEST
mode only. Plan first, /effort high. Use the official razorpay SDK. Verify payment
signatures with the key secret and webhook signatures on the RAW body with the webhook
secret, constant-time compare. Webhooks are the only thing that marks an order paid.
Write tests for every case in LAUNCH.md Stage 4e and PRODUCTION.md §14 rows 7–9 and 18.
Update FRONTEND_HANDOFF.md, openapi.json and contract tests. Commit, push, update
PROGRESS.md and stop.
```

## Production failure test pass (before going live)
```
Read PRODUCTION.md §14. For every row: find the automated test that covers it or write
it; for rows that need a manual check, write step-by-step instructions in RUNBOOK.md
under "Pre-production checks". Run everything on staging with production-sized seed
data (≥50k members). Report each row as Pass / Fail / Needs manual check, fix failures
one at a time (failing test first), and stop with the report in PROGRESS.md.
```

## Frontend data layer + mock mode (do once, before heavy UI work)
```
Read CLAUDE.md "Frontend architecture" and FRONTEND_HANDOFF.md. Create apps/app/src/data
with one TanStack Query hook per screen/action listed in the handoff, returning
UI-ready objects. Move every existing API, Supabase or fetch call out of screens and
components into these hooks; add an ESLint rule that blocks such imports elsewhere.
Add `pnpm dev:mock` using MSW handlers generated from the backend contract fixtures,
with a scenario switcher (empty, loading, error, slow 3G, under-18, partner, investor).
Keep all Playwright tests passing. Commit, push and stop.
```

## Pure UI tinkering session (any time after the above)
```
Read DESIGN.md. UI-only session: change only files under apps/app/src/app, apps/landing
and packages/ui. Do not edit src/data, packages/api-client or the backend. If a screen
needs data the hook doesn't return, stop and tell me. Run in mock mode, show
screenshots at 375px and 1280px after each change.
```
