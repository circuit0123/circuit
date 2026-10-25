# Circuit — Design guide (lifestyle networking app)

Read this before building or changing any screen. It defines how Circuit looks,
moves, sounds and behaves. If a screen breaks a rule here, the screen is wrong.

---

## 1. What Circuit should feel like

Circuit is the app young builders open every day to see what's happening in their
world: who near them is building what, who needs help, who's hiring, and where
their next opportunity is. It should feel as natural to open as Instagram, but
leave people better off: closer to a job, a collaborator, a mentor.

Three words: **alive, personal, generous.**
- Alive: something new every day, real people and real work, motion that feels physical.
- Personal: your profile is your identity and your portfolio, not a CV.
- Generous: every interaction can turn into help, an intro, or an opportunity.

North-star moment: you open Circuit in the morning, see three new people worth
meeting with a reason for each, a classmate's build log, and a startup 4 km away
hiring for exactly your skills. You tap "Intro me" and close the app feeling ahead.

## 1a. Design philosophy (how we decide)

We follow the principles Steve Jobs held Apple to, turned into rules we can check.

| Principle | What it means for Circuit | The rule |
|---|---|---|
| "Simplicity is the ultimate sophistication." | Remove until it breaks, then add back one thing. | Every screen has ONE job and ONE primary action. If a screen needs explaining, redesign it. |
| Focus is saying no. | Most ideas are good; most don't belong on this screen. | Before adding an element, name what it replaces. A new feature goes to BACKLOG.md unless a screen genuinely needs it. |
| "Design is how it works." | Looks follow behaviour, never the reverse. | Prototype the interaction (tap, swipe, wait, fail) before polishing pixels. |
| Care about the back of the fence. | The parts nobody screenshots are what make it feel premium. | Loading, empty, error, offline, 404, emails, push copy and the 1,000th row get the same care as Home. |
| It just works. | Smart defaults instead of settings. | No setting is added if a good default exists. Nothing asks the user for information we can infer. |
| The whole widget. | Landing, app, emails and notifications feel like one product. | One token set, one voice, one icon style, one motion language everywhere. |
| Delight in the details. | Small moments, earned. | One signature moment (circuit closing); micro-interactions only where they confirm an action. |

From Apple's Human Interface Guidelines we also take three qualities:
- **Clarity:** text is legible at every size, icons are precise, every element has a purpose.
- **Deference:** the UI steps back so people's work and faces are the content. Chrome is
  neutral; colour is reserved for meaning.
- **Depth:** layers, translucent bars and physical motion show where you are and where
  you came from.

**Craftsmanship checklist (every screen, before it's "done"):** one job, one primary
action · aligned to the 4px grid · type only from the scale · colour only from tokens ·
all five states designed (loading, empty, error, offline, success) · works one-handed
at 375px · works with VoiceOver/TalkBack · tested on a real mid-range Android and an
iPhone · nothing on screen you could remove without losing meaning.

## 2. What we borrow, and what we refuse

| From | Borrow | Refuse |
|---|---|---|
| Instagram | Full-bleed visual posts; profile as a visual grid; messaging as a primary destination; physical, weighted motion; create button in the top bar so the bottom bar holds destinations | Circle "story" rings with gradient borders (instantly reads as a copy); infinite scroll with no end; public like and follower counts; filters that fake reality; algorithmic outrage |
| BeReal | Scarcity that creates meaning (the Daily Drop is finite); authenticity over polish (no beauty filters); a dark-first, content-first interface | Daily posting pressure; notifications that guilt you |
| Threads | Short text posts that feel light and quick; replies as conversation | Engagement-bait reposts |
| Read.cv / Posts.cv | Work-first profiles; calm, confident typography | Being so minimal it feels empty |
| LinkedIn | Nothing visual. We take only the idea of verified professional identity | Humblebrag feed, vanity metrics, recruiter spam |

## 3. Navigation

Mobile bottom bar (5 destinations, icons with labels):

`Home` · `Discover` · `Circuits` · `Inbox` · `Profile`

- **Top bar on Home:** `+` (create build log) on the left, the Circuit wordmark in the
  centre, notifications bell on the right (dot for unread, never a number over 9 → "9+").
- **Circuits** sits in the centre as our signature, like Instagram centres what it values most.
- Desktop (≥1024px): left rail with the same five destinations + create button; centre
  column max 600px for Home and Profile; ONE right rail (max 340px, 48px gap from the
  centre column) holding only the Daily Drop on Home. "People you may know" and nearby
  roles live in Discover, not on Home. Discover's map and the partner dashboard may use
  full width.
- **Swipe between tabs (mobile):** a horizontal swipe anywhere on the content area moves
  to the neighbouring tab in bar order (Home ↔ Discover ↔ Circuits ↔ Inbox ↔ Profile).
  The screen follows the finger 1:1 and the tab bar's selection indicator slides with it;
  release past 35% of the width or above 600px/s to commit, otherwise it snaps back.
  Rules so it never fights other gestures:
  - It only starts when the gesture begins outside a horizontally scrollable or swipeable
    element (Live wire, Daily Drop stack, media pager, chips rows, map, segmented
    controls). Those keep their own swipe.
  - Disabled on pushed (non-tab) screens, where a swipe from the left edge means Back,
    and whenever a sheet, menu or keyboard is open.
  - Disabled on Discover's Map segment (the map owns all gestures there).
  - The gesture must be clearly horizontal (angle under 30°) before it captures; vertical
    scrolling always wins otherwise.
  - Each tab keeps its scroll position and state when you swipe away and back.
  - Off when `prefers-reduced-motion` is set (tabs switch with a fade instead), and a
    "Swipe between tabs" toggle in Settings → Appearance can turn it off.
  - Tapping a tab still works; tapping the current tab scrolls it to the top.
- Partner admins get `Dashboard` in place of `Circuits` in the bar (Circuits moves into
  Profile → Activity); see "Partner home" in §4. Students under 18 see the same bar; Inbox
  only shows connections and organisation staff.
- **Feature flags change the bar, never grey it out.** A feature that is off for this
  member simply isn't there (no "coming soon", no disabled icons):
  - `circuits` off → four tabs: `Home` · `Discover` · `Inbox` · `Profile`; swipe order
    follows the visible tabs.
  - `pulse` off → no `+` in the top bar, no Live wire, no Pulse; Home is the Daily Drop
    followed by matches and nearby roles. `daily_drop` off → Home starts with matches.
  - `investor_mode` off → no investor role in onboarding or on the landing CTA (the
    /investors page shows the waitlist form instead; the landing site reads
    `/api/config` at build time). `partner_mode` off → partner home
    shows only the dashboard (F8).
  - `promotions` off → promoted slots don't exist; layouts must look complete without them.
  - A deep link to an off feature shows the normal 404 screen.

## 4. Core screens

### Landing site (one home, five front doors)
Same visual system as the app (brand emerald, the Bridge logo, Geist). Each page has
one job: get that audience into the app with their role pre-set.

| Page | Headline | Proof shown | Call to action |
|---|---|---|---|
| `/` | "Build with people near you." | Live counts for the pilot city (startups, open roles, circuits closed) — real numbers only, hidden until meaningful | Five audience tiles |
| `/students` | "Startups near you want your skills, not your college name." | Real roles near the pilot college with stipends in ₹ | "Find work near you" |
| `/founders` | "Find people who can help you — and students who want to work with you." | "Claim your startup" example card with student-interest count | "Claim your startup" |
| `/mentors` | "Help founders who need exactly what you know." | An example circuit (anonymised) | "Start mentoring" |
| `/investors` | "Three startups a day that fit your thesis. No noise." | An example "Today's picks" card | "Set your focus" |
| `/partners` | "See what your ecosystem is missing — and fix it." | A sample gap-map screenshot (demo data, labelled) | "Bring Circuit to your campus" (contact form + demo link) |

Layout per page: hero (headline, one subhead, one primary button), three short
"how it works" steps with real UI screenshots, one proof section, an FAQ of 4–6 honest
answers (including privacy and minors where relevant), footer. No stock photos, no
fake testimonials, no fake numbers. Mobile-first; Lighthouse ≥ 95.

### Sign-up and onboarding (one thing per screen)
The first two minutes decide whether someone stays. Every screen asks ONE thing, has
ONE primary button pinned at the bottom (50px, full width), and nothing else competing
for attention. Tone: minimalist meets professional Gen Z — short, confident, warm, no
corporate filler, no slang that will age.

Layout of every step: thin progress bar at the very top (no step numbers), a back
chevron top-left, a Large title question, one short subhead, the single input or
choice, then the primary button at the bottom above the keyboard. "Skip" appears as a
text button top-right only on optional steps. Pushed screens slide in from the right;
swipe from the left edge goes back. Answers save on every step, so closing the app
resumes exactly where you left off.

| # | Screen | Large title | The one thing | Notes |
|---|---|---|---|---|
| 1 | Welcome | "Build with people near you." | `Continue with Google` | Subhead: "Find work, collaborators and mentors who need what you're good at." Secondary text button: "Use email instead" (OTP). Legal line in Footnote: "By continuing you agree to the Terms and Privacy Policy." |
| 2 | Email code (only if email) | "Check your inbox." | 6-digit code field, auto-advance, paste supported | "Resend in 30s" text button. |
| 3 | Invite (only if BETA_MODE and no access) | "Got an invite code?" | Code field | Secondary: "Join the waitlist" → one-screen waitlist confirmation. Invite links prefill and skip this screen. |
| 4 | Name | "What should we call you?" | First and last name (prefilled from Google) | Most people just tap Continue. |
| 5 | Role | "What brings you here?" | Five large tappable rows: "Find work and internships" · "Build a startup" · "Mentor people" · "Invest" · "Run a college or incubator programme" | Choosing a row advances immediately (no extra Continue). Maps to role. |
| 6 | Age | "Are you 18 or older?" | Two large buttons: "Yes" / "Not yet" | "Not yet" sets is_minor, private profile and safety defaults; one Footnote line explains why we ask. |
| 7 | Where | "Where are you based?" | `Use my location` primary; "Choose a city" secondary | Stores a coarse location only; explains in one line. |
| 8 | Your work | "What are you working on?" | One large text field: "Paste your bio, LinkedIn About, or just tell us in a few lines." | The LLM turns it into chips on the next screen. Skip allowed (goes to manual pickers). |
| 9 | You offer | "Here's what you can offer." | Suggested capability chips, pre-selected, tap to remove; "+ Add" opens search | Max 5. If the LLM fails: a searchable chip list, no error shown. |
| 10 | You need | "And what you need right now." | Same chip pattern for needs | Max 3. |
| 11 | Organisation (students, partners; skipped if detected) | "Where do you study?" (or "Which programme?") | Search field with college/organisation results | Auto-filled and skipped when the verified email domain matches an organisation. "Not listed" is fine. |
| 12 | Photo (optional) | "Add a photo." | Large circle; tap to choose; `Continue` | Skip allowed; re-prompted once later. Shows the circuit-pattern avatar as the placeholder. |
| 13 | Make it yours (optional) | "Pick your colour." | The six accent swatches with a live preview | Skip keeps Emerald. |
| 14 | Ready | "You're on the circuit." | `See today's drop` | Short reveal of the first Daily Drop card (matches computed on the spot for new members, from precomputed candidates). |

**Investor branch.** Choosing "Invest" at step 5 replaces steps 8–11 with:

| # | Screen | Large title | The one thing | Notes |
|---|---|---|---|---|
| 8i | Focus | "What do you invest in?" | Sector chips from our fixed sector list (pick up to 5) | Popular sectors for the city shown first; search for the rest. |
| 9i | Stage | "Which stages?" | Multi-select rows: Idea · Pre-seed · Seed · Series A+ | One tap each, `Continue` at the bottom. |
| 10i | Cheque (optional) | "Typical cheque size?" | Ranges in ₹: under ₹5L · ₹5–25L · ₹25L–1Cr · ₹1Cr+ | Skip allowed. Never shown publicly. |
| 11i | Verify | "Help founders trust you." | One link field: LinkedIn, AngelList or fund website | Reviewed by a super admin for verification level 3. Until verified, investors can browse picks but can't request intros. |

Then photo, colour, and step 14 becomes "Your first picks are ready." → `See today's picks`.
Investors are never asked for a bio, offers or needs; their offers are set to
"Funding" and "Investor network" automatically and editable later.

**Partner branch.** Choosing "Run a college or incubator programme" at step 5 replaces
steps 8–11 with:

| # | Screen | Large title | The one thing | Notes |
|---|---|---|---|---|
| 8p | Type | "What do you run?" | Rows: College · Incubator · Accelerator · Coworking space · Government programme · Corporate programme | Advances on tap. |
| 9p | Organisation | "Which organisation?" | Search existing organisations; "Add a new one" (name + website) | Joining an existing org sends a request to its current admin. |
| 10p | Verify | "Confirm you're from {org}." | Work email on the org's domain (OTP) | If no matching domain: website link + "We'll check within 1 working day." Admin powers unlock after verification. |
| 11p | Goal | "What do you want to do first?" | Rows: Invite my startups · Invite my students · Post a call for applications · See my ecosystem's gaps | Lands them on that action after onboarding. |

Then photo (org logo), colour, and step 14 becomes "{Org} is on the circuit." → the
chosen first action. Partners are never asked for a bio, offers or needs.

Rules:
- Links that carry `role` skip step 5; invite links that carry an organisation skip
  step 11 / 9p; invite codes skip step 3.
- Target: Welcome to first Daily Drop card in under 2 minutes; most screens take one tap.
- Never ask for anything we can infer (name from Google, organisation from email domain,
  city from location).
- No account details beyond these steps during onboarding: headline, highlights,
  GitHub and proof of work are invited later from Profile (profile strength meter).
- Consent: the legal line on Welcome plus a stored consent record; under-18 students
  also see one plain-language screen about safety defaults before step 7.
- Errors are inline, one sentence, and never clear what the person typed.
- Every step works with VoiceOver/TalkBack and with the keyboard on desktop.
- Desktop: the same steps in a centred 440px column; Enter submits.

### Home
1. **Live wire** (top of Home; replaces any "stories" pattern). This is Circuit's own
   idea, not a copy of Instagram stories. A single thin horizontal trace line (1.5px,
   `border` colour) runs across the top of the feed like a circuit board track. Along it
   sit **nodes**: rounded-square (12px radius) 44px thumbnails, each with a verb label
   under it in Caption size — `shipped`, `hiring`, `needs`, `joined`, `closed a circuit`.
   - The node image is the most relevant visual of the update (a build log's first image,
     a startup logo, a circuit mini-ring), with the person's 20px avatar overlapping its
     bottom-right corner. Never a big initials circle.
   - Unseen nodes are "powered": the node gets a 2px `current` outline and a small dot of
     current travels along the trace into it (§7). Seen nodes are dimmed to 60% opacity.
   - Order: updates most relevant to you first (shared capabilities, mutuals, distance),
     max 12 nodes; if none: the trace line shows "Quiet on the wire today" and one action.
   - Tap a node: a full-screen **Update view** (not a story viewer): the image, one line
     of what happened, why it matters to you ("You both build with Kotlin · 3 km away"),
     and one action (`Intro me`, `View role`, `Reply`). Swipe left/right between updates.
2. **Daily Drop** (card stack, 3 cards per day, refreshed at 8:00 local time). The card
   leads with the REASON, not a giant avatar:
   - Top: "Sakthi can help you with **mentoring**" in Title size, with the capability in
     semibold `text`. Below: the mutual connection ("via Meera, mentor") with both tiny avatars.
   - Middle: their photo (or their best build log image) at 4:3, then name, verification
     badge, headline, place.
   - Chips: up to 3 of what they offer that you need.
   - Match strength as words, never a raw low percentage: `Strong match` (score ≥ 0.75),
     `Good match` (≥ 0.55); below 0.55 they don't appear in the drop at all.
   - A "Bridge match" badge when cross-sector. Actions: `Intro me` and `Skip`; swipe
     right/left; buttons always present.
   After the third card: "That's today's drop. New one tomorrow at 8."
3. **Pulse** (vertical feed below), mixing, in this order of priority:
   - Build logs from your connections, followed startups and organisation
   - New roles near you that match your skills
   - Circuit completed ("Asha, Priya and Arjun closed a circuit"), intros that worked,
     startups newly claimed nearby
   - ("Skills in demand near you" lives at the top of Discover → Jobs, not in Pulse)
   Pulse is chronological within the last 7 days, not engagement-ranked. When you reach
   content you've seen: "You're caught up." with a suggestion (explore Discover). No
   infinite scroll beyond that.

### Investor home (calm by design)
Investors want signal, not noise. Their Home is the same structure with a quieter,
fixed rhythm:
1. **Today's picks** (replaces the Daily Drop): 3 startups per day at 08:00 IST that fit
   their focus, stage and city. Each card leads with the fit ("Seed-stage healthtech in
   Coimbatore, shipping weekly"), then the startup's best build log image, name,
   verification, stage, team size, and up to 3 traction signals (recent build logs,
   roles posted, verified founders). Actions: `Request intro` and `Pass`. After 3:
   "That's today's picks. New ones tomorrow at 8."
2. **Pulse, filtered:** only build logs and updates from startups in their focus that are
   open to investors, plus startups they follow. No student posts, no job ads, no
   promotions in an investor's Pulse.
3. **Live wire, filtered:** startups in focus that shipped, hired or closed a circuit.
- A pick never repeats within 30 days unless the startup posts a meaningful update.
- Founders control this completely: a startup only appears to investors if its founder
  turned on "Open to investor conversations" (off by default), and can turn it off any
  time. Fundraising status is shown only if the founder sets it.
- Intro requests from investors go to the founder, who accepts or declines; contact
  details are never shown before acceptance. Warm paths ("via Meera, mentor") are
  suggested first.
- Investors can change their focus any time in Profile → Investing; picks update the
  next morning (never mid-day, so the feed stays stable).

### Partner home (colleges, incubators, programmes)
Partners use Circuit to run their ecosystem. Their tab bar is Home · Discover ·
Dashboard · Inbox · Profile (Dashboard replaces Circuits). Home shows, in order:
1. **Needs your attention:** applications to review, RSVPs nearing capacity, cohort
   invites pending — each a row with one action.
2. **Cohort health:** three numbers (active members this week, intros accepted,
   placements/hires) with a small trend, aggregates only.
3. **Open calls and upcoming events** as cards.
4. **Pulse filtered to their cohort and members** (build logs from cohort startups first).
Primary action on Home: `New` (opens a sheet: Call · Event · Announcement · Invite).

### Organisation page
Public profile for each organisation: logo, name, kind, city, verification badge, about,
open calls, upcoming events, cohort startups (only those who agreed to be listed), and
`Follow`. Members of the org see a "Your organisation" badge.

### Calls and events (cards and pages)
- **Call card:** organisation, kind (Programme / Internship drive / Challenge), title,
  deadline in plain words ("Closes in 5 days"), sectors, `Apply`. Applying is a short
  one-thing-per-screen form (max 5 questions set by the partner).
- **Event card:** date block (day + month in Geist Mono), title, venue or "Online",
  going count shown only to the organiser, `RSVP`. Event page adds the agenda and a
  calendar add.
- Partner items in Pulse carry "From {org}" in Footnote `text-muted` and are capped at
  1 per 10 items. They are not promotions and are never paid placements.

### Build log (post)
- Media: up to 4 photos or screenshots (portrait 4:5 or square 1:1), shown full-bleed
  edge to edge with a dot pager. Video is not in v1.
- Text: up to 500 characters; first 2 lines visible, "more" expands inline.
- Tags: capabilities from our fixed list (max 3, shown as chips), optional link
  (GitHub, live demo, Figma, etc.) shown as a clean link card.
- Header: avatar, name, verification badge, headline, place, time ("2h").
- Reactions (no public counts to others; the author sees totals privately):
  `Helpful` · `Intro me` · `Let's talk`. "Intro me" and "Let's talk" open the intro or
  message flow. Replies are threaded one level deep, max 300 characters.
- Composer: big media area first, then text, then capability chips; crop only, no
  filters; "Who can see this": Everyone / Connections / My organisation. Under-18
  default: My organisation, and public posting is off until age is verified.

### Discover
Tabs: `People` · `Startups` · `Jobs` · `Map`
- People and Startups: a 2-column visual grid (photo-first cards with name, headline,
  match %), filters in a bottom sheet (capability, distance, role, verified only).
- Jobs: list with startup logo, role, stipend in ₹, distance, match %; job page with a
  sticky `Apply` button.
- Map: the existing MapLibre map, full-screen, pins by hiring status; tapping a pin opens
  a bottom sheet with the startup card (name, sector, distance, hiring summary, skill match).
  The pin tap itself never navigates (accidental taps while panning). The sheet's primary
  action for a hiring startup is `See open roles`: it opens the Startup page scrolled to
  its Hiring section, or the job page directly when the startup has exactly one open role.
  Non-hiring startups show `Follow` instead. Back returns to the map with the same pin
  selected and the same zoom.
- Search field at the top of Discover searches all four.

### Startup page
Reached from the map sheet, Discover → Startups, job pages and Pulse.
- Header: logo (or circuit-pattern square), name, verification/claimed state, sector,
  stage, team size, place and distance. Unclaimed startups show "Unclaimed · from public
  sources" in Footnote and, to signed-in founders, `Claim this startup`.
- Primary action: `Follow` (or `Following`). One primary only.
- **Hiring** (first section when hiring): open roles as rows (role, stipend in ₹ in Geist
  Mono, type, skill match in words), each opening the job page; "Not hiring right now"
  with `Follow for updates` otherwise. `See open roles` and deep links land here.
- About, build logs grid, founders (with `Intro via a mutual` when a warm path exists),
  and for investors only (when the startup opted in) stage and fundraising status.
- No public follower counts; founders see their own interest and view counts privately.

### Circuits (signature screen)
- Active and proposed circuits as large cards: three avatars on a ring connected by the
  circuit line, three "who helps whom" lines, time left to respond.
- Accept / Decline as two clear buttons. When others accept, their segment of the ring
  lights up live. When all three accept, the ring closes with the signature animation
  (§7) and a short line: "Circuit closed. You help Priya with fundraising."
- History: completed circuits as a grid of small rings on the profile.
- Empty state: an illustrated empty ring and "Add what you need and what you can offer to
  join this week's round."

### Inbox
- Two folders: `Chats` (connections) and `Requests` (intros and first messages from
  non-connections, which must be accepted first). Students under 18: no Requests from
  strangers at all.
- Chat bubbles, read receipts optional (off by default), image sharing, report/block in
  the header menu.

### Profile
- Header: large avatar (or a cover photo for startups), name, verification badge,
  headline, place, organisation; `Needs` and `Offers` as two rows of chips.
- Actions: `Connect` (or `Follow` for startups), `Message`, `Intro via a mutual` when a
  warm path exists ("via Meera, mentor").
- Highlights: up to 6 pinned projects as rounded tiles.
- Tabs: `Build logs` (3-column grid of first images) · `Circuits` · `About` (skills,
  proof of work links, GitHub summary when connected).
- No public follower or connection counts. Show "12 mutual connections" only.
- Profile strength meter visible only to the owner, with one next step.

### Notifications
Grouped by day. Only these types: intro requests and responses, messages, circuit
proposals and status changes, application status changes, replies to your build logs,
someone you know posted for the first time this week (max one per day). Never "X people
viewed your profile" more than once a week.

### Promoted items (F19)
- Look like the normal card of their type (startup, role, build log) so they feel native,
  but always carry a "Promoted" label in Footnote size, `text-muted`, top-left, plus the
  startup name. Never styled to look like a match, a Daily Drop card or a Live wire node.
- The "…" menu on a promoted item has `Why am I seeing this?` (one sentence: "Promoted to
  people in Coimbatore interested in Android development") and `Hide this`.
- Placement: Pulse (never first, max 1 per 8 items), top of Discover → Startups and
  Jobs (one slot, below the search field). Never in the Daily Drop, Live wire, Circuits,
  Inbox, Profile, applicant lists or the partner dashboard.
- Founders get a simple "Promotion results" card on their startup page: impressions,
  taps and applications per day, as plain numbers.

## 5. Visual system

### Colour: "Emerald" (dark-first, light supported)
Circuit's brand colour is **emerald**. It fills the one primary button on each screen and the
app icon. A brighter emerald, **Current**, marks anything live or active (it's the
electricity in the circuit). **Bridge** (indigo) marks cross-sector matches. Everything
else is neutral, so people's photos and work stay the loudest thing on screen. The dark
theme is true black with faintly green-tinted surfaces; the light theme is a soft lavender grey.

| Token | Dark | Light | Use |
|---|---|---|---|
| `bg` | `#000000` | `#C2BCC8` | App background (true black on OLED) |
| `bg-grouped` | `#000000` | `#C2BCC8` | Behind grouped lists and settings |
| `surface` | `#08140F` | `#D2CDD7` | Cards, sheets, grouped rows |
| `surface-2` | `#0E2019` | `#B3ACBA` | Inputs, chips, placeholders, segmented-control track |
| `surface-3` | `#1B382D` | `#D2CDD7` | Selected segment, pressed states, elevated controls |
| `separator` | `rgba(255,255,255,0.10)` | `rgba(18,3,9,0.12)` | Hairlines (0.5px on retina, 1px otherwise) |
| `text` | `#F3EEF5` | `#120309` | Primary text |
| `text-muted` | `#A79FAD` | `#4A4150` | Secondary text |
| `text-subtle` | `#8A8390` | `#4A4150` | Tertiary text, timestamps, placeholders |
| `primary` | `#00563F` | `#00563F` | Primary button fill (one per screen), selected chips, own chat bubbles, app icon |
| `on-primary` | `#FFFFFF` | `#FFFFFF` | Text/icon on primary |
| `current` | `#2FBF8A` | `#00563F` | Live and active: powered Live wire nodes, unread dots, focus rings, progress bars, hiring pins, accepted/completed states, links |
| `bridge` | `#8E8CFF` | `#3B2F9E` | Bridge match badge and bridge UI only |
| `warning` | `#FFB340` | `#6A3800` | Expiring soon |
| `danger` | `#FF453A` | `#8F0016` | Destructive actions, errors |

Measured contrast (WCAG): white on `primary` 8.7:1; `current` on black 8.9:1 and on
lavender 4.7:1; body text 16.4:1 (dark) and 10.9:1 (light); `text-subtle` on dark
`surface` 5.1:1; warning and danger pass 4.5:1 in both themes. Deep `#00563F` on black is only 2.4:1, which is why dark mode uses the
brighter `#2FBF8A` for dots, rings and links, never the deep emerald.

### Logo: "The Bridge"
An arch joining two people (two nodes), with a smaller node at the top for the mutual
connection between them: a warm intro and a bridge match in one shape. Wordmark:
lowercase `circuit` in Geist Semibold, tracking -0.035em, mark to the left.
- App icon: white mark on `primary` `#00563F`, rounded square (the platform mask wins).
- On black: mark in `#2FBF8A`, wordmark `#F3EEF5`. On lavender or white: mark `#00563F`,
  wordmark `#120309`. One colour only, never a gradient, outline or shadow.
- Node gaps are cut with the background colour (a 4-unit ring in a 100-unit box), so the
  mark always sits on a flat background.
- Minimum size 20px (mark) / 88px wide (lockup); clear space = the top node's diameter.
- Source: `docs/design-reference/Brand.dc.html`. [YOU] run a trademark search in India
  before public launch.

### Personal accent (members choose their Current colour)
Members can choose the colour that plays the `current` role for them. It's personal
expression with guardrails: it only changes `current` (live states, unread dots, focus
rings, links, powered Live wire nodes) and the signature gradient. Primary buttons stay
brand emerald and status colours never change, so the app stays coherent.

| Accent | Dark | Light | Bridge colour while selected |
|---|---|---|---|
| Emerald (default) | `#2FBF8A` | `#00563F` | Indigo `#8E8CFF` / `#3B2F9E` |
| Sky | `#5AC8FA` | `#004E8C` | Indigo |
| Indigo | `#8E8CFF` | `#3B2F9E` | Emerald `#2FBF8A` / `#00563F` (swapped so Bridge stays distinct) |
| Rose | `#FF6482` | `#8A1238` | Indigo |
| Lime | `#B6E85A` | `#285004` | Indigo |
| Mono | `#F3EEF5` | `#120309` | Indigo |

- Only these six; no free colour picker (every light value is ≥4.5:1 on `#C2BCC8` and
  every dark value ≥3:1 on black; recheck if any value changes).
- Chosen in Settings → Appearance (with a live preview of a Live wire node, a Bridge
  badge and a link) and offered once, optionally, at the end of onboarding.
- Stored on the member (`appearance.accent`) so it follows them across devices; applied
  before first paint (no flash of the default colour).
- Mono: live states also use shape and weight (filled dot, semibold) so nothing relies on
  colour alone.
- Danger and warning are fixed and never selectable.
- The landing site, emails and the logo always use brand emerald.

**Signature gradient (the only gradient allowed):** `current → bridge`, using the
member's accent and its paired Bridge colour (default `#2FBF8A → #8E8CFF` dark,
`#00563F → #3B2F9E` light) at 135°. Used ONLY for the circuit ring and its closing
animation. Never on the logo or app icon.

### Materials (iOS-style translucency, used systematically)
- Top bars, tab bar and sheet headers use a translucent material: `bg` at 72% opacity
  + `backdrop-filter: blur(20px) saturate(180%)`, with a `separator` hairline.
- Fall back to solid `bg` when `backdrop-filter` is unsupported, when
  `prefers-reduced-transparency` is set, or when the device reports data-saver /
  low memory. Never use translucency on cards or content.

### Typography
- Family: **Geist** for everything (one brand voice on iPhone, Android and desktop);
  **Geist Mono** only for numbers that matter (stipend, distance, dashboard figures).
  Self-hosted, subset, 3 weights (400 regular, 500 medium, 600 semibold).
- Scale (iOS-style, px, mobile; desktop +2 on Large title and Title 1 only):
  Large title 34/600 · Title 1 28/600 · Title 2 22/600 · Title 3 20/500 ·
  Headline 17/600 · Body 17/400 · Callout 16/400 · Subhead 15/400 · Footnote 13/400 ·
  Caption 12/400.
- Tracking: −0.022em at 28px and up, −0.012em for 20–22px, 0 for body, +0.01em for
  12–13px. Line height 1.2 for titles, 1.4 for body.
- Sentence case everywhere. Left-aligned text. Names and numbers are the loudest things
  on a card.

### Breathing room (this is what "premium" means here)
Colour doesn't make Circuit feel like Apple; space, restraint and hierarchy do. When a
screen feels cramped, remove something before you shrink anything. These are hard rules,
checked in review and by the `premium` Playwright checks (§13). The reference
mock is the "Circuit app design" canvas (Home, Discover, Inbox, Profile, desktop Home):
- **Fewer things per screen.** Home on mobile shows at most 3 distinct blocks before the
  first scroll (e.g. large title, Live wire, Daily Drop card). Desktop: at most 2 columns
  of content (centre column + one rail), never 3 competing ones.
- **No boxes around everything.** Feed items (build logs, roles, activity) are NOT
  bordered cards: they sit directly on `bg`, separated by 32px of space and one full-width
  hairline. Only the Daily Drop card, sheets and grouped settings lists get a surface.
  Never a border AND a background on the same element.
- **Section spacing:** 40px between sections on mobile, 56px on desktop. Section headers
  are Title 3 with 12px below. Inside a surface: 20px padding mobile, 24px desktop.
- **Rows:** list rows min 56px tall (64px with a subtitle), 16px between avatar and text.
- **Line length:** body text max 60 characters per line (centre column max 600px, text
  max 540px); reasons and bios never truncate mid-sentence: show 2 full lines, then
  "more".
- **One loud thing per block.** Each block has one element in Headline/Title weight; the
  rest is Body or Subhead in `text-muted`. Max 5 type sizes per screen (normally
  34 Large title, 22 Title 2, 17 Body/Headline, 15 Subhead, 12 Caption).
- **Accent budget:** the accent (`current`) appears on at most 2 kinds of element per
  screen (e.g. unseen Live wire nodes + unread dot). Never on buttons (they use `primary`), card backgrounds,
  large icons or headlines. If you can see accent in more than ~3 places in one
  viewport, it's too much.
- **One primary button per screen**, brand emerald (`primary`) with white text. Everything else is a secondary
  (`surface-2` fill) or a text button. On the Daily Drop: `Intro me` is primary,
  `Skip` is a text button.
- **Media:** images are calm. Generated circuit-pattern avatars and placeholders use only
  greys (`surface-2`/`surface-3` with `text-subtle` traces) plus at most a thin accent
  line; no brown, olive or saturated fills. Daily Drop media max 200px tall on desktop.
- **Edges:** horizontal rows (Live wire) end with a soft 32px fade at the screen edge,
  never a half-cut item with a border.
- **Large titles:** every tab screen starts with a Large title (`Today`, `Discover`,
  `Circuits`, `Inbox`, profile name) with 8px above the first block; it collapses into
  the translucent top bar on scroll (iOS behaviour).

### Space, shape, depth
- 4px base grid; common steps 4, 8, 12, 16, 24, 32, 48.
- Screen side padding: 16px mobile, 24px desktop.
- Radius: 14px cards, 12px buttons and inputs, 10px grouped-list sections, 22px sheet
  top corners, 999px chips and avatars, 0 for full-bleed media.
- Primary and secondary buttons are 50px tall on mobile, full width at the bottom of
  forms and sheets; text buttons for tertiary actions.
- Depth comes from layering, translucency and motion, not heavy shadows: one soft shadow
  for sheets and the Daily Drop stack only (`0 12px 40px rgba(0,0,0,.45)` dark, `.10` light).

### iOS-quality patterns (mobile)
- **Large titles** on top-level screens (Home excepted) that collapse into a centred
  inline title on scroll, with the translucent bar appearing as content passes under it.
- **Grouped inset lists** for settings, profile About and account screens.
- **Sheets with detents** (medium and large), a grabber, drag-to-dismiss and the page
  behind scaling to 0.94 with a dimmed backdrop.
- **Edge swipe back** on pushed screens; pull-to-refresh on feeds.
- **Long-press context menus** on posts, people and messages, always mirrored by a
  visible "…" button.
- **Segmented controls** instead of tabs inside a screen.
- **Press states:** scale 0.97 and 80% opacity within 100ms; no colour flash.
- **Safe areas** respected everywhere; content never sits under the home indicator.
- Haptics via the Vibration API where supported (Android); iOS web has none, so every
  confirmation must also be visual.

### Imagery
- Real people and real work, full-bleed. No stock photos, no 3D blobs, no AI art.
- Real users are asked for a photo during onboarding (skippable, re-prompted once).
- Avatars without a photo: a deterministic geometric "circuit pattern" (traces and nodes
  drawn from a hash of the member id, in 2 of the 8 muted tones) with the first initial
  small in a corner. Never a big initials-only circle, never a silhouette.
- Startup cards without a logo: the same pattern style, squared, with the name beside it.
- Build log images must look like real work: real UI screenshots with readable text and
  data, code, hardware, whiteboards, event photos. Grey skeleton bars inside an image are
  banned — they read as a broken loading state.
- Demo/seed imagery: render each persona's project as a believable, specific screen
  (e.g. a Kannada voice-assistant app with real labels, an inventory dashboard with real
  numbers in ₹) from HTML/SVG mockups. No stock photos and no AI-generated people.

### Iconography
- One outline icon set (Lucide), 1.75px stroke, 24px in the tab bar, 20px elsewhere.
- Icons always paired with a label in navigation and primary actions.

## 6. Components (packages/ui)
TabPager (swipeable tabs with gesture rules from §3), AccentPicker (six swatches with
live preview), ThemeProvider (theme + accent as CSS variables, set before first paint),
Avatar (photo or circuit pattern), Badge (verification 1–3, Bridge, Hiring, Under-18
private), Button (primary, secondary, ghost, destructive; 48px tall on mobile), Chip
(selectable, removable), Card (person, startup, job, build log, match, circuit),
LiveWire (trace + nodes), UpdateView, MatchStrength (words, not %), DropStack, PostComposer, MediaPager, ReactionBar, ReplyThread,
BottomSheet, Modal, Tabs, SegmentedControl, SearchField, Toast (with undo), Skeleton,
EmptyState (illustration + one sentence + one action), CircuitRing (animated).

## 7. Motion

Principles (from Instagram's motion system): elements have weight, entrances are
staggered, movement follows physics, and the UI layers like paper in light.

| Interaction | Spec |
|---|---|
| Default spring (iOS feel) | `{ type: "spring", duration: 0.35, bounce: 0 }` — fast, no overshoot |
| Push / pop between screens | slide 100% from the right with the previous screen moving −30% and dimming; `duration: 0.4, bounce: 0` |
| Sheets | `duration: 0.45, bounce: 0.1`; page behind scales to 0.94; drag-to-dismiss with velocity |
| Large title collapse | tied to scroll position (no time-based animation) |
| Card stack swipe | follows finger 1:1; rotates up to 8°; throw threshold 30% width or 800px/s |
| List entrance | fade + rise 12px, 40ms stagger, first 8 items only |
| Tab switch (tap) | content slides 24px + fades in the direction of the tab, `duration: 0.3, bounce: 0`; indicator slides with the same spring |
| Tab swipe (mobile) | 1:1 with finger; commit at 35% width or 600px/s; settle `duration: 0.35, bounce: 0`; neighbouring screen is pre-rendered so there's no blank frame |
| Accent change | all `current` uses crossfade to the new colour over 250ms |
| Live wire current | on load, a 6px `current` dot travels along the trace from left to each unseen node (600ms, ease-out, 80ms stagger), then the node outline lights; plays once per session, not on every scroll |
| Node "seen" | outline fades out and node dims to 60% over 300ms after the Update view closes |
| Reaction tap | icon scales 1 → 1.25 → 1 in 220ms; light haptic where supported |
| **Circuit closing (signature)** | the three ring segments draw in sequence (3 × 300ms), the gradient sweeps once around (600ms), avatars pulse once; total ≤ 1.6s; plays once per circuit |

- Animate only transform and opacity. 60fps on a mid-range Android or it gets simpler.
- `prefers-reduced-motion`: replace all motion with 150ms fades; the circuit closing
  becomes a static closed ring with a checkmark.
- Library: `motion` (Framer Motion for React).

**Landing site motion** (same principles, one orchestrated moment per page):
- Hero: headline words rise 16px and fade in with a 60ms stagger (total ≤ 700ms), then
  the logo video starts; the page is fully readable at rest before any of it runs.
- Bridge line: a thin `current` arch draws once between "How it works" steps as they
  enter the viewport (stroke-dashoffset, 900ms), connecting step 1 → 2 → 3.
- Scroll reveals: sections fade + rise 12px when they enter (once, 40ms stagger, first
  6 items); content starts visible if JavaScript or IntersectionObserver is missing.
- Audience tiles: hover/focus lifts 2px and the arrow nudges 4px; press scales to 0.98.
- Buttons: press scale 0.97 with the default spring. FAQ: height animates with the
  default spring, the + rotates to ×.
- No parallax, no scroll-jacking, no looping background motion besides the hero video;
  Lighthouse ≥ 95 mobile still applies; reduced motion = everything static.

## 8. Healthy habit rules (non-negotiable)
- The Daily Drop is finite (3 per day). Pulse ends with "You're caught up."
- No public like, follower or view counts. Authors see their own totals privately.
- No streaks, no "you haven't posted in X days", no guilt notifications.
- Notifications: max 3 push per day by default; quiet hours 22:00–08:00 IST by default;
  every notification type can be turned off.
- Under-18: private by default, organisation-only posting, no Requests from strangers,
  no appearance in public Discover until age is verified and the student opts in.
- Every post and profile has Report and Block within two taps.
- Promotions never pretend to be recommendations, never interrupt (no pop-ups or
  full-screen ads), and are capped per §4 "Promoted items".

## 9. Voice and copy
- Plain, warm, specific. Write like a helpful senior from your college, not a brand.
- Indian context by default: ₹ stipends, real cities and neighbourhoods, IST times,
  names from across India.
- Do: "Riya is building a Kannada voice assistant and needs a backend dev." /
  "3 startups within 5 km are hiring React interns." / "You're caught up."
- Don't: "Unlock your potential", "Supercharge your network", "Revolutionise",
  "Seamless", "AI-powered", exclamation marks in system copy.
- Empty states: one sentence that explains, one action that helps.
- Errors: what happened + what to do ("Couldn't load jobs. Check your connection and
  pull to refresh.").

## 10. Accessibility
- WCAG AA contrast in both themes; tap targets ≥ 44px.
- Every swipe has a button alternative; every icon-only control has a label.
- Images in build logs require alt text (composer suggests it; author can edit).
- Full keyboard support on desktop; visible focus rings (2px `current`).
- Screen reader order matches visual order; the Live wire is a labelled list
  ("Harini shipped a build log, 4 hours ago").

## 11. Performance (budget Android phones, slow 4G)
- App initial JS < 250KB gzipped; route-level code splitting; map and dashboard lazy.
- Images: AVIF/WebP via Supabase Storage transforms, responsive sizes, blur placeholders,
  lazy below the fold. Max upload 4 images × 5MB, resized client-side to 1440px.
- Feed: virtualised list; prefetch the next 5 items' images only.
- Skeletons for every loading state; no spinners for content.
- Lighthouse mobile ≥ 90 on Home, Discover and Profile.

## 12. Banned (never ship these)
- Any gradient other than the signature gradient, and the signature gradient anywhere
  outside the circuit ring and its closing animation (never on the logo or app icon)
- Instagram-style circular story rings with gradient borders, or anything that looks
  like a copy of another app's signature pattern
- Initials-only avatars as the main visual of a card (Daily Drop, Live wire, Discover)
- Grey skeleton bars used as content inside images or cards (skeletons are for loading only)
- Raw match percentages below 55%, or any number that makes a recommendation look weak
- Glassmorphism on cards or content, neon glows, blurred blobs, aurora backgrounds (translucent system bars per "Materials" are the only blur allowed)
- Primary buttons in any colour other than brand emerald; the bright `current` on a button; orange or warm accent colours; the logo recoloured, outlined, gradient-filled or redrawn
- Emoji as icons; sparkle icons; "AI-powered" labels
- Stock photos, lorem ipsum, "John Doe", fake stats, placeholder logos
- Public follower/like counts; infinite feeds without an end; streaks
- Centred body text; more than one primary button per screen; heavy drop shadows
- Animations that don't explain a change
- Bordered cards for feed items; three content columns on desktop; truncated reasons
  ("You have a…"); muddy or saturated placeholder art; accent on buttons or headlines

## 13. Process
1. Build packages/ui and the Home screen first; show screenshots at 375px (dark and
   light) and 1280px before building anything else.
2. For each new screen, state in one sentence what the user is trying to do and what the
   single most important element is, then build it.
3. After each screen, critique the screenshot against this file and the banned list;
   fix, then show before/after.
4. Test on a real mid-range Android phone before calling a screen done.
5. `premium` Playwright checks (apps/app/tests/premium.spec.ts) run on every tab screen at
   375px and 1280px and fail the build when: more than one primary button is visible;
   a feed item has both a border and a background; section gaps are under 40px (mobile)
   or 56px (desktop); body text lines exceed 600px; more than 5 font sizes are used; the
   `current` colour is used on more than 2 kinds of element or on any button, or a
   primary button is not `primary`; text is
   truncated mid-sentence with an ellipsis.

---
Research references: Instagram's current tab layout and the reasoning behind it
(DMs and Reels as primary destinations, create moved to the top bar); Instagram's
motion system (weight, physics, staggered timing, layering); Instagram's brand refresh
(full-bleed real imagery, a single signature gradient used sparingly); BeReal's design
(scarcity and authenticity creating meaning without pressure).
