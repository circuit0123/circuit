# UI v2 plan

## 1. Audit findings

**Stack**
- Next.js 16.4, App Router, React 19, TypeScript. Two apps: `apps/app` (product, client-rendered) and `apps/landing` (static export). pnpm workspaces, so the build command is `make build-web` (pnpm), not `npm run build`.
- Tailwind v4, CSS-first. No `tailwind.config`. All tokens live in `packages/ui/src/tokens.css`, imported by each app's `src/app/globals.css`.
- Components: shared primitives in `packages/ui/src/` (TabBar, Screen, Button, Logo, PostCard…); screens in `apps/app/src/components/<area>/`; route files in `apps/app/src/app/` are one-line wrappers. Data hooks in `apps/app/src/data/` (untouched by this work).
- Geist and Geist Mono are already loaded in the app through the `geist` package (`apps/app/src/app/layout.tsx`). Landing loads Geist Sans only.
- One Vercel project serves landing at `/` and the app at `/app` (`vercel.json`), so they share an origin.

**Feature flags today**
- Server-side flags in `backend/core/flags.py` (off / testers / everyone), exposed by `GET /api/config`, read through `useFeatures()` in `apps/app/src/data/features.ts`. They gate features, not looks.
- A proper per-member `ui_v2` would mean adding a flag there, which is a backend and API-contract change. That is out tonight.

**Proposed `ui_v2` switch (frontend only)**
- One build-time variable: `NEXT_PUBLIC_UI_V2 = off | preview | on` (default `off`).
- `preview`: old UI for everyone, except a browser that has opened `/app/?ui=v2`. That choice is saved in `localStorage` and `?ui=v1` clears it. This is per browser, not per account, because sign-in and the invite gate render before any account is known. Open the link on your own phone and laptop to see v2 first.
- `on`: v2 for everyone. `off`: the v2 code is never reached. Rollback is changing the variable and redeploying the frontend.
- Mechanism: a tiny inline script in `layout.tsx` puts `data-ui="v2"` on `<html>` before first paint; a `useUiV2()` hook reads it. v1 components are not edited; each v2 screen is a new file chosen at one branch point.
- Landing is static, so it cannot switch per browser cleanly. In `preview` the v2 home is built at a hidden, no-index `/next/` route; in `on` it becomes `/`.

**Route-to-file map**

| Screen | Route | Files |
|---|---|---|
| Landing | landing `/` (+ `/students` etc.) | `apps/landing/src/app/page.tsx`, `components/{Header,Hero,Audiences,Faq,Footer,Waitlist}.tsx`, `content/home.ts` |
| Sign-in | any app route when signed out | `apps/app/src/components/Gate.tsx` → `SignIn.tsx` |
| Beta invite gate | same, gate = `invite`; `/join` | `components/onboarding/Invite.tsx`, `components/JoinRoute.tsx` |
| Nav / shell | `(shell)/layout.tsx` | `components/AppShell.tsx`, `packages/ui/src/TabBar.tsx` |
| Feed (home) | `/` | `components/home/{Home,Pulse,LiveWireSection,DropSection}.tsx`, `packages/ui/src/{PostCard,PulseCards,LiveWire}.tsx` |
| Post composer | `/compose` | `components/compose/Composer.tsx`, `packages/ui/src/PostComposer.tsx` |
| Profile | `/profile`, `/members/[id]` | `components/profile/{Profile,Person,parts}.tsx` |
| Inbox | `/inbox` | `components/inbox/{Inbox,Waiting}.tsx` |
| Chat | `/inbox/[id]`, `/inbox/new` | `components/inbox/Conversation.tsx` |
| Startup map | `/discover?s=map` | `components/discover/MapView.tsx`, pin CSS in `app/globals.css` |
| Startup directory | `/discover?s=startups`, `/startups/[id]` | `components/discover/{Discover,parts,FilterSheet}.tsx`, `components/startups/StartupScreen.tsx` |

**Do DMs let anyone message anyone? No. But they are not connections-only either.**
The server rule (`backend/apps/social/relations.py: may_message`, `apps/messaging/services.py`):
- Connected people chat freely.
- An adult who is **not** connected can still send **one** first message to anyone whose profile is visible and who has "allow requests" on. That setting is **on by default**. The message lands in a separate Requests folder until the recipient accepts.
- People in the same organisation can also message each other without being connected.
- Under-18s only get messages from connections and their own organisation's staff.

So "No cold messages, ever" and "Can strangers message me? No" are **not true today** and must be reworded (section 5).

## 2. Token setup
- **CSS variables:** append one block to `packages/ui/src/tokens.css`, scoped `:root[data-ui="v2"]`, with the handoff's `--c-*` variables. The same block also remaps the existing tokens (`--bg` → `#0A0A0C`, `--surface` → `#17181B`, `--separator` → `#2E3036`, `--text`, `--text-muted`, `--primary`, `--current`) so screens not rebuilt tonight (settings, jobs, onboarding, notifications) pick up the PM palette instead of clashing. Add `--color-c-*` entries to `@theme inline` so Tailwind classes like `bg-c-card` work. Nothing outside the `data-ui` scope changes, so flag-off output is identical.
- **v2 is dark only.** The block forces the dark values regardless of the member's theme and accent setting.
- **Fonts:** keep the existing `geist` package (same typefaces, self-hosted, already wired to `--font-sans` / `--font-mono`). The handoff says `next/font/google`; switching would change the flag-off build for no visible gain. Only change: add `GeistMono` to `apps/landing/src/app/layout.tsx`.
- **Shared v2 pieces** go in `packages/ui/src/v2/`: `LogoV2` (SVG copied verbatim from `PMHome.dc.html`), `BigHeadline` (outlined second line), `EmeraldBand`, `HeroCard`, `IconButton`, `MonoLabel`, `ChipV2`.

## 3. Build order
New screen files live in `apps/app/src/components/v2/`. Data hooks, API client and backend are never touched.

| # | Step | Follows | Files changed | Stays unchanged |
|---|---|---|---|---|
| 1 | Tokens, fonts, flag | handoff §2, `PMBrand` | `packages/ui/src/tokens.css`, new `packages/ui/src/v2/*`, new `apps/app/src/lib/uiV2.ts`, `apps/app/src/app/layout.tsx` (inline script), `apps/landing/src/app/layout.tsx` (mono font) | All v1 components; theme script |
| 2 | Nav | `PMNav` | new `v2/NavV2.tsx`; one branch in `AppShell.tsx` | Tab order logic, swipe pager, unread dot, desktop left rail (recoloured by tokens only) |
| 3 | Sign-in and invite | `PMWelcome`, `PMInvite` | new `v2/SignInV2.tsx`, `v2/InviteV2.tsx`; branches in `Gate.tsx` | Google/OTP logic, email and code steps, waitlist flow, demo personas, redeem hook |
| 4 | Feed and composer | `PMHome` (layout only), `PMComposer` | new `v2/HomeV2.tsx`, `v2/PostCardV2.tsx`, `v2/ComposerV2.tsx`; branches in `Home.tsx`, `Composer.tsx` | Feed stays home; `useHome`, `usePulse`, upload, crop, 500-char limit, visibility picker, capability tags, required alt text |
| 5 | Profile | `PMProfile` | new `v2/ProfileV2.tsx`, `v2/PersonV2.tsx`; branches in `Profile.tsx`, `Person.tsx` | Connect / Message / intro rules, private-profile handling, tabs content |
| 6 | Inbox and chat | `PMInbox`, `PMChat` | new `v2/InboxV2.tsx`, `v2/ChatV2.tsx`; branches in `Inbox.tsx`, `Conversation.tsx` | Chats / Requests folders, accept / decline / block, attachments, realtime, read receipts |
| 7 | Map | `PMMap` | new `v2/MapChromeV2.tsx`; v2-scoped pin CSS in `globals.css`; branch in `MapView.tsx` | MapLibre setup, tiles, filters, data |
| 8 | Directory | `PMDiscover` | new `v2/DiscoverV2.tsx`, `v2/StartupCardV2.tsx`; branch in `Discover.tsx` | Search, segments, existing hiring filter, filter sheet, jobs and people data |
| 9 | Landing | `PMLanding` | new `apps/landing/src/components/v2/*`, new `app/next/page.tsx`; branch in `app/page.tsx`; copy in `content/home.ts` (v2 entries) | Waitlist form and endpoint, CTA link building, audience pages, privacy and terms pages |

After each step: `make test-web` (or `make test-landing` for step 9) with the flag off, and one commit.

## 4. Out of scope tonight (handoff §4)
- `PMHome` daily intro cards, `PMRole` / `PMOffer` / `PMReady` onboarding, `PMPeople`, `PMCircuits`, `PMPings`, `PMJob`.
- `PMSettings`: Settings exists, so it is eligible, but I would ship it tokens-only tonight and rebuild it later.
- Those screens keep their current layout and inherit the v2 colours from the token remap.
- No API, database, backend, `.env` or secret changes. No pushes to main.

## 5. Honest-copy fixes (handoff §5)
| Item | Finding | Fix |
|---|---|---|
| "No cold messages, ever" (landing hero, step 03, sign-in) | False: strangers can send one message request (section 1) | Remove. Sign-in keeps today's line: "Find work, collaborators and mentors who need what you're good at." |
| FAQ "Can strangers message me? No" | False | "Someone you're not connected to can send one message request. It waits in a separate Requests folder until you accept. Under-18 members never receive them." |
| "LIVE" pill | The app has a real Live wire fed by events, behind the `pulse` flag | Show the pill only from `useLiveWire` data; no data, no pill. Never the sample line |
| "Strong match" / "Good match" | Sample content | Not shown anywhere in v2 tonight, including the landing example card |
| Vouch quotes and names (Meera, Sakthi, Kavya, Tatvagrid) | Sample content | Landing hero card becomes a labelled illustration with no real-looking quote, or is dropped |
| "Three warm introductions a day" | Only true where `daily_drop` is on | Use the current landing subhead instead |
| Investors tile | Live site already gates it on `investor_mode` | Hidden in v2 unless that flag is on |
| `[COMPANY LEGAL NAME]` | Footer already reads `NEXT_PUBLIC_COMPANY_LEGAL_NAME` | Reuse; omitted when empty, never a placeholder |
| Privacy / Terms / Contact | `/privacy/` and `/terms/` exist; Contact reads `NEXT_PUBLIC_CONTACT_EMAIL` | Link to those |
| Other sample details | "10 CHARACTERS" (live codes are 6+), "STEP 1 OF 4", "BETA · CHENNAI", "ACTIVE TODAY · 4 KM", profile count tiles, "introduced by Arun", 280-char limit, "12 applied" | Dropped or replaced with what the app really knows |

## 6. Test checklist
- [ ] Flag `off`: `make test-web` and `make test-landing` pass with no test changes (the existing Playwright suites are the proof that the old UI is unchanged). Manual smoke: sign-in, feed, DM, map.
- [ ] Flag `preview` without `?ui=v2`: identical to off.
- [ ] Flag on, at 390px and 1440px: nav, sign-in (Google + email code), invite code + waitlist, feed, composer (post blocked until alt text), own profile, other profile, inbox (Chats and Requests), chat (send text + image), map (pin select, card), directory (hiring filter), landing.
- [ ] New `apps/app/tests/ui-v2.spec.ts`: each v2 screen renders in mock mode at both widths, with axe checks.
- [ ] Keyboard focus visible; every icon button labelled; no muted text under 12px.
- [ ] No sample names, quotes or placeholders in the built output (grep for Sakthi, Meera, Tatvagrid, `[COMPANY`).
- [ ] `make build-web` passes; no console errors.

## 7. Risks and open questions
1. **Logo mismatch.** The PM screens draw the centre node in `#ECEDEF` and set "circuit" as live Geist text. The repo's brand file (`packages/ui/src/logo-paths.ts`, from `docs/brand/svg`) has an emerald centre node and an outlined wordmark. Your rule says to copy the PM SVG exactly, so v2 uses the PM version. Tell me if the brand file should win instead.
2. **No desktop design for the app.** Every PM app screen is 390px; only the landing is drawn wide. At 1440px I will keep the current left rail and 600px column in v2 colours. It will look consistent, not designed.
3. **Map tiles are light.** The live map uses standard OpenStreetMap raster tiles; `PMMap` shows a dark map. Tonight only the pins, header and card get restyled. A dark map needs a different tile source.
4. **Light theme and accent colours.** v2 is dark-only and emerald-only. Members who chose light or another accent will see their setting ignored while v2 is on. The Appearance screen should hide those options under v2.
5. **Circuits tab.** `PMNav` has four tabs plus the `+`. Where the `circuits` flag is on, the live bar has five. I will keep Circuits in the v2 bar when its flag is on.
6. **The handoff says daily intros are not built, but the code has Daily Drop and Live wire** behind `daily_drop` and `pulse`. I don't know which are on in production. The plan keeps whatever shows today and restyles it.
7. **Per-account preview is not possible without a backend change.** The `?ui=v2` browser switch is the substitute. Anyone who learns the link can see v2 during preview; nothing private is exposed by that.
8. **`.env.example`** should document `NEXT_PUBLIC_UI_V2`. It holds no secrets, but it is an env file, so I will only add the line if you say so. You set the real value in Vercel yourself.
9. **This departs from `DESIGN.md`** (true black, six accents, light theme, tab bar spec) and from the stage-by-stage rule in `CLAUDE.md`. `DESIGN.md` is left as is until v2 is on for everyone.
10. **Time.** Nine steps before 7:30 AM is tight. Steps 1–6 are the core; map, directory and landing can each ship later with the flag still protecting them.
