# Circuit `ui_v2` — "PM / professional mayhem" reskin handoff

**Goal:** reskin the live app in the PM design, behind a `ui_v2` flag, and relaunch at 9:00 AM.
**Design source:** https://claude.ai/artifact/KS93XSNUApAMoVJD9kvGpw. The screens are the `project/PM*.dc.html` files. Ignore the Mayhem*, Mono*, Plum*, Trio*, Mid*, GenZ* and Pro* explorations.
**Hard stop:** finish features by 7:30 AM. Use 7:30–9:00 for testing and deploying.

---

## 1. Rules (do not break)
1. **Put everything behind `ui_v2`.** With the flag off, the current UI must render unchanged. If anything breaks after launch, switch the flag off.
2. **Reskin only.** No new backend features tonight. Change no API contracts and no DB migrations.
3. **Keep the logo exactly as it is:** the emerald arc with three nodes, plus the "circuit" wordmark. Copy the SVG from `PMHome.dc.html`. Never recolour or redraw it.
4. **One loud moment per screen.** Use at most one rotated emerald band, outlined headline or bright CTA per screen.
5. **Write honest copy only** (see section 5).
6. **Work on a branch** (`feat/ui-v2`). Open a PR. Don't push to main without review.

## 2. Design tokens
Put these in one place: CSS variables in `globals.css`, or a Tailwind theme extension.

```css
:root[data-ui="v2"] {
  --c-bg:        #0A0A0C;   /* page */
  --c-card:      #17181B;   /* cards, inputs, icon buttons */
  --c-border:    #2E3036;
  --c-hero:      #272727;   /* hero / featured card */
  --c-hero-text: #F1F1F1;
  --c-hero-muted:#AAAAAA;
  --c-text:      #ECEDEF;
  --c-muted:     #9A9CA3;
  --c-brand:     #00563F;   /* emerald: in-app primary buttons, bands */
  --c-bright:    #2FBF8A;   /* emerald bright: accents, landing CTA, live dots */
  --c-bright-bg: #0F2A21;   /* tinted pill behind bright text */
  --font-sans: "Geist", system-ui, sans-serif;
  --font-mono: "Geist Mono", ui-monospace, monospace;
}
```
Load the fonts with `next/font/google` (Geist, Geist_Mono).

## 3. Recurring patterns (copied from the PM screens)
| Pattern | Spec |
|---|---|
| Big headline | 54px (mobile) / clamp(60px, 9vw, 132px) (landing), weight 700, line-height 0.95–0.98, letter-spacing −0.055em. Second line is outlined: `color: transparent; -webkit-text-stroke: 1.5px var(--c-muted)` |
| Section heading | clamp(44px, 6vw, 80px), 700, −0.055em, ends with an emerald `.` (`color: var(--c-bright)`) |
| Mono label | Geist Mono 11–13px, UPPERCASE, `--c-muted` (e.g. `INVITE-ONLY BETA · CHENNAI`, `STEP 3 OF 4`) |
| Emerald band | absolutely positioned div, `background: var(--c-brand)`, `transform: rotate(-5deg … -8deg)`, behind content, `aria-hidden` |
| Hero card | `--c-hero` bg, radius 22px, padding 8px, inner dark panel radius 16px, stacked "deck" behind it (one card rotated 3deg in `--c-brand`, one −2deg in `--c-card`) |
| Card | `--c-card` bg, 1px `--c-border`, radius 18–22px |
| Primary button (app) | height 48–52px, radius 12–14px, `--c-brand` bg, `--c-text` text, 15–16px / 600 |
| Primary button (landing) | `--c-bright` bg, `--c-bg` text |
| Secondary button | transparent, 1px #4A4A4A border, same size |
| Icon button | 40×40, radius 999px, `--c-card` bg, 1px `--c-border` |
| Chip / toggle | height 36px, radius 10px. Off: `--c-card` / `--c-border`. On: `--c-bright-bg` bg, `--c-bright` text, `--c-brand` border. Use `aria-pressed` |
| Live pill | height 32px, radius 999px, 6px `--c-bright` dot + mono "LIVE" + one line of text + mono time |
| Bottom nav | floating `PMNav` component, 366×64 at 12px from the bottom/left (see `PMNav.dc.html`) |
| Mobile frame | the designs are 390×844. Build them responsive; don't hard-code the frame |

## 4. Scope for tonight: live feature → PM screen
These are mapped by screen name. Open each screen to confirm before building it.

**Ship tonight (these features are already live):**
| Live feature | PM screen(s) | Notes |
|---|---|---|
| Landing page (circuitapp.net) | `PMLanding` | Hide the Investors tile and change the FAQ (see section 5) |
| Sign-in (Google, email OTP) + beta gate | `PMWelcome`, `PMInvite` | Restyle only. Auth logic stays as it is |
| App shell / nav | `PMNav` | Only include tabs for features that exist |
| Feed + posts with photos | `PMHome` *layout and tokens only*, `PMComposer` | Daily intros aren't built, so **the feed stays as home** in the PM style. Keep alt text required in the composer |
| Profiles + avatars | `PMProfile` | |
| Direct messages + attachments | `PMInbox`, `PMChat` | |
| Startup map + neighbourhood pins | `PMMap` | |
| Startup directory (148 startups) | `PMDiscover` | Use the existing hiring / not-hiring filter |

**Not tonight (needs backend, stays behind a later flag):**
`PMHome` daily intro cards, `PMRole` / `PMOffer` / `PMReady` onboarding, `PMPeople`, `PMCircuits`, `PMPings`, `PMJob`, `PMSettings` (ship it only if Settings already exists in the app).

## 5. Honest-copy checklist (fix before relaunch)
- [ ] **"LIVE" activity pill:** show it only if it's fed by real events. Otherwise remove it. Never hard-code sample activity.
- [ ] **"Strong match" / "Good match":** don't show these until a real match score exists.
- [ ] **Vouch quotes** (e.g. "He fixed our sync bug…" — Meera): use them only when written by the named person, with consent. Sample names stay in mockups only.
- [ ] **"No cold messages, ever" / "Can strangers message me? No":** keep this copy only if live DMs are actually limited to accepted connections. If anyone can DM anyone today, reword it to describe what's true.
- [ ] **Investors tile ("Three startups a day"):** hide it until investors are actually on Circuit.
- [ ] **Footer `[COMPANY LEGAL NAME]`:** replace it with the registered name.
- [ ] **Privacy / Terms / Contact links:** point them at real pages, not `#`.

## 6. Done checklist (7:30–9:00)
- [ ] `ui_v2` off: the old UI is unchanged (smoke-test sign-in, feed, DM, map)
- [ ] `ui_v2` on: every screen in section 4 renders at 390px and 1440px
- [ ] Keyboard focus is visible, buttons have labels, and text contrast passes (muted #9A9CA3 on #0A0A0C is OK for body text, but not below 12px)
- [ ] Images keep alt text
- [ ] `npm run build` passes; there are no console errors
- [ ] Deploy with `make deploy ENV=production`, then turn `ui_v2` on for your own account first, then for everyone
- [ ] Write a results log: what shipped, what's flagged off, and known issues
