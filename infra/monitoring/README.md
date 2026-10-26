# Cloud Monitoring as code

Uptime checks, log-based metrics and alert policies for one environment. Nothing here is applied by hand in the console.

    make monitoring ENV=production DRY=1     # print what would be created, with every file
    make monitoring ENV=production           # create or update (asks you to type the environment name)

Each `*.json` is one object. `kind` says which: `logMetric`, `uptimeCheck` or `alertPolicy`. `${NAME}` placeholders are filled by
`scripts/gcp.py` (see `variables()` in `scripts/gcp_monitoring.py`); the rest is the Google API's own JSON, so the field names are
the ones in the Cloud Monitoring and Cloud Logging REST docs. `scripts/gcp_monitoring.py apply` finds each object by its display name
(or metric name) and creates it or updates it, so running it twice is harmless.

Notification channels (email, SMS, the Cloud Console mobile app) are NOT created here: they hold your phone number and email.
Create them once in the console (Monitoring > Alerting > Edit notification channels), then write their display names in
`deploy/gcp/<env>.toml` under `[monitoring] notification_channels`.

| File | What it watches | Alerts when |
|---|---|---|
| `uptime-*.json` | `/ready` on the API, the home page of the app and of the landing site, every minute from several places | down for 2 minutes |
| `alert-5xx.json` | API responses | more than 2% are 5xx for 5 minutes (and at least 3 of them) |
| `alert-latency.json` | API response time | p95 above 1 s for 10 minutes |
| `alert-jobs-failed.json` | scheduled jobs | any `job.failed` log line, or a Cloud Run Job execution that failed |
| `alert-job-overdue.json` | scheduled jobs | `check_jobs` finds a job with no success for 2x its interval |
| `alert-jobs-heartbeat.json` | the `check_jobs` job itself | it has not run for 30 minutes (the watcher is dead) |
| `alert-usage.json` | free-tier limits | the weekly usage report finds something at 70% or more |
