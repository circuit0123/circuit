# Circuit — PM ("professional mayhem") design export

The 20 `PM*` screens from the design canvas (https://claude.ai/artifact/KS93XSNUApAMoVJD9kvGpw), exported unchanged on 12 Nov 2026. SHA-256 checksums match the canvas.

## Read these as design specs, not as runnable pages
The files come from the design tool's template format, so **they won't render correctly if you open them in a browser**:
- `{{name}}` placeholders are filled by the small `<script type="text/x-dc">` class at the bottom of each file. That class also holds the sample data and interaction states.
- `<sc-if>` means "show if" and `<sc-for>` means "repeat for each item".
- `<dc-import name="PMNav">` embeds the shared bottom-nav component.
- `support.js` is the design tool's runtime and isn't included.

To build from a screen, take the layout and inline styles from the markup, and the states and copy from the script class. Rebuild each one as a Next.js component using the tokens in `circuit-ui-v2-handoff.md`.

## Screens
| File | Screen | Ship tonight? |
|---|---|---|
| PMBrand | Brand sheet: colours, type, components, rules | Reference |
| PMLanding | Landing page (desktop) | Yes (fix copy first) |
| PMWelcome | Sign-in | Yes |
| PMInvite | Invite code (beta gate) | Yes |
| PMNav | Bottom tab bar | Yes |
| PMComposer | New post ("build log") with required alt text | Yes |
| PMProfile | Profile | Yes |
| PMInbox | Inbox | Yes |
| PMChat | Chat | Yes |
| PMMap | Startup map | Yes |
| PMDiscover | Discover (jobs / startups) | Yes, as the directory |
| PMHome | Today: 3 daily intro cards | Layout only (intros not built) |
| PMSettings | Settings | Only if Settings exists |
| PMRole | Onboarding step 2: role | Later |
| PMOffer | Onboarding step 3: offers and needs | Later |
| PMReady | Onboarding step 4: "You're in" | Later |
| PMPeople | People nearby | Later |
| PMCircuits | Circuits (3-person loops) | Later |
| PMPings | Notifications | Later |
| PMJob | Job detail | Later |

## Sample content: never ship it as real
Every name, quote, number and startup in these files is placeholder content. That covers Sakthi, Meera, Kavya, Tatvagrid, "12 applied", "Strong match", the "LIVE" ticker, and the `[COMPANY LEGAL NAME]`, `[VERSION]` and `[NUMBER]` placeholders. Replace each with real data, or remove it. See section 5 of the handoff file.
