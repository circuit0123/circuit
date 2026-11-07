# apps/landing

The public marketing site: a home page plus /students, /founders, /mentors, /investors, /partners, /privacy, /terms.
Statically exported (`output: "export"`), no login, no third-party trackers.

## Run
From the repo root:
```
make landing    # http://localhost:3001
```

## Test
```
make test-landing                      # builds the site and runs Playwright (CTAs, waitlist, axe, reduced motion)
pnpm --filter @circuit/landing lint
```

Calls to action link into the app with the role pre-set (`APP_URL/join?role=student&src=landing-students`).
Build-time variables: `NEXT_PUBLIC_APP_URL`, `_LANDING_URL`, `_API_URL`, `_LAUNCH_MODE`, `_WAITLIST_URL`, `_JOIN_LIVE`
(see `.env.example`).
