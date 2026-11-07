# deploy/gcp

Cloud Run configuration. Read by `scripts/gcp.py` (deploys) and by backend code (job schedule checks).

| File | What it is |
|---|---|
| `app.toml` | Shared: service sizing, secret names, and every scheduled job with its schedule |
| `production.toml`, `staging.toml`, `demo.toml` | Per-environment project, region (asia-south1), env vars, `FEATURES` |
| `backup-lifecycle.json` | Deletes backup objects after 30 days |

**These files are public. Never put secret values here**; secrets live in Secret Manager (`make secret`).

## Run
```
make deploy ENV=production     # ships to Cloud Run. Asks you to type the environment name first
make rollback ENV=production
```
Deploying is the owner's decision; nothing runs it automatically.

## Test
`backend/tests/unit/test_deploy_config.py` and `test_scheduled_jobs.py` validate these files.
