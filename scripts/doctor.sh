#!/usr/bin/env bash
# make doctor: OK/MISSING per tool and per .env variable. Never prints a value.
status=0
for tool in git make docker uv node pnpm; do
  if command -v "$tool" >/dev/null 2>&1; then echo "OK       tool $tool"; else echo "MISSING  tool $tool"; status=1; fi
done
# Only needed to deploy to Google Cloud (RUNBOOK.md "First production deploy"); not a failure when missing.
if command -v gcloud >/dev/null 2>&1; then echo "OK       tool gcloud (optional, for deploying)"; else echo "OPTIONAL tool gcloud (only to deploy: yay -S google-cloud-cli)"; fi
if docker compose version >/dev/null 2>&1; then echo "OK       tool docker compose"; else echo "MISSING  tool docker compose"; status=1; fi
if [ ! -f .env ]; then echo "MISSING  .env (copy .env.example to .env)"; exit 1; fi
# Required = the app refuses to start without it. Anything else has a default and is reported as DEFAULT.
required=" ENV SECRET_KEY DATABASE_URL REDIS_URL ALLOWED_HOSTS CORS_ALLOWED_ORIGINS APP_URL LANDING_URL API_URL SEED_CITY_NAME SEED_CITY_LAT SEED_CITY_LNG "
while IFS= read -r name; do
  if grep -Eq "^${name}=.+" .env; then echo "OK       env $name"
  elif [[ "$required" == *" $name "* ]]; then echo "MISSING  env $name"; status=1
  else echo "DEFAULT  env $name (not set, optional)"; fi
done < <(grep -Eo '^[A-Z][A-Z0-9_]*=' .env.example | tr -d '=' | grep -v '^NEXT_PUBLIC_')
exit $status
