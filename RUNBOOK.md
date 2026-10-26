# Circuit — runbook

What to do when something needs a human. Sections are added by the stage that builds the thing (LAUNCH.md Stage 11 completes this file:
restore, outage, takedown; deploy, rollback and secrets are below). Commands are `make` targets (COMMANDS.md).

## First production deploy on Google Cloud

Goal: the backend API and its scheduled jobs running on Google Cloud (Mumbai), behind the invite-only beta. Do the steps in
order. Steps marked **[YOU]** need your accounts or your decision; every `make` command prints what it will run and asks you to
type `production` first. Allow 2–3 hours for the first time, mostly waiting on accounts and DNS.

What lives where: the **API and the jobs** run on Google Cloud (Cloud Run, Cloud Scheduler). The **database, sign-in, files and
realtime** stay on Supabase. **Redis** is Upstash. The **app and landing site** are on Vercel. Your Google Cloud project and your
Supabase project may belong to different Google accounts: they only meet through addresses and keys kept in Secret Manager.

### A. Before you touch Google Cloud
1. **[YOU] Supabase.** Create the production project **in Mumbai (ap-south-1)** and choose the **Pro** plan (the free plan pauses after
   a week unused and has no backups; PRODUCTION.md §6 explains PITR, which is a separate paid add-on). Then:
   - Database → Extensions: turn on `postgis` and `vector`.
   - Authentication → Providers: turn on Google and Email (one-time code). Authentication → Signing keys: use an asymmetric key
     (ES256), which is what `SUPABASE_JWT_ALG` expects.
   - Authentication → URL configuration: Site URL = your app address; Redirect URLs = `<app address>/auth/callback` and
     `http://localhost:3000/auth/callback`.
   - Storage: create the buckets the app uses: `posts`, `messages` and `private` (all private).
   - Connect → **Transaction pooler**: copy the address. It looks like
     `postgres://postgres.<ref>:<password>@aws-0-ap-south-1.pooler.supabase.com:6543/postgres`. Port **6543** is the point. If the
     password contains `@ : / #`, URL-encode them.
   - Project settings → API: copy the project URL (`https://<ref>.supabase.co`) and the `service_role` key (backend only, never Vercel).
2. **[YOU] Google sign-in.** In any Google Cloud project (it can be a different account from the one running the API), APIs & Services
   → Credentials → Create OAuth client ID → Web application. Authorised JavaScript origins: your app address and
   `http://localhost:3000`. Authorised redirect URI: `https://<ref>.supabase.co/auth/v1/callback`. Paste the client ID and secret
   into Supabase → Authentication → Providers → Google.
3. **[YOU] Upstash.** Create a Redis database in the Mumbai region. Copy the address that starts with **`rediss://`** (two s: TLS),
   not the REST address. The app refuses a plain `redis://` address in production.
4. **[YOU] Resend.** Add your domain and publish the SPF, DKIM and DMARC records it shows. Production refuses Resend's
   `@resend.dev` test sender, so the app cannot start until `EMAIL_FROM` uses your verified domain. Create an API key.
5. **[YOU] LLM key.** An Anthropic API key (production uses the paid tier, whose terms exclude training on our data). Set a monthly spend limit on it in the Anthropic console now: the code has no cap of its own yet.
6. **[YOU] Vercel.** The production app and landing projects exist (LAUNCH.md Stage 5). You will set their variables in step 15.

### B. Google Cloud, once
7. **Install and log in** (Arch / Omarchy):
   ```bash
   yay -S google-cloud-cli
   gcloud auth login            # a browser opens: pick the Google account that owns the Cloud project
   make doctor                  # gcloud should now say OK
   ```
8. **[YOU] Create the project and attach billing** (the $300 credits come with the billing account). Pick your own project id:
   ```bash
   gcloud projects create circuit-prod-<something-unique>
   gcloud billing accounts list                                   # copy the ACCOUNT_ID
   gcloud billing projects link circuit-prod-<something-unique> --billing-account=<ACCOUNT_ID>
   gcloud config set project circuit-prod-<something-unique>
   ```
9. **Fill in `deploy/gcp/production.toml`.** Replace every `<placeholder>`: project id, billing account, `budget` (an amount in the
   currency of your billing account, e.g. `5000INR`; alerts at 50/80/100% of it), the app and landing addresses, `CORS_ALLOWED_ORIGINS`
   (exactly the app address, no slash), `SUPABASE_URL`, `EMAIL_FROM`, `SUPPORT_EMAIL`, the grievance officer details, and a random
   `ADMIN_PATH` (`python -c "import secrets; print(secrets.token_urlsafe(12))"` + `/`). Commit it: it holds no secrets.
10. **Set up the project:** `make gcp-setup ENV=production`. Read the list, type `production`. It turns on the services, creates the
    image repository, two service accounts (one runs the API and jobs, one may only start jobs), an empty slot per secret, and the
    budget. Success: `Done.` Run it again any time: it skips what exists. If the budget step is refused, your account needs the
    *Billing Account Administrator* role.
11. **Store the secrets**, one at a time (the value is typed at a hidden prompt, never on a command line):
    ```bash
    python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # copy this for SECRET_KEY
    make secret ENV=production NAME=SECRET_KEY
    make secret ENV=production NAME=DATABASE_URL                 # the transaction pooler address from step 1
    make secret ENV=production NAME=REDIS_URL                    # the rediss:// address from step 3
    make secret ENV=production NAME=SUPABASE_SERVICE_ROLE_KEY
    make secret ENV=production NAME=ANTHROPIC_API_KEY
    make secret ENV=production NAME=RESEND_API_KEY
    ```
    The list for an environment is in `deploy/gcp/app.toml` and `<env>.toml`. `make deploy` refuses to start until every one has a value.

### C. The first deploy
12. **Rehearse.** `make deploy ENV=production DRY=1` prints the whole plan and the files it would write, and runs nothing. Read it once.
    Optionally prove the image works first: `make build-api`, then `make run-prod-local` in one terminal and
    `make smoke URL=http://localhost:8080` in another.
13. **Deploy:** `make deploy ENV=production`, type `production`. It checks the secrets, builds and uploads the image (the first upload is
    several hundred MB), runs the migrations and waits, creates the service, then smoke-tests it. It ends with the smoke test
    (`OK: 0 failed`) and `Done.` Write down the API address from the smoke output
    (`https://circuit-production-api-<number>.asia-south1.run.app`).
    - It stops at the first failure and leaves the old version serving. Fix the cause (table below) and run the same command again.
14. **Smoke from outside:** `make smoke URL=<api address> ORIGIN=<app address> EXPECT_ENV=production`. Every line should be `PASS`.
    Check the cold start once: wait 15 minutes, then time `curl -s -o /dev/null -w '%{time_total}\n' <api address>/health`. Write the
    number here: `<COLD START SECONDS>`.
15. **Vercel.** In the production app project set `NEXT_PUBLIC_API_URL=<api address>` (and the other variables in PRODUCTION.md §2a),
    then redeploy; do the same for the landing project. Sign in with Google once from the real app address.
16. **Create the first super admin.** `admin_user` asks for a password at a prompt, which a Cloud Run job cannot do, so run it from your
    laptop against the production database, for this one command only:
    ```bash
    read -rs -p "Production DATABASE_URL: " PGURL; echo
    DATABASE_URL="$PGURL" DATABASE_POOLER=transaction make admin-user USER_NAME=<your-name>
    unset PGURL
    ```
    Add the printed `otpauth://` link to your authenticator app, then open `<api address>/<ADMIN_PATH>` and sign in. (The dev-only
    commands such as `reset-demo` refuse to run against a remote database, so this cannot wipe anything.) Invite codes are made in
    the admin (Beta → Invite codes).
17. **Check the schedule.** `make jobs` lists it. Run one job by hand: `make jobs-run ENV=production JOB=compute_matches`, then
    `make logs ENV=production JOB=compute_matches`: you should see `job.start` and `job.end` (or `job.skipped` with a reason).
    In the Cloud console → Cloud Scheduler, every trigger should show a recent successful run after its time.

### D. Do next
18. **Rollback drill (once, while nothing depends on it).** Make a small harmless commit, `make deploy ENV=production`, then
    `make rollback ENV=production`: the smoke test passes against the previous revision. Deploy again to go forward.
19. **Custom domain for the API** (when you buy the domain; PRODUCTION.md §2a). Check what your project allows:
    `gcloud beta run domain-mappings create --service circuit-production-api --domain api.<domain> --region asia-south1`.
    - If it works, add the DNS records it prints, wait for the certificate, then in `production.toml` set `API_URL = "https://api.<domain>"`,
      `ALLOWED_HOSTS = "api.<domain>,.run.app"`, `CSRF_TRUSTED_ORIGINS = "https://api.<domain>,https://*.run.app"`, update Vercel, and redeploy.
    - If domain mappings are not available in `asia-south1`: the cheap route is a **Firebase Hosting** site whose rewrite sends `/api/**`
      to the Cloud Run service (free, same region); the sturdy route is a global external load balancer in front of Cloud Run
      (about $18/month). Ask before building either.
20. **Logs and alerts.** Set Cloud Logging retention to 30 days (section below). Uptime checks and failure alerts arrive in Stage 8.

### Rotating a secret
`make secret ENV=production NAME=<NAME>` stores a new version (old versions stay), then `make deploy ENV=production` so new instances
pick it up. If the new value is wrong, `make rollback` does not help (it is the secret, not the code): run `make secret` again with the old value.

### When a deploy fails
| What you see | Cause and fix |
|---|---|
| `X has no value yet` | `make secret ENV=production NAME=X` |
| Docker says `denied` when pushing | `gcloud auth configure-docker asia-south1-docker.pkg.dev`, then deploy again |
| Migration job failed | `make logs ENV=production JOB=migrate`. The old version is still serving. Fix, commit, deploy again. Migrations are written so the previous code keeps working with them |
| The service does not become ready; log shows `ValidationError` / `Value error, ...` | The app refused to start; the message names the variable (`make logs ENV=production`). Fix `production.toml` or the secret, deploy again |
| `/ready` fails in the smoke test | Postgres does not answer: check `DATABASE_URL` (port 6543, URL-encoded password, project not paused) and `DATABASE_POOLER = "transaction"` |
| `/ready` is `degraded` | Redis is down or out of free commands: the app works from Postgres; check `REDIS_URL` and the Upstash dashboard |
| `FAIL CORS ...` | `CORS_ALLOWED_ORIGINS` must be exactly the app address you pass as `ORIGIN` |
| `Invalid HTTP_HOST header` (400) | The address is not in `ALLOWED_HOSTS` |
| A job log says `skipped: flag off` | Normal: that feature is off for everyone. Switch it on in Django admin (Core → Feature flags) |
| A job log says `skipped: already running` | Normal if a previous run is still going. A run killed by a timeout frees itself after its lease (10–70 minutes) |

### What it costs per month
Prices change: confirm in the Google Cloud pricing calculator before relying on a number. Estimates are for the closed beta (tens of
invited members), in US dollars, billed in your account's currency. The $300 credit covers everything on the Google Cloud side.
Mumbai is, as far as could be confirmed, in Google's more expensive "Tier 2" price group for Cloud Run, so the figures below leave room for that.

| Piece | Setting | About per month | Why |
|---|---|---|---|
| Cloud Run API | min 0, max 3 | $0–2 | Free monthly allowance (180,000 vCPU-seconds, 2 million requests) covers a beta; you pay only while a request runs. First request after quiet: ~5–10 s |
| Cloud Run API, always warm | min 1 | +$8–12 | One instance kept running so nobody waits. Switch on before public launch: `min_instances = 1` in `production.toml` |
| Cloud Run Jobs | 8 jobs, the 5-minute one dominates | $0–3 | ~9,000 short runs a month (about 10 s each) plus a few longer daily/weekly ones; inside the free allowance of 240,000 vCPU-seconds |
| Cloud Scheduler | 6 triggers now, 8 later | $0.30–0.50 | First 3 are free, then $0.10 each. This is why the frequent jobs share one trigger: five separate ones would start ~33,000 containers a month |
| Secret Manager | 6 secrets | ~$0.50 | ~$0.06 per active secret version + a few cents for reads. Destroy old versions you no longer need |
| Artifact Registry | newest 5 images | ~$0.30 | ~$0.10 per GB over the first 0.5 GB; the image is ~0.6 GB compressed |
| Cloud Logging | JSON logs | $0 | Free up to 50 GiB a month; probes are not logged |
| Network out | to members and Supabase | $0–1 | Small JSON responses |
| **Google Cloud total** | | **about $1–7** | With min instances 1: about $9–19 |
| Upstash Redis | free tier | $0 | 500,000 commands a month, 256 MB. If you hit it the app falls back to Postgres; pay-as-you-go is $0.20 per 100,000 commands, i.e. about $1 for the next 500,000 |
| Supabase | **Pro** | **$25** | Needed for real members (backups, no pausing). Not covered by the Google credits. **PITR is an extra, about $100/month**: decide before launch (PRODUCTION.md §6). Free plan: $0 but pauses after a week unused and has no backups |
| Resend | free | $0 | 3,000 emails a month, 100 a day |
| Anthropic API | onboarding extraction | cents | One short call per sign-up. **The monthly cap promised in PRODUCTION.md §14 row 20 is not in the code yet**: set a spend limit in the Anthropic console (Settings → Limits) before real members |
| Domain | | ~₹800–1,500 a year | |
| **Everything, closed beta** | | **about $26–32** | Almost all of it is Supabase Pro |

## Retention

What is removed, when, and by what. The daily job is `retention_cleanup` (`make retention` runs it by hand; Cloud Scheduler runs it
once a day from Stage 5). It is idempotent and logs **counts only**.

| What | After | Done by |
|---|---|---|
| Accounts that signed in but never accepted the terms | 30 days (`UNVERIFIED_ACCOUNT_DAYS`) | `retention_cleanup`, through the same pipeline as "delete my account". Staff roles are never purged |
| Data export files | The download link lasts 24 hours (`EXPORT_LINK_HOURS`); the file is deleted when the link expires | `retention_cleanup` |
| Rejected waitlist entries | 90 days (`REJECTED_WAITLIST_DAYS`) | `retention_cleanup` |
| Sent and failed outgoing email records | 30 days (`EMAIL_KEEP_DAYS`) | `send_emails` |
| Product events | Kept (pseudonymous: ids and types only) | nothing |
| Orders, payments, invoices | `FINANCIAL_RECORD_RETENTION_YEARS` (8, **accountant to confirm**) | nothing deletes them; Stage 4e |
| **Request logs** | **30 days** | **Cloud Logging, NOT code.** See below |

### Request-log retention is a Cloud Logging setting
The API writes one JSON log line per request (method, path, status, time, request id, member id; never names, emails, phones, message
text or tokens). How long those lines are kept is decided by the retention of the Cloud Logging bucket that receives them, not by the
application. **Set the `_Default` bucket (or the bucket our log sink writes to) to 30 days** for staging and production and check it
after any change to log routing. This is a `[YOU]` step on cloud resources (ask before running it); until it is set, logs follow Google's default (30 days for `_Default`,
but confirm it, and confirm it was not raised for a longer-lived sink). Record the date checked here: `<DATE CHECKED>`.

## Data requests (DPDP)

Members do these themselves in the app (Settings → Your data). The jobs below do the work; you only step in when one is stuck.

| Request | How it works | If it is stuck |
|---|---|---|
| **Export** | `POST /api/me/export` → `build_exports` (every 5 min) builds the zip in the private bucket and emails a 24-hour link | `make job NAME=build_exports`. A row in `accounts_dataexport` with status `failed` gave up after 3 tries (look for `export_failed` in the logs: the error class only). The member can ask again |
| **Correction** | The member edits their profile (`PATCH /api/me`). Or they write to support | Edit the Member in Django admin (audit-logged) |
| **Deletion** | `POST /api/me/deletion` locks the account at once; `delete_accounts` (every 5 min) removes the sign-in, files and personal data and turns the row into a "Deleted member" tombstone | Look for `account_erase_failed` in the logs. Usual causes: Supabase Auth or Storage unreachable. The account stays locked; the next run retries. `make job NAME=delete_accounts` runs it now |
| **Grievance / question** | `POST /api/support` emails `SUPPORT_EMAIL` (grievances: `GRIEVANCE_EMAIL`) with the member id and Reply-To, and sends the member a reference (`S-<id>`) | Acknowledge within the time the Grievance Officer page promises. The reference is the id of the outgoing email row |

Never delete a Member row by hand: orders and payments (Stage 4e) point at it. Use the deletion pipeline.

Dev only: `make export MEMBER=<id>` and `make delete-account MEMBER=<id>` do one member immediately.

## Landing site: feature flags and the join switch are baked in at build time
`apps/landing` reads `GET /api/config` once while it builds (`src/lib/features.ts`), so the pages are static. `/investors` shows the app button when
`investor_mode` is on and a waitlist form ("Investor access opens soon.") when it is off; `/partners` shows the app button when `partner_mode` is on and a
contact form when it is off; the home investor tile follows `investor_mode` too. **After changing either flag in Django admin or `FEATURES`, redeploy the
landing site** (Vercel: redeploy `circuit-landing`, or trigger its deploy hook), otherwise visitors keep seeing the old state. `NEXT_PUBLIC_JOIN_LIVE` is baked in the same way: while it is unset or `false` every call to action opens the waitlist form; set it to `true` in the landing
project only after the app ships `/join` and is deployed, then redeploy. If the API can't be reached
during a build, every flag is treated as off and the build log says `[landing] Could not read … /api/config`: check the log before shipping a deploy that
should have the app buttons.

## Privacy checks before real users
- `GRIEVANCE_OFFICER_NAME`, `GRIEVANCE_EMAIL`, `GRIEVANCE_ADDRESS` are real (not `<PLACEHOLDER>`).
- `POLICY_VERSION` matches the published text (docs/legal/ after the lawyer's review).
- Cloud Logging retention is 30 days (above).
- `FINANCIAL_RECORD_RETENTION_YEARS` is confirmed by the accountant.
