# apps

The two websites. Both are Next.js (App Router) + TypeScript + Tailwind, in the pnpm workspace.

| Folder | What it is | Live at |
|---|---|---|
| `app/` | The product app (signed-in screens). Talks to the API only through `src/data/` hooks. | `app.circuitapp.net` |
| `landing/` | Public marketing site, statically exported. Only calls `POST /api/waitlist` and `GET /api/config`. | `circuitapp.net` |

Each has its own README with run and test commands.
