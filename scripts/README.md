# scripts

Deploy and ops tools. Most are called from the `Makefile`; run them through `make`, not directly.

| Script | What it does | Called by |
|---|---|---|
| `gcp.py` | Deploy, setup, rollback, secrets, jobs, logs (standard library only; uses the `gcloud` CLI) | `make deploy`, `gcp-setup`, `rollback`, `secret`, `jobs-run`; `deploy.yml` |
| `gcp_monitoring.py` | Builds and applies `infra/monitoring` | `make monitoring` |
| `smoke.py` | Read-only smoke test of a running API | `make smoke`; `gcp.py` |
| `check_api_freeze.py` | Fails if `openapi.json` changed without a version bump | `make api-freeze`; CI |
| `doctor.sh` | Checks tools and `.env` variable names (never prints values) | `make doctor` |
| `restore_drill.py` | Backup restore drill into a scratch database | `make restore-drill` |
| `landing-screens.mjs` | Renders the landing site's phone screens from `docs/design-reference` | `make landing-screens` |
| `serve-static.mjs` | Static server used by the Lighthouse scripts in `screenshots/` | `screenshots/landing-*.mjs` |

## Test
`backend/tests/unit/test_api_freeze.py`, `test_deploy_config.py` and `backend/tests/api/test_smoke_script.py` cover them.
