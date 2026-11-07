# packages

Shared code used by both apps. Consumed as source; there is no separate build.

| Folder | What it is |
|---|---|
| `ui/` | Design components and tokens (`tokens.css`) |
| `api-client/` | TypeScript client generated from the backend OpenAPI spec. `src/schema.d.ts` is generated: never edit by hand. `fixtures/` holds the contract fixtures |

## Run and test
```
make api-client          # re-export openapi.json from Django and regenerate the client
pnpm typecheck           # all packages
pnpm lint
```
There are no unit tests here; the apps' Playwright suites and the backend contract tests (`backend/tests/contract`) cover them.
