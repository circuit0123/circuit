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

## 2. What we borrow, and what we refuse

| From | Borrow | Refuse |
|---|---|---|
| Instagram | Full-bleed visual posts; a circle strip at the top (Today); profile as a visual grid; messaging as a primary destination; physical, weighted motion; create button in the top bar so the bottom bar holds destinations | Infinite scroll with no end; public like and follower counts; filters that fake reality; algorithmic outrage |
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
  column max 600px for Home and Profile; right rail with the Daily Drop, nearby roles and
  "people you may know". Discover's map and the partner dashboard may use full width.
- Partner admins get a sixth destination, `Dashboard`, replacing `Circuits` in the bar
  (Circuits moves into Profile → Activity). Students under 18 see the same bar; Inbox
  only shows connections and organisation staff.

## 4. Core screens

### Home
1. **Today strip** (top, horizontal circles, 64px): people you're connected to, startups
   you follow and your organisation, who posted a build log or a role in the last 24h.
   Unseen = signature ring; seen = thin neutral ring. Tap opens a full-screen viewer;
   tap right/left to move, swipe down to close.
2. **Daily Drop** (card stack, 3 cards per day, refreshed at 8:00 local time):
   each card is a person or startup with a large photo, name, headline, verification
   badge, the one-line match reason, a "Bridge match" badge when cross-sector, and two
   actions: `Intro me` and `Skip`. Swipe right = intro, left = skip; buttons always present.
   After the third card: "That's today's drop. New one tomorrow at 8."
3. **Pulse** (vertical feed below), mixing, in this order of priority:
   - Build logs from your connections, followed startups and organisation
   - New roles near you that match your skills
   - Circuit completed ("Asha, Priya and Arjun closed a circuit"), intros that worked,
     startups newly claimed nearby
   - A "Skills in demand near you" card at most once per day
   Pulse is chronological within the last 7 days, not engagement-ranked. When you reach
   content you've seen: "You're caught up." with a suggestion (explore Discover). No
   infinite scroll beyond that.

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
  a bottom sheet with the startup card.
- Search field at the top of Discover searches all four.

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

## 5. Visual system

### Colour (dark-first, light supported)
| Token | Dark | Light | Use |
|---|---|---|---|
| `bg` | `#0B0B0E` | `#FAFAF7` | App background |
| `surface` | `#15151A` | `#FFFFFF` | Cards, sheets |
| `surface-2` | `#1E1E25` | `#F1F0EC` | Inputs, chips |
| `border` | `#2A2A33` | `#E3E1DB` | Hairlines (1px) |
| `text` | `#F5F4F0` | `#121215` | Primary text |
| `text-muted` | `#A3A1A8` | `#5E5C63` | Secondary text |
| `accent` | `#FF5A36` | `#E8431F` | Primary action only (one per screen) |
| `bridge` | `#7C5CFF` | `#5B3DF0` | Bridge match badge and bridge-related UI only |
| `success` | `#2ECC8F` | `#14A36B` | Accepted, hired, completed |
| `warning` | `#FFB020` | `#C98200` | Expiring soon |
| `danger` | `#FF4D5E` | `#D92D3E` | Destructive, errors |

**Signature gradient (the only gradient allowed):** `#FF5A36 → #FF2E93 → #7C5CFF`
at 135°. Used ONLY for: unseen Today-strip rings, the circuit ring and its closing
animation, the app icon. Never on buttons, backgrounds or text.

Contrast: all text meets WCAG AA on its background in both themes.

### Typography
- Family: **Geist** (open source) for everything; **Geist Mono** only for numbers that
  matter (match %, stipend, distance, dashboard figures). Self-hosted, subset, 2 weights
  (400, 600).
- Scale (mobile / desktop): Display 32/40, Title 22/24, Headline 17/18, Body 15/16,
  Caption 13/13, Micro 11/11. Line height 1.35 for body, 1.15 for display.
- Sentence case everywhere. Left-aligned text. Names and numbers are the loudest things
  on a card.

### Space, shape, depth
- 4px base grid; common steps 4, 8, 12, 16, 24, 32, 48.
- Screen side padding: 16px mobile, 24px desktop.
- Radius: 12px cards, 20px sheets, 999px chips and avatars, 0 for full-bleed media.
- Depth comes from layering and light, not heavy shadows: one soft shadow for sheets
  and the Daily Drop stack only (`0 8px 32px rgba(0,0,0,.35)` dark, `.12` light).

### Imagery
- Real people and real work, full-bleed. No stock photos, no 3D blobs, no AI art.
- Avatars without a photo: initials on a colour derived from the name (from a fixed set
  of 8 muted tones), never a generic silhouette.
- Startup cards without a logo: the startup's initial in Geist 600 on `surface-2`.

### Iconography
- One outline icon set (Lucide), 1.75px stroke, 24px in the tab bar, 20px elsewhere.
- Icons always paired with a label in navigation and primary actions.

## 6. Components (packages/ui)
Avatar (with story ring states), Badge (verification 1–3, Bridge, Hiring, Under-18
private), Button (primary, secondary, ghost, destructive; 48px tall on mobile), Chip
(selectable, removable), Card (person, startup, job, build log, match, circuit),
TodayStrip, StoryViewer, DropStack, PostComposer, MediaPager, ReactionBar, ReplyThread,
BottomSheet, Modal, Tabs, SegmentedControl, SearchField, Toast (with undo), Skeleton,
EmptyState (illustration + one sentence + one action), CircuitRing (animated).

## 7. Motion

Principles (from Instagram's motion system): elements have weight, entrances are
staggered, movement follows physics, and the UI layers like paper in light.

| Interaction | Spec |
|---|---|
| Default spring | stiffness 380, damping 32, mass 1 (snappy, no wobble) |
| Sheets, modals | stiffness 300, damping 30; drag-to-dismiss with velocity |
| Card stack swipe | follows finger 1:1; rotates up to 8°; throw threshold 30% width or 800px/s |
| List entrance | fade + rise 12px, 40ms stagger, first 8 items only |
| Tab switch | 150ms crossfade; no slide between tabs |
| Story ring "seen" | ring fades from gradient to neutral over 400ms after viewing |
| Reaction tap | icon scales 1 → 1.25 → 1 in 220ms; light haptic where supported |
| **Circuit closing (signature)** | the three ring segments draw in sequence (3 × 300ms), the gradient sweeps once around (600ms), avatars pulse once; total ≤ 1.6s; plays once per circuit |

- Animate only transform and opacity. 60fps on a mid-range Android or it gets simpler.
- `prefers-reduced-motion`: replace all motion with 150ms fades; the circuit closing
  becomes a static closed ring with a checkmark.
- Library: `motion` (Framer Motion for React).

## 8. Healthy habit rules (non-negotiable)
- The Daily Drop is finite (3 per day). Pulse ends with "You're caught up."
- No public like, follower or view counts. Authors see their own totals privately.
- No streaks, no "you haven't posted in X days", no guilt notifications.
- Notifications: max 3 push per day by default; quiet hours 22:00–08:00 IST by default;
  every notification type can be turned off.
- Under-18: private by default, organisation-only posting, no Requests from strangers,
  no appearance in public Discover until age is verified and the student opts in.
- Every post and profile has Report and Block within two taps.

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
- Full keyboard support on desktop; visible focus rings (2px `accent`).
- Screen reader order matches visual order; the Today strip is a labelled list.

## 11. Performance (budget Android phones, slow 4G)
- App initial JS < 250KB gzipped; route-level code splitting; map and dashboard lazy.
- Images: AVIF/WebP via Supabase Storage transforms, responsive sizes, blur placeholders,
  lazy below the fold. Max upload 4 images × 5MB, resized client-side to 1440px.
- Feed: virtualised list; prefetch the next 5 items' images only.
- Skeletons for every loading state; no spinners for content.
- Lighthouse mobile ≥ 90 on Home, Discover and Profile.

## 12. Banned (never ship these)
- Any gradient other than the signature gradient, and the signature gradient anywhere
  outside rings, the circuit animation and the app icon
- Glassmorphism, neon glows, blurred blobs, aurora backgrounds
- Emoji as icons; sparkle icons; "AI-powered" labels
- Stock photos, lorem ipsum, "John Doe", fake stats, placeholder logos
- Public follower/like counts; infinite feeds without an end; streaks
- Centred body text; more than one primary button per screen; heavy drop shadows
- Animations that don't explain a change

## 13. Process
1. Build packages/ui and the Home screen first; show screenshots at 375px (dark and
   light) and 1280px before building anything else.
2. For each new screen, state in one sentence what the user is trying to do and what the
   single most important element is, then build it.
3. After each screen, critique the screenshot against this file and the banned list;
   fix, then show before/after.
4. Test on a real mid-range Android phone before calling a screen done.

---
Research references: Instagram's current tab layout and the reasoning behind it
(DMs and Reels as primary destinations, create moved to the top bar); Instagram's
motion system (weight, physics, staggered timing, layering); Instagram's brand refresh
(full-bleed real imagery, a single signature gradient used sparingly); BeReal's design
(scarcity and authenticity creating meaning without pressure).
