# apps/app

The Circuit product app: Next.js, client-rendered, mobile-first.

Three layers: `packages/api-client` (generated) → `src/data/` (one TanStack Query hook per screen or action) → screens in
`src/app` and `src/components`. Screens never call the API directly; an ESLint rule enforces this.

## Run
From the repo root:
```
make app        # http://localhost:3000, needs the API (make api)
make mock       # mock data, no backend and no login; switch scenario in the banner
```

## Test
```
make test-web   # type check, boundary rule, Playwright on mock mode (375px and 1280px)
make e2e        # Playwright against the real API (needs make dev running)
pnpm --filter @circuit/app lint
```

| Folder | What it is |
|---|---|
| `src/app/` | Routes. `/design` is dev only |
| `src/components/` | Screens grouped by feature |
| `src/data/` | The only code that talks to the backend; `mocks/` holds mock mode |
| `tests/` | Playwright on mock mode; `e2e/` runs against the real API |

Environment variables: `NEXT_PUBLIC_*`, documented in `.env.example`.
