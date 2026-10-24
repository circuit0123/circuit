> **DRAFT — for lawyer review.** Not legal advice and not yet in force. **[VERIFY]** items must be checked against the real frontend
> once it is built; this draft describes the intended design (DESIGN.md, PRODUCTION.md §3), not a finished implementation.

# Cookie and Local Storage Notice

**Version:** `<POLICY_VERSION>` · **Last updated:** `<DATE>` · Operator: **`<LEGAL_NAME>`**, `<ADDRESS>`

## The short version
Circuit uses only what it needs to work. We use **no advertising cookies, no analytics cookies and no third-party trackers**.
Because of that, there is no cookie banner to click through. If this ever changes, we will ask first.

## What is stored on your device

| Name / kind | Where | Why | How long | Needed to work? |
|---|---|---|---|---|
| Sign-in session (set by Supabase Auth) **[VERIFY name and storage type]** | Browser storage (cookie or local storage) | Keeps you signed in | Until you sign out, or the session expires | Yes |
| Appearance (theme, accent colour, swipe between tabs) | Browser storage, plus saved on your account so it follows you across devices | Shows the app the way you chose before the first screen draws | Until you change it or clear storage | Convenience; the app works without it |
| App shell and offline cache (PWA) **[VERIFY when built, Stage 10]** | Browser cache | Lets the app open quickly and show a basic screen offline | Until a new version replaces it | Convenience |
| Draft text you have not sent yet, last-used tab or filter **[VERIFY]** | Browser storage | Does not lose your work | Until sent or cleared | Convenience |
| Django admin session | Cookie (staff only) | Signs Circuit staff in to the admin | 8 hours | Yes (staff only) |

## The landing site
The landing site sets no cookies. The waitlist form sends your email address, role, city and college to our API only when you submit it.

## Third parties
Maps use OpenStreetMap tiles **[VERIFY]**, requested from the tile server when you open the map; the request carries your IP address
as any web request does. Razorpay Checkout, when you pay for a promotion, is run by Razorpay and may set its own cookies on its own screens; see Razorpay's notice.

## Your choices
You can clear storage and cookies in your browser at any time; you will be signed out. You can change appearance in Settings → Appearance.

## Contact
`<SUPPORT_EMAIL>` · Grievance Officer: `<GRIEVANCE_OFFICER>`, `<GRIEVANCE_EMAIL>`
