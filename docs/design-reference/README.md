# Design reference mock (Emerald)

These files are the visual target for every screen (from the "Circuit app design" canvas).
They are REFERENCE ONLY: never import, copy or ship them. Rebuild each screen with
packages/ui components, DESIGN.md tokens and data hooks.

| File | Screen | DESIGN.md |
|---|---|---|
| Brand.dc.html | Logo "The Bridge": app icon and lockup on lavender and black | §5 Logo |
| TabBar.dc.html | Tab bar component (partner variant shows Dashboard) | §3 |
| Main.dc.html | Home: Live wire + Daily Drop | §4 Home |
| Update.dc.html | Live wire update view | §4 Home |
| Discover.dc.html / People.dc.html / Map.dc.html | Discover: Jobs, People, Map | §4 Discover |
| Job.dc.html | Job page with sticky Apply | §4 Discover |
| Circuits.dc.html | Circuits ring, accept, closed state | §4 Circuits |
| Inbox.dc.html / Chat.dc.html | Inbox and a conversation | §4 Inbox |
| Profile.dc.html / Person.dc.html | Own profile, someone else's profile | §4 Profile |
| Composer.dc.html | New build log | §4 Build log |
| Notifications.dc.html | Notifications grouped by day | §4 Notifications |
| Settings.dc.html / Appearance.dc.html | Settings, Appearance (theme, accent, swipe; light theme preview) | F12, §5 accent |
| Welcome, Invite, Role, Work, Offer, Colour, Ready (.dc.html) | Sign-up steps 1, 3, 5, 8, 9, 13, 14 | §4 Sign-up |
| InvestorFocus.dc.html / InvestorHome.dc.html | Investor step 8i, Today's picks | §4 Investor |
| PartnerType.dc.html / PartnerHome.dc.html / Org.dc.html | Partner step 8p, Partner home, Organisation page | §4 Partner |
| Desktop.dc.html | Desktop Home: rail, centre column, Daily Drop rail | §3 |
| Landing.dc.html | Landing site home page | §4 Landing |

Phones are 390×844, shown in the dark theme (Appearance.dc.html previews light).
Layout and every value are inline `style="…"`. `{{…}}`, `<sc-for>`, `<sc-if>` and
`<dc-import>` are the mock's template syntax; sample data and interactions are in the
`<script>` block.

Hex → DESIGN.md §5 token (dark theme):
#000000 bg · #08140F surface · #0E2019 surface-2 · #1B382D / #142C23 surface-3 ·
#F3EEF5 text · #A79FAD text-muted · #8A8390 text-subtle · #00563F primary (with
#FFFFFF on-primary) · #2FBF8A current · #8E8CFF bridge · #FF453A danger.
Light theme: #C2BCC8 bg · #D2CDD7 surface · #B3ACBA surface-2 · #120309 text ·
#4A4150 text-muted · #00563F primary and current · #3B2F9E bridge.
Use the tokens, never the hex values. Placeholder text in [BRACKETS] must come from
real data or config, never be shipped as-is.
