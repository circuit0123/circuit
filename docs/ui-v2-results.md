# UI v2 results log

Branch `feat/ui-v2`. Frontend only: no API, database, backend, `.env` or secret changes. Plan: `docs/ui-v2-plan.md`.

## How to switch it on and off
One build-time variable, `NEXT_PUBLIC_UI_V2`, set in Vercel for **both** the app and the landing project, then redeploy the frontend:

| Value | App | Landing |
|---|---|---|
| `off` (default, or unset) | Old UI. v2 code is never reached. | Old home. `/next/` shows a 404 page. |
| `preview` | Old UI for everyone, except a browser that opened `/app/?ui=v2` (saved in that browser; `?ui=v1` clears it). | Old `/`. v2 home at hidden, no-index `/next/`. |
| `on` | v2 for everyone. | v2 home at `/`. |

Rollback = set `off` and redeploy. The preview switch is per browser, not per account (sign-in renders before any account is known). `NEXT_PUBLIC_UI_V2` is not in `.env.example`; I did not touch env files. Add the line if you want it documented.

## What shipped (one commit per step)
1. **Tokens, flag, shared pieces**: `--c-*` tokens scoped to `data-ui="v2"` (also remapping the old tokens so un-rebuilt screens match; dark only), the `NEXT_PUBLIC_UI_V2` switch, `packages/ui/src/v2/` (LogoV2, BigHeadline, EmeraldBand, HeroCard, IconButton, MonoLabel, ChipV2), Geist Mono on landing.
2. **Nav**: floating bar, active pill, `+` for a build log (only when `pulse` is on). Circuits stays in the bar when its flag is on. Desktop rail unchanged.
3. **Sign-in welcome and invite code**. Auth, redeem and waitlist logic untouched; the email/code steps and waitlist screens inherit the v2 colours.
4. **Feed and composer**: header, big headline, LIVE strip, post cards, composer header/headline/text panel. Alt-text blocking, 500 limit and uploads untouched.
5. **Profiles**: own and other-person banner.
6. **Inbox and chat**: pill tabs, rows, bubbles, composer.
7. **Map**: headline, count, pins, selected-startup card. The map is drawn dark in v2.
8. **Directory**: pill tabs, headline, startup and role cards.
9. **Landing home** (`apps/landing/src/components/v2/HomeV2.tsx`).

Plus `apps/app/tests/ui-v2.spec.ts`, `playwright.v2.config.ts` and `make test-web-v2` (in COMMANDS.md).

## Honest-copy fixes applied
- "No cold messages" removed everywhere. New FAQ "Can strangers message me?" says one message request waits in Requests, never for under-18s. The profile line "only takes messages from connections" is reworded in v2.
- LIVE pill only from real Live wire data; no data, no pill.
- Landing: no sample intro card, quote, names or "Strong match"; no "three a day"; Investors tile only when `investor_mode` is on; footer legal name only if set; Privacy/Terms/Contact are real links. Dropped "STEP 1 OF 4", "10 CHARACTERS", city labels, count tiles, "introduced by", the 280 limit.

## Skipped, and why
- Out of scope per the plan: PMHome daily intro cards, Role/Offer/Ready onboarding, People, Circuits, Pings, Job. They keep their layout and inherit the v2 colours.
- PMSettings: tokens only, not rebuilt. Settings → Appearance still offers theme and accent options that v2 ignores (v2 is dark and emerald only). Hide them if v2 goes on for everyone.
- Landing: screen tour, hero video and pilot-city blocks are not in v2 (the tour shows old-UI screenshots).
- Nothing needed a backend change, so nothing was skipped for that reason.

## Known issues and decisions for you
- **Real match words still show.** Inherited v1 pieces (the Daily Drop card, people tiles) still show "Strong match" / "Good match" from real scores. The plan says not anywhere in v2. My new v2 cards leave match words out; the old pieces were not changed. Say if you want those hidden too.
- **Logo**: v2 uses the PM logo (light centre node, live "circuit" text), not `docs/brand/svg`. Your call on which wins.
- No desktop design exists for the app: at 1440px v2 keeps the left rail and 600px column in v2 colours.
- Map tiles are still OpenStreetMap raster, dimmed dark, not a true dark style.
- v2 flips on after hydration, so the first frame can briefly show v1 structure in v2 colours.
- With the flag `off`, `/next/` on the landing exists as a 404 page served with a 200 status (noindex).
- Sign-in welcome, invite screen and landing home are covered by typecheck, build and my own screenshots only. Mock mode starts signed in, so Playwright cannot reach the sign-in screens. Google and email-code flows were not exercised.
- Screenshots are in `screenshots/ui-v2/` (not committed).
- The `/design` gallery and mock fixtures contain sample names (existing, dev only); no v2 file does.

## Test checklist
- Flag off, `make test-web`: **629 passed, 0 failed.** (An earlier run during parallel builds had 4 phone flakes that passed alone.)
- `make test-landing`: **397 passed.**
- `make test-web-v2` (flag on, 390px and 1440px, axe): **16 passed**, stable over 3 runs after the person-profile check was made to wait out the fade-in.
- Preview mode: no param = old UI; `?ui=v2` = v2 and saved; `?ui=v1` clears (checked in a browser).
- Typecheck, lint and `pnpm build` for app and landing pass. The flag-on build has no "No cold messages" or `[COMPANY` text.
- Not done: manual smoke of real sign-in, a DM against a real backend, and real map tiles on a device.
