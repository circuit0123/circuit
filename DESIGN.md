# Circuit — Design guide

Visual and writing rules for `apps/landing`, `apps/app` and `packages/ui`. Tokens live in
`packages/ui/src/tokens.css`; this file is the reason behind them. If a screen needs
something that is not here, change this file first.

## Idea
Circuit is about handovers: one person needs a thing, another offers it, and a line runs
between them. Our picture for that is a **suburban rail route map**: one line, round
stations, 45° bends, a loop that closes. Everything else stays quiet so that line is the
one memorable thing.

## Palette
Light theme only for now (students use phones outdoors). All text pairs are ≥ 4.5:1 (ratios measured, not estimated).

| Token | Hex | Use |
|---|---|---|
| `paper` | `#F5F7FA` | Page background |
| `surface` | `#FFFFFF` | Cards, sheets, inputs |
| `ink` | `#0E1A3A` | Body text, headings (15.9:1 on paper) |
| `ink-soft` | `#4A5573` | Secondary text (6.9:1 on paper, 7.4:1 on white) |
| `rule` | `#D5DBE6` | Borders, dividers (not for text) |
| `line` | `#1F4BD8` | The circuit line, primary buttons, links (6.4:1 on paper; white on it 6.9:1) |
| `line-wash` | `#E6ECFC` | Selected chips, quiet fills behind `line` text |
| `signal` | `#F2A100` | Hiring pins and badge fill (use with `ink` text, 8.0:1) |
| `bridge` | `#9B2C75` | Bridge match badge (white on it 7.0:1) |
| `verified` | `#16795A` | Verification badges, success (white on it 5.4:1) |
| `alert` | `#B3261E` | Errors, destructive (white on it 6.5:1) |

Colour is never the only signal: hiring, Bridge and verified always carry a text label.

## Type
Both faces come from `next/font/google`, self-hosted at build time.
- **Display: Bricolage Grotesque** (variable, 600–800). Headings and big numbers only.
- **Text: Hanken Grotesk** (400, 500, 600). Everything else.

Scale (mobile → desktop), line-height in brackets:

| Step | Size | Use |
|---|---|---|
| `display` | 40 → 72px (1.02) | Landing hero only |
| `h1` | 28 → 40px (1.1) | Page titles |
| `h2` | 22 → 28px (1.2) | Section titles |
| `h3` | 18px (1.3) | Card titles |
| `body` | 16px (1.55) | Default; never below 16px for inputs |
| `small` | 14px (1.45) | Metadata, captions |

Line length ≤ 68 characters. Sentence case everywhere. No all-caps labels. Negative
letter-spacing (−0.02em) on display and h1 only.

## Spacing and shape
- 4px base: 4, 8, 12, 16, 24, 32, 48, 64, 96.
- Page gutter 16px on mobile, 32px from 768px. Content max-width 1120px; reading text 62ch.
- Radius by role, not one for all: inputs and buttons 10px, cards 14px, sheets 20px (top
  corners), badges and chips fully round, avatars round.
- One shadow only: the sheet/modal shadow (`0 12px 32px rgba(14,26,58,.16)`). Cards use a
  1px `rule` border and no shadow.
- Touch targets ≥ 44×44px. Bottom bar 64px.

## Motion
- Only motion that answers an action (open, close, confirm, route change of a sheet) or
  that draws the circuit line once on first load of the hero.
- 120–200ms, `cubic-bezier(.2,.8,.2,1)`. Nothing loops. No entrance animations on every
  section, no hover lifts.
- `prefers-reduced-motion: reduce` turns all of it off; the hero line is then drawn complete.
- Skeletons are static blocks in `rule` colour with no shimmer.

## The circuit line
- 2px stroke in `line`, round caps, only horizontal, vertical and 45° segments.
- Stations are 12px rings (2px `line` stroke, `surface` fill); a filled `line` dot marks "you".
- A loop always closes back on itself. Labels sit beside stations in `small`, never on the line.
- Used for: the hero diagram, the circuit card in the app, section dividers (a short
  line with one station), empty states. Not used as background texture or ornament.
- Component: `CircuitLine` in `packages/ui`.

## Voice
- Plain, specific, second person. Indian English spelling (organisation, programme).
- Say what happens: "Send intro", not "Submit". The same action keeps the same name in
  the button, the toast and the notification ("Send intro" → "Intro sent").
- Say who and why: "They offer SEO, which you need." Not "Great match!".
- Errors say what went wrong and what to do; no apologies, no codes shown. "We couldn't
  load your matches. Check your connection and try again."
- Empty states say what will appear here and the one thing to do next.
- Numbers are real or absent. When the API hides a count under 5, say "fewer than 5".
- Use "need" and "offer" as the two core words. A "Bridge match" is explained once in
  plain words: "Different sector, complementary need."

## Accessibility floor
Visible 2px focus ring in `line` with 2px offset on every interactive element; skip link;
landmarks; labels on every input; modals trap focus and close on Esc; maps have a list
alternative; axe has zero serious or critical violations on every screen at 375px and 1280px.

## Banned list
- Gradients of any kind, glassmorphism/blur backdrops, glows, neon.
- Emoji or emoji-style icons. Icons are simple 24px outline SVGs, 1.75px stroke.
- Buzzwords: "unlock", "supercharge", "leverage", "seamless", "ecosystem-driven",
  "revolutionise", "next-gen", "synergy".
- Lorem ipsum, "John Doe", placeholder logos.
- Fake stats, fake testimonials, fake user counts, fake partner logos.
- A tracked all-caps eyebrow above headings, middle-dot meta strings, "→" appended to
  every link, one-word accent colour in a headline, identical card grids with the same radius
  and shadow everywhere, numbered steps unless the content really is a sequence.
- Cream backgrounds with terracotta accents; dark backgrounds with a neon accent.
