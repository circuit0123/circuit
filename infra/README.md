# infra

Infrastructure templates that are not part of the service config.

| Folder | What it is |
|---|---|
| `monitoring/` | Cloud Monitoring alerts, metrics and uptime checks (templates with `${ENV}`, `${API_HOST}`). See `monitoring/README.md` |

## Run
```
make monitoring ENV=staging    # applies the templates through scripts/gcp_monitoring.py
```

## Test
`backend/tests/unit/test_monitoring_config.py` checks that every template is valid and wired up.
