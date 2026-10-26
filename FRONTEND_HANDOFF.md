# Circuit — Frontend handoff

**API version:** 1.2.0 (frozen). Any change to `packages/api-client/openapi.json` needs a higher version here and in `backend/circuit/api.py`, and an entry in section 3; `make api-freeze` (and CI) fails otherwise.

What the app's data layer (`apps/app/src/data`) can rely on from the backend. One section per screen: the hook that serves it, the
endpoints it calls, what comes back, which errors to draw, the Realtime channels and the rate limits.

**How this file stays true.** Every screen section below has a *contract test* (`backend/tests/contract/`) that makes the calls
exactly as written here against the seeded demo world, checks each response against `packages/api-client/openapi.json`, and compares it
with a committed fixture in `packages/api-client/fixtures/<screen>/<scenario>.json`. A test also checks that every endpoint named in
this file exists and that every screen has a section. Change an endpoint → update this file, the contract test, the fixtures
(`make contract-fixtures`) and the client (`make api-client`) in the same commit.

**Mock mode.** The fixture files are what `make mock` should serve. `fixtures/index.json` lists screens → scenarios → hooks. Each
file is `{screen, scenario, persona, calls: [{hook, request: {method, path, body?}, status, response}]}`; a mock handler matches a
request by method and path and answers with `status` and `response`. The world is the demo seed at a frozen clock
(Monday 2 March 2026, 09:30 IST), so "3 hours ago" in a fixture is 3 hours before that moment.

---

## 0. Conventions that apply everywhere

### Calling the API
- Base path `/api`. JSON in, JSON out. `Authorization: Bearer <Supabase access token>` on everything except the public routes
  (`GET /api/config`, `POST /api/waitlist`, `GET /api/support/contact`, `GET /api/health*`, unsubscribe links).
- The client is generated from `openapi.json` (`packages/api-client`). Never hand-write a fetch.

### Errors: one envelope
```json
{"error": {"code": "not_found", "message": "Not found", "details": null}}
```
| Status | `code` | Draw |
|---|---|---|
| 401 | `unauthenticated` | Session ended: sign out |
| 403 | `beta_required` | Invite-code screen (`GET /api/config` and `GET /api/me` also carry `beta_access`) |
| 403 | `consent_required` | Consent screen (`me.needs_consent`) |
| 403 | `account_suspended`, `account_deleted` | Signed-out notice |
| 403 | `forbidden` | "You can't do that" (wrong role) |
| 403 | `under_18_restricted` | The one-sentence under-18 explanation |
| 404 | `not_found` | The 404 screen. Also what hidden, blocked, under-18 and other people's items look like, on purpose |
| 404 | `feature_off` | The feature's flag is off for this member: show the 404 screen and hide its entry points |
| 409 | `conflict`, or a specific code (`intro_weekly_limit`, `target_full`, `awaiting_reply`, `not_a_request`, `already_requested`, `job_closed`, `invalid_transition`...) | One sentence for that code |
| 422 | `validation_error` (`details` = the field problems), or a specific code (`unknown_capability`, `bad_cursor`...) | Inline field message |
| 429 | `rate_limited` | "Try again in a bit" — `details.retry_after` is seconds |
| 5xx | `internal_error`, `service_unavailable` | The 500 screen / retry |

### Lists
- **Offset pages:** `?limit=20&offset=0` (limit 1–100) → `{items, count, next_offset}`; `next_offset` is `null` on the last page.
- **Cursor feeds** (Pulse, messages): `?cursor=<next_cursor>&limit=` → `{items, next_cursor}`; a bad cursor is 422 `bad_cursor`: reload from the top.
- Some small lists are plain arrays (Live wire, map pins, connections, conversations: at most 100).

### Feature flags (`GET /api/config` → `features`)
`pulse`, `daily_drop`, `circuits`, `investor_mode`, `partner_mode`, `promotions`, `payments`. A flag that is off for the member makes its
endpoints answer **404 `feature_off`**, and leaves its items out of Pulse, Live wire, search, notifications, the Startup page's build
logs and the Profile's grids. Hide the entry point rather than showing the 404. Fixtures: `*/features_off.json`.

### Gates, in the order the app meets them
1. Signed in (Supabase). 2. `403 beta_required` → invite code. 3. `403 consent_required` → consent. 4. Onboarding (`GET /api/onboarding/state`).

### Under-18 members (the server enforces all of this; do not rely on hiding it in the UI)
Hidden profile, no requests from strangers (`allow_requests` false), no Daily Drop, no intros (`403`), no circuits, no Requests folder
(`requests` count is always 0), `photo` visible only to themselves, roles and hiring only from **verified** (claimed) startups
everywhere (jobs, map, startup page, search, skills in demand, Pulse, Live wire), search finds only their connections. Fixtures:
`*/under_18.json`.

### What is never in a response
Raw match scores (words only: `strength`: `strong` | `good`), another person's distance (only coarse filters), public follower or
connection counts (`mutual_count` is "you and them"), startup `view_count` / `interest_count` (only for the startup's team, or a
founder looking at an *unclaimed* page, and then only from 5), a decline ("declined" looks like nothing happened to the sender),
emails and phone numbers, anything about under-18 members to people who may not see them.

### Photos and images
Every person-shaped object (`PersonOut`, `AuthorOut`) has `photo: string | null` (a signed link, valid about an hour; draw the
circuit-pattern avatar for `null`). Startups have `logo` the same way. Upload flow for any image: `POST /api/media/uploads`
`{purpose: "post" | "message" | "avatar" | "startup_logo", content_type, size}` → `{id, upload_url}` → `PUT` the file to `upload_url`
→ `POST /api/media/uploads/{id}/complete` → use the id (`PUT /api/me/photo`, `PUT /api/startups/{id}/logo`, a post, a message).
JPEG, PNG or WebP, up to 5 MB; shrink to 1440px on the phone first.

### Realtime (Supabase private Broadcast; ids only, then refetch through the API)
| Topic | Event | Payload | Who hears it | Hook |
|---|---|---|---|---|
| `member:<my id>` | `notification` | `{notification_id}` | me | `useNotificationNudges` |
| `member:<my id>` | `conversation` | `{conversation_id}` | me: a new request or chat, a new message, or my request was accepted | `useInbox`, `useInboxDot` |
| `conversation:<id>` | `message` | `{message_id, conversation_id}` | the two people in it | `useConversation` |
| `circuit:<id>` | `status` | `{circuit_id}` | the three members | `useCircuits` |

A missed event is harmless: refetch on reconnect and on a slow poll. Row-level policies let a member join only their own topics.

### Rate limits (per member per window; 429 `rate_limited`)
| Action | Limit | Action | Limit |
|---|---|---|---|
| `GET /api/search` | 120 / hour | `POST /api/intros` | 10 / day (and 3 new per rolling week) |
| `GET /api/organisations/search` | 60 / hour | `POST /api/jobs/{id}/apply` | 30 / day |
| `POST /api/onboarding/extract` | 10 / hour | `POST /api/posts` | 10 / day |
| `PATCH /api/onboarding/state` | 120 / hour | replies / reactions | 60 / day, 300 / hour |
| settings, photo, logo writes | 60 / hour | `POST /api/media/uploads` | 40 / day |
| `POST /api/conversations` (new) | 10 / day | `POST .../messages` | 300 / day |
| `POST /api/connections/requests` | 20 / day | `POST /api/reports` | 10 / day |
| `POST /api/beta/redeem` | 10 / hour (30 / hour per address) | `POST /api/waitlist` | 5 / hour per address |
| `POST /api/join/visit` | 120 / hour per address | | |
| `POST /api/me/export` | 3 / day | `POST /api/support` | 5 / day |

---

## 1. Screens

Each section: **Hooks** (in `apps/app/src/data`), **Calls**, **Notes**, **Fixtures**. Shapes name the schema in `openapi.json`;
only the fields a screen draws are listed. `?` = may be `null`.

### `bootstrap` — who am I, what is on (before every screen)
**Hooks:** `useFeatures`, `useMe`, `useSettings`, `useAppearance`, `useGate` (reads `/api/config` and `/api/me`; no call of its own).
| Call | Returns |
|---|---|
| `GET /api/config` (public) | `ConfigOut` `{env, beta_mode, beta_access, features: {flag: bool}, llm_available}`. `llm_available: false` = skip the paste-your-bio box |
| `GET /api/me` | `MeOut`: `id, role, display_name, bio, city, college, lat?, lng?, verification_level, organisation_id?, is_minor, profile_visibility, visible_to_org, circuits_opt_in, allow_requests, open_intro_slots, read_receipts, photo?, startup_id?, has_needs_and_offers, beta_access, needs_consent, policy_version, appearance {theme, accent, swipe_tabs}` |
| `GET /api/me/settings` | `SettingsOut` (see `settings`) |

Notes: the accent is `emerald | sky | indigo | rose | lime | mono`. `mint` is the old name of `emerald`: the server still accepts it on
write but never sends it (drop the app's `mint` mapping). `role` is one of `student | founder | mentor | investor | partner_admin | super_admin`.
`startup_id` is the founder's startup (link Profile to its roles). `has_needs_and_offers` false = not in this week's circuit round yet.
**Fixtures:** `bootstrap/{signed_out,default,founder,partner,under_18,features_off}.json`.

### `access` — invite code, waitlist, consent
**Hooks:** `useRedeem`, `useJoinWaitlist`, `useJoinVisit`, `useConsent`, `useInviteLink`.
| Call | Returns / errors |
|---|---|
| `POST /api/beta/redeem` `{code}` | `RedeemOut`. Any bad code is the same `400 invalid_code`. `429` after 10 tries an hour |
| `POST /api/waitlist` (public) `{email, role, city, college, note, src}` | `202 {status: "ok"}` always (never say "already on the list") |
| `POST /api/join/visit` (public) `{src}` | `204`. Call it once per browser session when `/join` opens with a `src`, for the per-source funnel (clicks next to sign-ups). Fire and forget: ignore errors. Stores only a per-day count; `422` for a `src` that is not lowercase letters, digits, `-` or `_` (max 40) |
| `POST /api/me/consent` `{policy_version}` | `ConsentOut` |
| `GET /api/invites` | `InvitesOut`: my invite codes and links (up to 3), used or available |

**Fixtures:** `access/{default,beta_gate}.json`. `beta_gate`: a member without access gets `403 beta_required` on everything except `GET /api/me`.

### `signup` — one question per screen
**Hooks:** `useOnboarding`, `useCapabilities`, `useWhere`, `useOrganisationSearch`, `useRoleChoices` (no call: the roles come from `/api/config` flags).
| Call | Returns |
|---|---|
| `GET /api/onboarding/state` | `OnboardingOut` `{branch, steps[], skip[], current_step?, completed_at?, answers, signup_source}`; `skip` lists steps we already know |
| `PATCH /api/onboarding/state` `{current_step?, answers?: {step: {...}}, signup_source?, completed?}` | the new state. **`answers.age.adult: false` makes the member under 18 on the server** (`is_minor`, hidden profile, no requests, student role, circuits off); answering "adult" later never clears it |
| `PATCH /api/me` `{display_name, role, city, college, bio, lat, lng}` | `MeOut` (send `lat` and `lng` together; the app rounds to ~1 km) |
| `GET /api/cities` | `[{name, lat, lng, pilot}]` the pilot city first |
| `GET /api/organisations/search?q=&kind=` | `[{id, name, kind, city}]` up to 10, `q` ≥ 2 characters. Never a join code. Choosing one only fills `college`; joining still needs the organisation's code (`POST /api/organisations/join`) or a verified email on its domain (`POST /api/organisations/join-by-email`) |
| `POST /api/onboarding/extract` `{bio}` | `ExtractOut` `{source: "llm" | "manual", suggestions: {needs, offers, skills, traits}}`; `manual` = empty suggestions, show the pickers |
| `GET /api/capabilities`, `GET /api/traits` | the fixed lists (slug, name, category) |
| `PUT /api/me/offers`, `/needs`, `/skills`, `/traits` | replace the list: `[{capability, description}]` (at most 8 items in each; traits 10). The app's own limits of 5 offers and 3 needs are UI rules; the server allows more, and `422 too_many` is the error |
| `PATCH /api/me/appearance`, `/privacy` | see `settings` |
| `PUT /api/me/photo` `{upload_id}` / `DELETE /api/me/photo` | `MeOut` with `photo`. The Photo step is real now |
| `GET /api/drop/today` | "Ready": the first card if the first drop is built, else `cards: []` and `next_drop_at` about 5 minutes away |

Notes: a member who finishes sign-up gets matches and a first Daily Drop within about 5 minutes (job `first_drops`), not at 08:00 tomorrow.
**Fixtures:** `signup/{new_member,under_18}.json`.

### `home` — Live wire, Update view, Daily Drop, Pulse
**Hooks:** `useHome`, `useLiveWire`, `useMarkUpdateSeen`, `useDailyDrop`, `useSkip`, `usePulse`, `useMarkPulseSeen`, `useReact`, `useReport`, `useMatches`.
| Call | Returns / errors |
|---|---|
| `GET /api/livewire` (`pulse`) | up to 12 × `WireItemOut` `{key, kind, actor?, startup?, image?, headline, reason, action {kind: intro|view_role|reply, target_id}, created_at, seen}` |
| `POST /api/livewire/seen` `{key}` | `204` |
| `GET /api/drop/today` (`daily_drop`) | `DropOut` `{date, cards[], done, next_drop_at}`; card: `{member (AuthorOut), reason, is_bridge, strength, help_with?, offers_you_need[], via?, image?, outcome?}`. Under-18: `cards: []` |
| `POST /api/drop/today/{member_id}/swipe` `{direction: intro|skip}` | the updated `DropOut`; `409 already_answered` |
| `GET /api/pulse?cursor=&limit=&include_seen=` (`pulse`) | `PulseOut` `{items, next_cursor, caught_up}`; item `{kind: post|role|activity|skills_in_demand, key, created_at, seen, post?, role?, activity?, skills_in_demand?}` |
| `POST /api/pulse/seen` | `204` |
| `PUT` / `DELETE /api/posts/{post_id}/reactions/{kind}` (`kind` = `helpful | intro_me | lets_talk`) | `204` |
| `GET /api/matches` | see `discover` |
| `POST /api/reports` `{target_type, target_id, reason}` | `201` |

Notes: Pulse / Live wire / Daily Drop answer `404 feature_off` when their flag is off; the screens collapse as DESIGN.md §3 says. Partner and
promoted slots are **not served yet** (they arrive with Stages 4d and 4g); keep the mock stand-ins for them.
**Fixtures:** `home/{default,empty,founder,under_18,features_off}.json`.

### `intros` — the intro sheet and the intros inbox
**Hooks:** `useIntroPath`, `useIntroCapacity` (new), `useRequestIntro`, `useIntros`, `useRespondIntro`, `useRateIntro`.
| Call | Returns / errors |
|---|---|
| `GET /api/intros/path/{target_id}` | `PathOut` `{target, via?}`; `404 no_warm_path` when there is no mutual connection |
| `GET /api/intros/capacity` | `CapacityOut` `{allowed, weekly_limit, used, left, next_frees_at?}`. `allowed: false` for under-18s. About me only; how full another person is stays private |
| `POST /api/intros` `{target_id, message}` | `201` new / `200` already open: `IntroOut`. `409 intro_weekly_limit`, `409 target_full`, `403` under 18 |
| `GET /api/intros?box=sent|received|brokered` | `Page<IntroOut>` `{id, my_role, status, stage, can_respond, requester, target, via?, message, outcome_rating?, created_at, expires_at}` |
| `POST /api/intros/{id}/respond` `{accept}` | `IntroOut` (the mutual connection answers first, then the person) |
| `POST /api/intros/{id}/rating` `{rating: 1-5}` | `IntroOut` |

**Fixtures:** `intros/{default,broker,target,rating,under_18}.json` (the Story 4 path: Sneha → Vikram through Lakshmi).

### `notifications`
**Hooks:** `useNotifications`, `useUnreadCount`, `useMarkRead`, `useNotificationNudges` (Realtime only).
| Call | Returns |
|---|---|
| `GET /api/notifications?unread=&limit=&offset=` | `Page<NotificationOut>` `{id, kind, text, actor?, target? {type, id}, payload, read, created_at}`. `text` now names the people and things ("Meera accepted your intro request to Sakthi.", "You were shortlisted for Frontend intern."); a deleted or under-18 person is never named: the plain line is used |
| `GET /api/notifications/unread-count` | `UnreadCountOut` `{count}` (the schema used to be called `CountOut`) |
| `POST /api/notifications/read-all` | `UnreadCountOut` (how many changed) |
| `POST /api/notifications/{id}/read` | `NotificationOut` |

Realtime: `member:<id>` / `notification`. **Fixtures:** `notifications/{default,empty}.json`.

### `discover` — People, Startups, Jobs, Map, search
**Hooks:** `useDiscoverPeople`, `useDiscoverStartups`, `useDiscoverJobs`, `useSkillsInDemand`, `useMapPins`, `useDiscoverSearch`.
| Call | Returns |
|---|---|
| `GET /api/matches?bridge=&role=&verified=&capability=&within_km=&limit=&offset=` | `Page<MatchOut>` `{candidate_id, display_name, role, verification_level, city, sector?, strength?, reason, is_bridge, photo?, headline, capabilities[]}`. `role` = student|founder|mentor|investor; `verified=true` = level 2+; `capability` = a slug they offer; `within_km` = 5, 10, 25 or 50 (else 422). No distance is returned |
| `GET /api/startups/nearby?lat=&lng=&radius_km=&hiring=&capability=&limit=` | `PinOut[]` `{id, name, lat, lng, hiring, sector, claimed, open_roles, match_pct?, distance_km?, logo?}` |
| `GET /api/startups/map?min_lng=&min_lat=&max_lng=&max_lat=&hiring=&capability=` | `PinOut[]` (the box may be about 2° wide; 500 pins) |
| `GET /api/jobs?kind=&capability=&startup_id=&max_distance_km=&min_stipend=&limit=&offset=` | `Page<JobOut>` (see `job`). Students: best skill match first |
| `GET /api/jobs/skills-in-demand?within_km=10` | `[{slug, name, open_roles}]` top 3. Role counts only |
| `GET /api/search?q=` (≥ 2 characters) | `SearchOut` `{people: AuthorOut[≤10], startups: PinOut[≤10], jobs: JobOut[≤10]}` — one call for the whole search field. People by name only; hidden, under-18, blocked and deleted people never appear |

Notes: `match_pct` is a student's own skill fit with a startup's open roles (0-100), shown to them only; draw it in words. Under-18: the server
removes unverified startups' roles and shows those startups as not hiring. **Fixtures:** `discover/{people,startups,jobs,under_18,empty}.json`.

### `job` — job page, apply, my applications
**Hooks:** `useJob`, `useApply`, `useWithdraw`, `useMyApplications`, `useStartupJobs`, `usePostJob`, `useEditJob`.
| Call | Returns / errors |
|---|---|
| `GET /api/jobs/{id}` | `JobOut` `{id, title, kind, description, stipend_min?, stipend_max?, location, is_open, created_at, startup_id, startup_name, sector, startup_verified, startup_logo?, duration_weeks?, starts_on?, contact? (PersonOut), is_team, lat?, lng?, distance_km?, capabilities[{slug, name, required, your_level?}], skill_match?, applied?}` — everything the page draws in one call. `is_team: true` → "See applicants". `404` for a closed role (unless I'm on the team) and, for under-18s, an unverified startup's role |
| `POST /api/jobs/{id}/apply` | `201` new / `200` already applied: `ApplicationOut` `{id, job_id, job_title, startup_id, startup_name, status, skill_match, created_at}`. `409 job_closed`; `404` for under-18 at an unverified startup; students only |
| `GET /api/me/applications` | `Page<ApplicationOut>` |
| `POST /api/applications/{id}/withdraw` | `ApplicationOut` |

Founders post roles with `POST /api/jobs` and edit or close them with `PATCH /api/jobs/{id}`, now also `duration_weeks` and `starts_on`; a student withdraws with `POST /api/applications/{id}/withdraw`. **Fixtures:** `job/{default,team,under_18,founder_posts}.json`.

### `applicants` — founder's applicant view
**Hooks:** `useApplicants`, `useSetApplicantStatus`.
| Call | Returns |
|---|---|
| `GET /api/jobs/{id}/applicants` | `Page<ApplicantOut>` `{application_id, student_id, display_name, status, skill_match, skills[{capability (slug), name, level, proof_url}], applied_at}`, best match first. Nothing about colleges. One query for all the skills |
| `PATCH /api/applications/{id}` `{status: shortlisted|rejected|hired}` | `ApplicationOut`; `409 invalid_transition`; someone else's is `404` |

**Fixtures:** `applicants/default.json`.

### `startup` — Startup page
**Hooks:** `useStartup`, `useFollows`, `useFollow`, `useInterest`, `useEditStartup`, `useStartClaim`, `useVerifyClaim` (the code arrives by email, so no fixture), `useStartupJobs`.
| Call | Returns / errors |
|---|---|
| `GET /api/startups/{id}` | `StartupOut` `{id, name, website_domain, description, sector, stage, address, team_size?, logo?, lat?, lng?, hiring, tech_stack[], claimed, verified, source, view_count?, interest_count?, interested, is_team, match_pct?, open_jobs[], founders[], build_logs[]}`. **One call draws the page:** `founders: [{person, role, via?, connected, is_me}]` carry the warm path (no call per founder); `build_logs: [{post_id, image}]` is the first picture of the team's latest build logs I may see (empty with `pulse` off). `view_count` / `interest_count` are **null** unless I'm on the team, or I'm a founder on an unclaimed page (then not under 5). Counts one view per member per day; the map sheet, which uses `GET /api/jobs?startup_id=`, counts none |
| `POST` / `DELETE /api/startups/{id}/follow` | `204` |
| `GET /api/me/follows` | followed startups |
| `POST` / `DELETE /api/startups/{id}/interest` | `204` (students) |
| `POST /api/startups/{id}/claim` `{email}` → `POST .../claim/verify` `{code}` | claim by company email (founders) |
| `PATCH /api/startups/{id}` | the team edits: `description, stage, hiring, address, tech_stack, team_size, lat, lng` |
| `PUT` / `DELETE /api/startups/{id}/logo` `{upload_id}` | the team sets the logo (upload with purpose `startup_logo`, founders only) |

**Fixtures:** `startup/{default,actions,claim,team,under_18}.json`.

### `circuits` — exchange circuits (flag `circuits`; students need level 2 to opt in)
**Hooks:** `useCircuits`, `useRespondCircuit`, `useMarkDone`, `useRateHandover`.
| Call | Returns / errors |
|---|---|
| `GET /api/circuits` | `Page<CircuitOut>`; `GET /api/circuits/{id}` the same shape. `{id, status, score_percent, week, consent_deadline, time_left_seconds?, created_at, my_consent, next_step: answer|waiting|mark_done|rate|none, you_help {person, capability}, helps_you {...}, members[{person, is_me, consent, done}], legs[{id, giver, receiver, capability, consent, fulfilled, rated, rating?, i_give, i_receive, can_mark_done, can_rate}]}` |
| `POST /api/circuits/{id}/respond` `{accept}` | `CircuitOut` (one no ends it for all three) |
| `POST /api/circuits/{id}/legs/{leg_id}/done` | `CircuitOut` |
| `POST /api/circuits/{id}/legs/{leg_id}/rating` `{rating: 1-5}` | `CircuitOut` |

Realtime: `circuit:<id>` / `status` → refetch. `me.has_needs_and_offers` and `me.circuits_opt_in` explain an empty list. Under-18 members are never in a round (empty list).
**Fixtures:** `circuits/{proposed,priya_accepts,active,rate,empty,features_off}.json`.

### `inbox` — Chats and Requests
**Hooks:** `useInbox`, `useInboxDot`, `useConnections`, `useStartConversation`.
| Call | Returns |
|---|---|
| `GET /api/conversations?folder=chats|requests` | `ConversationOut[]` (≤ 100, newest first) `{id, status: request|active, other (AuthorOut + photo), started_by_me, last_message_at?, unread, last_message?}` |
| `GET /api/conversations/unread-count` | `{chats, requests}`: conversations with something unread. `requests` is always 0 for under-18s |
| `GET /api/connections` | `AuthorOut[]` |
| `POST /api/conversations` `{member_id, body?, upload_id?}` | `201 {conversation, message}`; a stranger gets a request (one message until they answer) |

Realtime: **one** subscription is enough for the list: `member:<id>` / `conversation` (new request, new message, accepted). **Fixtures:** `inbox/{default,under_18,empty}.json`.

### `conversation`
**Hooks:** `useConversation`, `useDraftConversation` (no call of its own: `GET /api/members/{id}` then `POST /api/conversations`), `useDeclineRequest` (new).
| Call | Returns / errors |
|---|---|
| `GET /api/conversations/{id}` | `ConversationOut` (404 unless I'm one of the two) |
| `GET /api/conversations/{id}/messages?cursor=` | `{items: MessageOut[] (newest first), next_cursor?}`; `MessageOut` `{id, conversation_id, mine, body, image? {width, height, w1440, w480}, removed, created_at, read_at?}` |
| `GET /api/conversations/{id}/messages/{message_id}` | one `MessageOut` (what to fetch after a Realtime nudge) |
| `POST /api/conversations/{id}/messages` `{body?, upload_id?}` | `201 MessageOut`; `409 awaiting_reply` (a request allows one message until answered) |
| `POST /api/conversations/{id}/read` | `{marked}` |
| `POST /api/conversations/{id}/accept` | `ConversationOut` (only the person asked) |
| `POST /api/conversations/{id}/decline` | `204`. It disappears for me; the sender is **not** told and still sees a quiet request. `409 not_a_request` for a chat. Writing back later accepts it after all |
| `POST /api/conversations/{id}/block` | `204` |

`read_at` appears on **my** messages only when both people switched on `read_receipts` (default off), else `null`. Realtime: `conversation:<id>` / `message`.
**Fixtures:** `conversation/{default,awaiting_reply,request,decline,decline_answer}.json`.

### `profile` — Profile (own and others')
**Hooks:** `useProfile`, `useConnect`, `useConnectionRequests`. One call draws the screen.
| Call | Returns |
|---|---|
| `GET /api/members/{id}` (mine too) | `ProfileOut` `{id, is_me, role, display_name, photo?, headline, bio, city, college, verification_level, organisation? (only people in my organisation, and me), connection: self|connected|requested|requested_you|none, actions {connect, message, intro}, mutual_count? ("12 mutual connections"; null for me), via? (who would introduce me), build_logs[{post_id, image}] (≤ 12), circuits_closed? (mine or a connection's), strength? {percent, next_step {key, text}} (mine only), needs[], offers[], skills[{capability, level, proof_url}], traits[]}`. `actions` already applies every rule (blocks, under-18, closed to strangers, a recent decline): draw the buttons from it. Hidden, under-18, blocked, suspended, admin: `404` |
| `GET /api/members/{id}/posts` | their build logs I may see |
| `POST /api/connections/requests` `{member_id, note}` → `GET /api/connections/requests?box=incoming|outgoing` → `POST /api/connections/requests/{id}/respond` `{accept}`; `DELETE /api/connections/{member_id}` | connect (a declined request cannot be re-sent for 30 days: `409 recently_declined`) |

Not modelled yet (listed so nobody builds against a guess): *Highlights* (pinned projects) and the *GitHub summary*. No follower or connection counts exist anywhere.
**Fixtures:** `profile/{default,hidden_or_blocked,connect_ask,connect_answer}.json`.

### `build_log` — post, replies, composer
**Hooks:** `usePost`, `usePostReplies`, `useReply`, `useDeletePost`, `useDeleteReply`, `useMemberPosts`, `usePostComposer`, `useMediaUpload`. Flag `pulse`.
`GET /api/posts/{id}` → `PostOut` `{id, author, body, link, visibility: everyone|connections|organisation, status, created_at, capabilities[], media[{alt_text, w1440, w480, width, height}], my_reactions[], private_stats? (the author's totals; null for everyone else)}`;
`POST /api/posts` `{body ≤ 500, link?, visibility, capabilities[≤3], media[{upload_id, alt_text}] ≤ 4}`; `DELETE /api/posts/{id}`;
`GET` / `POST /api/posts/{id}/replies` (one level); `DELETE /api/replies/{id}`; `POST /api/media/uploads` (see Photos and images).
**Fixtures:** `build_log/{default,delete}.json`.

### `settings`
**Hooks:** `useBlock`, `useSettings`, `usePrivacy`, `useAppearance`, `useNotificationPrefs`, `useBlocks`, `useExport`, `useDeleteAccount` (destructive, so no fixture), `useSupport`.
| Call | Returns / errors |
|---|---|
| `GET /api/me/settings` | `SettingsOut` `{profile {display_name, role, city, college, is_minor, verification_level, email_hint}, privacy, appearance, notifications, blocked_count, export?, consent, support}` |
| `PATCH /api/me/privacy` `{profile_visibility?, visible_to_org?, circuits_opt_in?, allow_requests?, read_receipts?}` | `PrivacyOut`. Real booleans only. Under-18: `403 under_18_restricted` for a public profile or open requests; circuits need level 2 (`403`) |
| `PATCH /api/me/appearance` `{theme?, accent?, swipe_tabs?}` | `AppearanceOut` |
| `PATCH /api/me/notification-preferences` `{intros?: {in_app?, email?}, ...}` | `NotificationPrefsOut` (types: intros, applications, circuits, messages, pulse_replies, announcements) |
| `GET /api/me/blocks`, `POST` / `DELETE /api/members/{id}/block` | blocked people |
| `POST /api/me/export` → `GET /api/me/export` → `GET /api/me/export/download?token=` | data export (one at a time, a signed link by email) |
| `POST /api/me/deletion` `{confirm: "DELETE"}` | `202`; the account is locked at once and erased by a job (no fixture: destructive) |
| `POST /api/support` `{kind, message}`, `GET /api/support/contact` (public) | support and the grievance contact |

**Fixtures:** `settings/{default,blocks,block_from_chat,under_18}.json`.

### `partner_dashboard` — partner admins (core, not flagged)
**Hooks:** `useDashboard`, `useOrganisation`.
`GET /api/dashboard/gaps | heatmap | network | acceptance` → aggregates over the admin's own organisation; any count under 5 comes back as `{hidden: true, value: null}` (`MaskedCountOut`); anyone else gets `403`.
`GET /api/organisations/mine` (the admin also gets `join_code`), `GET /api/organisations/mine/members` (only members who opted in).
**Fixtures:** `partner_dashboard/{default,not_a_partner}.json`.

### `errors` — the envelope in each situation
Fixtures `errors/{signed_out,default,rate_limited,beta_required}.json` show 401, 404, 422, 429 (with `retry_after`) and 403 `beta_required` exactly as they arrive.

---

## 2. Not built yet (do not call; keep the mocks)

| Screen | Waits for | Planned shape (may still change) |
|---|---|---|
| Promoted slots in Pulse and Discover, "Hide this", "Why am I seeing this?" | Stage 4d (promotions) | A separate promotions endpoint (one per slot: Pulse, Discover startups, Discover jobs) returning at most one labelled item with its reason sentence; never part of matching, Drop, Live wire or search ranking |
| Payments / packages / checkout | Stage 4e | Orders created by the backend, Razorpay Checkout opened by the app, the webhook is the only thing that activates a campaign |
| Investor home, picks, founder opt-in | Stage 4f (`investor_mode`) | |
| Cohorts, calls, events, announcements, organisation page, partner items in Pulse | Stage 4g (`partner_mode`) | |
| Profile highlights, GitHub summary | not scheduled | |

## 3. What changed in the API in B7 (for switching hooks from mocks)

B7 part 3 (API 1.2.0; the 1.1.0 spec file had not been regenerated after these changes, so re-pull `packages/api-client`):
new `PUT /api/me/highlights` (up to 6 pinned projects, see the endpoint description); `ProfileOut` gains `highlights` and `circuits_together`;
`GET /api/members/{id}/posts` now returns a page `{items, next_cursor}` instead of a list; notification preferences gain a `push` flag per type
and `quiet_hours`. Fixed: `PUT /api/me/highlights` answered 500 (unregistered event name).

B7 part 2 (API 1.1.0): new `POST /api/join/visit` (above). Nothing else changed.

New: `GET /api/cities`, `GET /api/organisations/search`, `GET /api/search`, `GET /api/intros/capacity`, `GET /api/jobs/skills-in-demand`,
`GET /api/conversations/unread-count`, `POST /api/conversations/{id}/decline`, `PUT|DELETE /api/me/photo`, `PUT|DELETE /api/startups/{id}/logo`.
Changed: accent `mint` → `emerald`; `CountOut` → `UnreadCountOut` / `MaskedCountOut`; `MeOut`, `PersonOut`/`AuthorOut` (`photo`), `MatchOut`
(`photo, headline, capabilities` + filters on the list), `JobOut`, `StartupOut` (+ private counts), `ApplicantSkill.name`, `ProfileOut` (the whole
screen), `MessageOut` (`read_at`, typed `image`), `ConfigOut.llm_available`, `PrivacyOut.read_receipts`, `NotificationOut.text`.
Behaviour: the age answer sets `is_minor`; under-18s only see verified startups' roles; a new member's first drop is built within minutes;
every message nudges the other person's `member:<id>` channel.
