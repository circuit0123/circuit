# Circuit — runbook

What to do when something needs a human. Day-to-day operation (deploy, rollback, restore, secrets, alerts) is under "Operating it" below;
the beta's daily admin jobs (invites, waitlist, flags, takedowns), the load test, the incident checklist and the contact list are under
"Running the beta". Commands are `make` targets (COMMANDS.md). Django admin is at the secret path in `ADMIN_PATH` (a password plus a 2FA code).

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
   - Storage: create the buckets the app uses: `posts`, `messages`, `avatars` (profile photos and startup logos) and `private` (all private).
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
20. **Logs, alerts, backups and CI.** Set Cloud Logging retention to 30 days (section below). Then do "One-time setup for monitoring,
    backups and CI" under "Operating it": notification channels, `make monitoring`, the backup key, the first `make backup-now` and
    `make restore-drill`, and the GitHub settings that let CI deploy without a key.

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
| Cloud Run Jobs | 14 jobs (8 on a schedule), the 5-minute one dominates | $0–3 | ~9,000 short runs a month (about 10 s each) plus a few longer daily/weekly ones; inside the free allowance of 240,000 vCPU-seconds |
| Cloud Scheduler | 8 triggers now, 10 later | $0.50–0.70 | First 3 are free, then $0.10 each. This is why the frequent jobs share one trigger: five separate ones would start ~33,000 containers a month |
| Secret Manager | 8 secrets | ~$0.60 | ~$0.06 per active secret version + a few cents for reads. Destroy old versions you no longer need |
| Artifact Registry | newest 5 images | ~$0.30 | ~$0.10 per GB over the first 0.5 GB; the image is ~0.6 GB compressed |
| Cloud Logging | JSON logs | $0 | Free up to 50 GiB a month; probes are not logged |
| Cloud Monitoring | 3 uptime checks, 7 alert policies, 4 log metrics | $0 | Inside the free allowance. SMS alerts are free; the Cloud Console app sends push for free |
| Cloud Storage | the backup bucket | $0–0.10 | ~30 nightly dumps of a database under 500 MB, deleted after 30 days |
| Sentry | Developer (free) plan | $0 | 5,000 errors a month. Past that it drops events, it does not bill you |
| Network out | to members and Supabase | $0–1 | Small JSON responses |
| **Google Cloud total** | | **about $1–7** | With min instances 1: about $9–19 |
| Upstash Redis | free tier | $0 | 500,000 commands a month, 256 MB. `REDIS_LEAN=true` (set in the deploy files) keeps fewer copies in Redis so the month lasts. If you hit it the app falls back to Postgres; pay-as-you-go is $0.20 per 100,000 commands, i.e. about $1 for the next 500,000 |
| Supabase | **Pro** | **$25** | Needed for real members (backups, no pausing). Not covered by the Google credits. **PITR is an extra, about $100/month**: decide before launch (PRODUCTION.md §6). Free plan: $0 but pauses after a week unused and has no backups |
| Resend | free | $0 | 3,000 emails a month, 100 a day. The app keeps its own budget (90 a day, 2,800 a month): past it notification emails are in-app only, and invites and exports wait for tomorrow |
| Anthropic API | onboarding extraction | cents | One short call per sign-up. `LLM_DAILY_CALL_LIMIT` (500 in `production.toml`) stops the calls for the day when it is reached: onboarding then uses the manual pickers. Also set a spend limit in the Anthropic console (Settings → Limits) as the second lock |
| Domain | | ~₹800–1,500 a year | |
| **Everything, closed beta** | | **about $26–33** | Almost all of it is Supabase Pro |

## Operating it

Day-to-day. Each section starts with what you see and ends with how you know it worked. Alerts (phone, email) link here by section name.

### One-time setup for monitoring, backups and CI
Do this once, after the first production deploy (A–C above). Nothing here is automatic: every command asks you to type `production`.

1. **Notification channels [YOU].** Cloud Console → Monitoring → Alerting → Edit notification channels. Add an **email** channel and an
   **SMS** channel (or install the Cloud Console mobile app and add its push channel; SMS needs your phone verified). Name them exactly as
   `[monitoring] notification_channels` in `deploy/gcp/production.toml` says (for example `Circuit production on-call email`).
2. **Alerts and uptime checks.** `make monitoring ENV=production DRY=1` prints every object it would create; then
   `make monitoring ENV=production`. It stops, naming the channel, if one does not exist. Safe to run again after any change.
   Check: Cloud Console → Monitoring → Alerting shows 7 policies, Uptime checks shows 3 passing.
3. **Sentry [YOU].** Create a project (platform: Django) at sentry.io, copy its DSN, then `make secret ENV=production NAME=SENTRY_DSN`
   and `make deploy ENV=production`. In Sentry: Alerts → "Issue alerts" → notify you by email on every new issue. Errors arrive with the
   environment and release (the commit) attached; names, emails, phone numbers, tokens and request bodies are removed before they leave
   the server (`backend/core/monitoring.py`; the tests in `test_sentry_scrub.py` prove it).
4. **Backup key [YOU].** On your laptop: `age-keygen -o backup.key` (Arch: `sudo pacman -S age`). It prints `Public key: age1...`.
   Put that public key in `production.toml` as `BACKUP_AGE_RECIPIENT`. **Save `backup.key` in your password manager and delete the file
   from the laptop**: without it no backup can ever be opened; with it anyone holding a backup can read every member's data.
5. **Backup database address [YOU].** Supabase → Project Settings → Database → Connection string → **Session pooler** (port 5432 on the
   pooler host) or the direct address, not port 6543. `make secret ENV=production NAME=BACKUP_DATABASE_URL`.
6. **Bucket, keyless deploys.** `make gcp-setup ENV=production` again: it adds the private backup bucket (30-day deletion), the Workload
   Identity pool restricted to the repository in `deploy/gcp/app.toml`, and the deploy account. At the end it prints two values.
7. **GitHub settings [YOU].** Repository → Settings:
   - **Environments** → New environment `production`: tick **Required reviewers** (you) and add the two variables `WIF_PROVIDER` and
     `DEPLOY_SA` that step 6 printed. Do the same for `staging` and `demo` when you create them (no reviewers needed).
   - **Branches** → Add rule for `main`: **Require a pull request**, **Require status checks to pass** → choose **ci**.
     ("ci" is the last job in `.github/workflows/ci.yml`; it is green only when lint and check both are.)
   - **Variables** (repository): `STAGING_DEPLOY_ENABLED=true` and `DEMO_DEPLOY_ENABLED=true` only once those environments exist.
   - Delete the temporary deploy key and the temporary Vercel token from Stage 0 (Settings → Secrets) and revoke them at their source.
8. **First backup and drill.** `make backup-now ENV=production` → "backup written". Then on your laptop, with Docker running:
   `AGE_KEY_FILE=~/backup.key make restore-drill ENV=production` (needs your own `gcloud auth login` with read access to the bucket).
   Write down how many minutes it took and the date here: `<DATE, MINUTES>`. Repeat every quarter (put a reminder in your calendar).
9. **Rollback drill (once).** Merge a harmless commit (a comment), run "deploy production" from the Actions tab, then
   `make rollback ENV=production` and check that `make smoke` passes against the previous revision. Deploy forward again by running the workflow once more.
   This proves the thing you will need in a hurry.

### Deploy
There are two ways. Both do the same thing in the same order and stop at the first failure.

**From GitHub (the normal way).** Merge a pull request to `main` (CI must be green; the `ci` check blocks the merge otherwise).
- **Staging** (when `STAGING_DEPLOY_ENABLED=true`) deploys by itself after CI succeeds on `main`.
- **Production**: Actions → **deploy production** → Run workflow (leave the commit empty for the tip of `main`). The run first checks that the
  commit is on `main` with a green `ci`, then **waits for a reviewer to approve** (that is the "production" environment). After approval it
  builds the image for x86_64 and ARM64, pushes it, runs the migrations as a job, creates the new revision at 0% traffic, smoke-tests
  its private address, moves traffic, and smoke-tests the live address. **If that last test fails, traffic goes back to the previous
  revision by itself** and the run ends red.
- **Demo**: push a tag like `v1.0.0` (when `DEMO_DEPLOY_ENABLED=true`); the demo is deployed and its data reset.

**From your laptop** (`make deploy ENV=production`, COMMANDS.md §9): the same plan, with you typing `production` instead of a reviewer approving.
Use it if GitHub is down or CI itself is what you are fixing. It needs a clean `git status`.

How you know it worked: the last lines of the run say `OK: 0 failed` for the smoke test and `Done.`; `make jobs` still lists every job.
A red run is explained step by step in "When a deploy fails" above. A failed migration or a failed private smoke test changes nothing for
members: the old version keeps serving.

### Rollback
Use it when a deploy went out and something is wrong that the smoke test did not catch (a screen is broken, errors in Sentry started with the deploy).
1. `make rollback ENV=production`. Type `production`. It sends 100% of traffic to the previous revision and points the jobs at the same image. Seconds.
   For an older one: `make rollback ENV=production REVISION=circuit-production-api-00012-abc` (revision names: Cloud Console → Cloud Run).
2. `make smoke URL=<the API address> ORIGIN=<the app address> EXPECT_ENV=production` should say `OK: 0 failed`.
3. Database migrations are NOT undone. Every migration is written so the previous code still works with it (add first, remove later). If you ever
   meet one that is not, restore from a backup instead (below), and write down what happened.
4. Fix forward: revert or fix the commit in a pull request, and deploy again. Do not leave production on an old revision for days: the next
   deploy moves traffic forward again, and `make jobs-run` of a job uses the newest image.
The automatic rollback inside "deploy" is the same move, done for you when the live smoke test fails.

### Restore from a backup
**What is backed up.** Every night at 02:30 India time the job `backup_db` dumps the `public` schema (all of Circuit's data) and the `auth`
schema (the sign-in accounts), encrypts it with your public key, and stores it in `gs://<project>-circuit-production-backups/production/` for 30 days.
Not in it: **files** (post and message images, data exports) live in Supabase Storage. On Supabase Pro the daily backups Supabase itself keeps
cover the database too; this one is yours, in your account, and it is what the drill proves.

**Before you restore anything, stop and think.** A restore replaces data with the state of a past night: everything members did since is lost.
If only one thing is wrong (a bad migration on one table, a deleted post), fixing that one thing is better than a restore.

**Practice (safe, any time): `make restore-drill`.** It never touches the real database. See the one-time setup, step 8.

**A real restore.** Allow 1–2 hours. Do it into a NEW place first, then switch.
1. Put the app in a safe state. `BETA_MODE` already keeps strangers out; tell invited members it is down. Stop the schedules from writing:
   Cloud Console → Cloud Scheduler → pause the triggers (or `gcloud scheduler jobs pause <name> --location asia-south1`).
2. Download and open the newest backup on your laptop (needs the private key and `age`):
   `gcloud storage ls gs://<project>-circuit-production-backups/production/` then `gcloud storage cp gs://.../production/<stamp>.dump.age .` and
   `age --decrypt --identity ~/backup.key --output restore.dump <stamp>.dump.age`. Also fetch `<stamp>.counts.json` (row counts to check against).
3. Create a **new Supabase project** (same region, same extensions: postgis and vector, plus Google and email sign-in). A new project is the safe
   route: your old one stays untouched until you are sure. (Restoring over the old project is possible with `pg_restore --clean`, but only do that if
   you cannot create a new one.)
4. Restore into it with the SESSION pooler or direct address, using a `pg_restore` of version 17 or newer. Two parts, because a new Supabase project
   already has its own `auth` tables:
   - Circuit's data: `pg_restore --schema=public --no-owner --no-acl --dbname "<new project's session address>" restore.dump`.
     Messages about Supabase-only roles or extensions that already exist are normal; a table that fails to load is not.
   - The sign-in accounts (without them nobody's `auth_user_id` matches a Member any more):
     `pg_restore --data-only --disable-triggers --schema=auth --table=users --table=identities --dbname "<same address>" restore.dump`.
   **This is the least rehearsed step.** The drill proves the `public` part; rehearse this one on a scratch Supabase project before you ever need it
   (`PROGRESS.md`, "Cloud setup I must run later"). Supabase Pro's own daily backup, restored from its dashboard, brings back `auth` and `public` together:
   if you are on Pro and the problem is recent, that is the simpler route.
5. Check the counts against `<stamp>.counts.json` (the drill's script does exactly this: `python3 scripts/restore_drill.py --help`).
6. Point production at the new project: `make secret` for `DATABASE_URL`, `BACKUP_DATABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`; edit `SUPABASE_URL` in
   `production.toml` and the Supabase variables in Vercel; then `make deploy ENV=production`. Members sign in again with the same accounts (the `auth` schema came with the dump).
7. Resume the schedules. Run `make job-health ENV=production` and `make smoke ...`. Files: if Storage is gone too, post and message images are lost (the
   posts remain; the images show as missing). Tell members what happened (DPDP: a data breach has its own duties; ask the Grievance Officer's lawyer if data was exposed).
8. Write down the date, the backup used, and how long it took.

### Rotate a secret
Do this on a schedule (once a year), when someone who knew a secret leaves, or at once if one may have leaked (it was pasted somewhere, a laptop was lost).
1. **If it may have leaked, change it at its source first** (Supabase: Project Settings → API / Database → reset the password or key; Anthropic, Resend,
   Sentry, Upstash: create a new key and revoke the old). Rotating only in Secret Manager does not stop someone who holds the old value.
2. `make secret ENV=production NAME=<NAME>`: type the new value at the hidden prompt. Old versions stay in Secret Manager.
3. `make deploy ENV=production` (or run "deploy production" in GitHub): running instances read secrets only when they start, so a new revision is needed.
4. `make smoke ...` says `OK: 0 failed`; in Sentry no new errors.
5. Destroy the old version once all is well (Cloud Console → Secret Manager → the secret → Versions → Destroy), so a leaked old value is dead.

| Secret | What else to know |
|---|---|
| `SECRET_KEY` | Signs the Django admin session and demo tokens: everyone in the admin is logged out. Members stay signed in (Supabase signs their tokens) |
| `DATABASE_URL`, `BACKUP_DATABASE_URL` | Reset the database password in Supabase first; both addresses contain it, so change BOTH secrets and deploy once. Until you do, the app and the nightly backup fail |
| `SUPABASE_SERVICE_ROLE_KEY` | Reset in Supabase (API settings). Uploads, deletions and Realtime fail until the new value is deployed |
| `REDIS_URL` | Reset in Upstash. The app works from Postgres meanwhile |
| `ANTHROPIC_API_KEY`, `RESEND_API_KEY`, `SENTRY_DSN` | Create the new key first, deploy, then revoke the old one: no gap |
| Workload Identity / GitHub | There is no key to rotate. If the GitHub repository is compromised, remove the `production` variables `WIF_PROVIDER`/`DEPLOY_SA` and the deploy account's role bindings (Cloud Console → IAM) |
| The backup key (age) | A new key pair does not open old backups. Make the new one, change `BACKUP_AGE_RECIPIENT`, deploy, and KEEP the old private key until the last backup made with it is 30 days old |

### A job is overdue
**What you see:** an alert "a scheduled job is overdue" (a job has had no success for twice its interval), "a scheduled job failed", or "job watcher has stopped".
1. `make job-health ENV=production` runs the watcher once and shows its newest log lines: which job, since when (`job.overdue`, with the job's name and the reason).
   As a super admin you can also open `GET /api/health/jobs` with your token (or Django admin → Core → Job runs) to see every job's last result and last error.
2. `make logs ENV=production JOB=<name>` shows what the job's last runs did. The last error is also stored: class name and a short message with emails, phones and tokens removed.
3. Find the cause in this order:
   - **`skipped: flag off`** is normal (that feature is off for everyone), and such a job is never overdue.
   - **`skipped: already running`** repeatedly: a previous run is stuck holding its lease; it frees itself after the lease (10–70 minutes). If it does not, check Cloud Run → Jobs → executions.
   - **Failed** with an error class: read the Sentry issue tagged `job:<name>`. Common: Supabase or Redis unreachable (check their status pages), a bad migration, a missing secret after a rotation.
   - **No runs at all:** Cloud Scheduler → the trigger `circuit-production-<job>` → is it paused, or does its last run show a permission error? The scheduler account may only start jobs; `make deploy` recreates the trigger.
   - **Killed (out of memory or time):** Cloud Run → Jobs → the execution says "Memory limit exceeded" or "deadline". Raise `memory` or `timeout_seconds` for that job in `deploy/gcp/app.toml` and deploy.
4. Run it by hand once the cause is fixed: `make jobs-run ENV=production JOB=<name>`, then `make job-health ENV=production`: the job is no longer listed as overdue.
5. **"Job watcher has stopped"** means `check_jobs` itself (part of the `every-5-min` job) has not run for 30 minutes, so nothing is watching the rest. Look at the
   `circuit-production-every-5-min` job and its Scheduler trigger first. While it is down, the backups and the daily jobs are the thing to check by hand: `make jobs`, then Cloud Run → Jobs.
Daily jobs are only called overdue after two days of silence; if the **backup** job is the one that failed, take one by hand today: `make backup-now ENV=production`.

### Sentry alert triage
**What you see:** an email from Sentry about a new issue, or the alert "API 5xx rate high" / "API slow".
1. Open the Sentry issue. Read the title, the stack trace (the last frame in our code is usually the cause), and the tags: `environment`, `release` (the commit the error first appeared in), `job` (for scheduled jobs).
   There are no names, emails or request bodies in it by design. To find the request, copy the time and look up the `request_id` in `make logs ENV=production`.
2. **Decide how bad:**
   - Many events, new since a deploy (`release` is the newest commit): a regression. `make rollback ENV=production`, then fix forward.
   - One or two events, a rare input: fix in a normal pull request.
   - An error from a third party (Supabase, Upstash, Resend, the AI provider timing out): check their status page; the app has fallbacks (Redis → Postgres, email → retry later, AI → manual pickers) so this is usually not urgent unless it persists.
   - Out of memory or timeouts: Cloud Run → the service → Metrics. Raise memory, or look for the slow query.
3. **API slow (p95 above 1 s for 10 minutes):** with `min_instances = 0`, a quiet hour with a couple of cold starts (5–10 s each) can trigger this by itself. Look at Cloud Run → Metrics → request count: if there was almost no traffic, it is cold starts. If real traffic is slow: check Supabase (Dashboard → Reports → slow queries) and Upstash. If members complain about cold starts, set `min_instances = 1` (about $8–12 a month).
4. Resolve the issue in Sentry once fixed; "Ignore until it happens 10 times" for noise you have decided is harmless.
5. If an error shows personal data despite the scrubbing, that is a bug: delete the event in Sentry (Issue → Delete) and fix `backend/core/monitoring.py` with a new test.

### Site or API is down
**What you see:** the alert "site or API down" (an uptime check failed from several places for 2 minutes).
1. `make smoke URL=<the API address> ORIGIN=<the app address>` from your laptop. It names what failed.
2. API down: `make logs ENV=production` for the newest lines. If it began with a deploy, `make rollback ENV=production`. If `/ready` fails, Postgres is unreachable: Supabase status page, and check the project is not paused (free plan) or out of connections.
3. App (Vercel) or landing down: Vercel dashboard → the project → Deployments → "Instant rollback" to the last good deployment. Check the Vercel status page.
4. Tell invited members if it lasts more than an hour (the waitlist email or your community channel).

### A free-tier limit is nearly hit
**What you see:** the alert "a free-tier limit is at 70%", or you ran `make usage-report ENV=production` and a line is marked `!!`.
Nothing is broken yet. Each limit has a safe default behaviour when it is reached, listed below, so there is time to choose.

| Limit (free plan) | What happens at the limit | What to do now |
|---|---|---|
| Database 500 MB (Supabase) | Writes fail: the app breaks | The retention job already removes old events, notifications, snapshots. Check `make usage-report` for what grew. Run `make retention`. If it is still high, upgrade to Pro ($25/month, 8 GB) and set `FREE_TIER_LIMITS` to `{"database_bytes": 8589934592}` |
| File storage 1 GB (Supabase) | Uploads fail | Images are already compressed (`MEDIA_WEBP_QUALITY`). Lower it to 65, or upgrade. The Supabase bucket should also have a file-size limit of 5 MB (Dashboard → Storage → bucket settings) |
| Sign-in accounts 50,000 monthly active (Supabase) | Sign-in is refused above it | Upgrade before it; at pilot size you will not meet it |
| Emails 100/day, 3,000/month (Resend) | The app stops sending notification emails at 90/day and 2,800/month (in-app only), and holds invites and exports until the next day | Check who sends so much (`make usage-report`; `OutboundEmail` kinds in Django admin). Turn off a noisy email type's default in `apps/notifications/prefs.py` or upgrade Resend and set the four `EMAIL_*` numbers to 0 |
| Redis 500,000 commands/month, 256 MB (Upstash) | Redis refuses commands; the app reads Postgres, slower but correct | `REDIS_LEAN=true` should already be on (it is in the deploy files). Check the Upstash dashboard for the exact number; pay-as-you-go costs about $0.20 per 100,000 commands |
| AI calls (`LLM_DAILY_CALL_LIMIT`) | Onboarding uses the manual pickers for the rest of the day | Normal and safe. Raise the number if the day was a real sign-up spike, or set `LLM_PROVIDER=none` to run with no AI at all |
| Cloud Run / Cloud Logging free allowances | You are billed pennies | The budget alerts (50/80/100%) email you. Not measured by `usage-report`: look at Billing → Reports |
| Supabase egress 5 GB, Vercel bandwidth | Throttling or an upgrade prompt | Not measured by the app: look in each dashboard monthly |

After changing a limit or a plan, run `make usage-report ENV=production` again and note the date.

### Turn on branch protection (one line)
Settings → Branches → rule for `main` → Require status checks → **ci** (see step 7 of the one-time setup).

## Running the beta

### Approve a production deploy
Production never deploys by itself. Actions → **deploy production** → Run workflow; the run stops at the `production` environment and waits for you
(the required reviewer) to press **Review deployments → Approve**. Before you approve, check:
1. The commit is on `main` and the `ci` check is green (the run itself refuses otherwise).
2. The staging deploy of the same commit passed `make smoke` and you clicked through sign-in, Home and an apply on staging.
3. The pull request lists a migration? Read it: it must only add (new table, new nullable column, new index). A rename or a drop needs a two-step release.
4. Nothing is on fire: no open alert (Sentry, uptime), and it is not the middle of a payment or circuit round (circuits run Mondays; payments are off in the beta).
After approving, watch the run to its last lines (`OK: 0 failed`, `Done.`). If the live smoke test fails, traffic goes back by itself; then read "When a deploy fails".
Not sure? Do not approve. A deploy can wait; a bad one cannot be un-seen.

### Revoke an invite code
Django admin → Beta → **Invite codes** → tick the code → action **Revoke selected codes**. New sign-ins with that code get the same
`invalid_code` as a wrong code. People who already used it **stay in**; to remove one person, go to Beta → **Beta access**, tick them, **Revoke access**
(they are locked out at once and a revoked row stays so nothing re-grants it; **Restore access** undoes it). Everything here is audit-logged.
A code that leaked on a public page: revoke it, then create new ones: `make invite-codes N=10 USES=1 DAYS=30 NOTE="why"` (locally) or Add invite code in admin.

### Approve the waitlist
Django admin → Beta → **Waitlist entries** → filter `status = pending`, tick the people → **Approve and send the invite email** (a single-use code
is emailed, valid `INVITE_EXPIRY_DAYS_WAITLIST` = 30 days). **Reject** sends nothing. Approve in small batches (10–20) so the pilot stays
manageable; look at the funnel first (Django admin → Metrics, or `make funnel`) to see which sources actually finish onboarding.
Email limits apply (`make usage-report ENV=production`): at 100 a day on the free plan, approvals queue and go out the next day.

### Switch a feature flag
Django admin → Core → **Feature flags** → pick the flag → audience `off | testers | everyone` → save. It takes effect within 60 seconds. No deploy.
Rules the admin enforces: `promotions` and `payments` cannot be switched off while a paid campaign is active or an order is `created` (pause or refund first);
a flag cannot be on without the flag it depends on. Check the numbers in PRODUCTION.md §2b before switching anything on, and write the date and reason in
PROGRESS.md. After changing `investor_mode` or `partner_mode`, redeploy the landing site (see "Landing site" below). Testers: Members → tick `is_tester`.
Locally: `make flags` and `make flag NAME=circuits TO=testers`.

### Take down a post, a profile or a startup
1. **From a report** (the normal way): Django admin → Moderation → **Reports** → open the oldest unhandled one → tick it → choose an action:
   *hide* (post/reply stays in the database, members stop seeing it), *remove*, *warn the author* (in-app + email), *suspend* the author (or the startup's
   claimant; they are signed out at once), or *dismiss*. Each action marks the report handled and writes the audit log.
2. **Without a report** (a court or police notice, a legal complaint): find the item (Social → Posts, Members, Startups), then:
   - a post: set status to `hidden` or `removed`;
   - a member: tick them → **Suspend members** (reversible with **Reinstate members**);
   - a startup (crawled or user-made): set `hidden_at` to now. It disappears from the map, search and Pulse; the data stays.
3. Write down who asked, when, what you did and why (a line in the report's note or in PROGRESS.md). Answer the complainant within the time in the Terms.
4. Never delete rows by hand. Members' own deletion requests go through the deletion pipeline ("Data requests" below).
A startup owner who asks to be removed: use the takedown form's email, hide the startup, and tell them it is done.

### Run a load test on staging
Do this before a public launch and after any change to feeds, matching or the database. It sends real traffic: use staging, never production (the script refuses production).
1. Staging needs real sign-ins, because demo sign-in is off there by design. Create 10–20 test accounts in the staging app (use throwaway emails, invite codes,
   finish onboarding; one student, one founder, a few of each role). For each, sign in in a browser, open DevTools → Application → Local Storage → the Supabase
   `access_token`, and put one token per line in a file **outside the repository**, e.g. `~/staging-tokens.txt`. Tokens last 1 hour: run within it.
2. `make load-test URL=https://<staging API address> TOKENS=~/staging-tokens.txt USERS=50,200 SECONDS=120 JSON=~/load-staging.json`
3. Read the table: every row should say PASS (p95 under 300 ms for cached reads and 800 ms for the rest, no errors). `429` counts are the per-member limits working:
   with few tokens many users share a member, so 429s on apply and message are expected, not a failure.
4. For the full ~1,000-user run (PRODUCTION.md §9) use `USERS=1000` from a machine with a good network, with at least 20 tokens, and watch Cloud Run
   (instances, CPU, "too many connections") and Supabase (Reports → Database) while it runs. Write the date and numbers in PROGRESS.md.
5. Afterwards delete the test accounts' data (they are ordinary members: Settings → delete account) and delete the token file.

### Incident checklist
Something is wrong in production (alerts, a member's report, your own eyes). Work top to bottom; do not skip to the fix.
1. **Assess (5 minutes).** What is broken, for whom, since when? `make smoke URL=... ORIGIN=...`; `make logs ENV=production`; Sentry; the uptime alert. Write the start time down.
2. **Is it a recent deploy?** Yes → `make rollback ENV=production` first, ask questions afterwards.
3. **Contain.** Data exposed or being damaged? Switch the feature off in Django admin (flags, 60 seconds), suspend an abusive account, pause Cloud Scheduler
   triggers, or set `BETA_MODE` access closed (revoke the invite code). Stopping the leak comes before understanding it.
4. **Communicate.** Tell invited members if it lasts more than an hour (community channel / waitlist email). Say what you know, not what you guess.
5. **Personal data involved?** (someone saw another member's data, a key leaked, a backup was exposed.) Rotate the secret ("Rotate a secret"), note which
   members and which fields, and contact the Grievance Officer's lawyer the same day: the DPDP Act has a duty to tell the Data Protection Board and the people affected.
6. **Fix forward.** A pull request with a test that fails before the fix; deploy through the normal approval.
7. **Write it up** (within 2 days) in PROGRESS.md: timeline, cause, what you did, what changes so it cannot repeat (a test, an alert, a runbook line).

### Who to contact
Fill this in before launch and keep it current (the first row is the person on call).
| For | Who / where | Contact |
|---|---|---|
| Everything (on call) | `<YOUR NAME>` | `<PHONE, EMAIL>` |
| Backup person if you are unreachable | `<NAME>` | `<PHONE, EMAIL>` |
| Data requests, grievances (DPDP) | Grievance Officer | `GRIEVANCE_EMAIL` in the environment; `<LAWYER, PHONE>` |
| Database, sign-in, files (Supabase) | Dashboard → Support; status.supabase.com | `<ACCOUNT EMAIL, PROJECT ID>` |
| Servers, jobs, logs (Google Cloud) | Console → Support; status.cloud.google.com | `<PROJECT ID, BILLING CONTACT>` |
| App and landing hosting (Vercel) | vercel.com/support; vercel-status.com | `<TEAM NAME>` |
| Redis (Upstash) | upstash.com/support | `<ACCOUNT EMAIL>` |
| Email (Resend) | resend.com/support; resend-status.com | `<ACCOUNT EMAIL>` |
| Payments (Razorpay), once `payments` is on | dashboard → Support | `<MERCHANT ID>` |
| Errors (Sentry) | sentry.io | `<ORG NAME>` |
| Domain and DNS | `<REGISTRAR>` | `<ACCOUNT EMAIL>` |

### Manual checks (PRODUCTION.md §14), with the date each last passed
Everything else in §14 has an automated test in `make check`. These need a person, a phone or a real environment. Put the date and your initials when done.
| # | Check | How | Last passed |
|---|---|---|---|
| 3 | Migrations on production-sized data | Staging copy with ≥50k members and ≥500k events; time each migration | `<DATE>` |
| 4 | No "too many connections" under load | "Run a load test on staging" with 1,000 users; watch Supabase connections | `<DATE>` |
| 6 | Cold start time | `min_instances = 0`, wait 15 minutes, time the first `/api/config`. Write the number here: `<SECONDS>` | `<DATE>` |
| 19 | Email lands in the inbox | SPF/DKIM/DMARC verified at Resend; send to a Gmail and an Outlook address | `<DATE>` |
| 21 | Rollback and restore drills | "Rollback drill" and `make restore-drill` (setup steps 8 and 9) | `<DATE>` |
| 22 | A budget Android on throttled 4G | Sign in, Home, Discover, apply, Inbox; Lighthouse ≥ 90 | `<DATE>` |

## Retention

What is removed, when, and by what. The daily job is `retention_cleanup` (`make retention` runs it by hand; Cloud Scheduler runs it
once a day from Stage 5). It is idempotent and logs **counts only**.

| What | After | Done by |
|---|---|---|
| Accounts that signed in but never accepted the terms | 30 days (`UNVERIFIED_ACCOUNT_DAYS`) | `retention_cleanup`, through the same pipeline as "delete my account". Staff roles are never purged |
| Data export files | The download link lasts 24 hours (`EXPORT_LINK_HOURS`); the file is deleted when the link expires | `retention_cleanup` |
| Rejected waitlist entries | 90 days (`REJECTED_WAITLIST_DAYS`) | `retention_cleanup` |
| Sent and failed outgoing email records | 30 days (`EMAIL_KEEP_DAYS`) | `send_emails` |
| Product events | 365 days (`EVENT_RETENTION_DAYS`). Pseudonymous: ids and types only. The table refuses every delete except this job's | `retention_cleanup` |
| Notifications | Read ones after 90 days (`NOTIFICATION_READ_RETENTION_DAYS`), any after 180 (`NOTIFICATION_RETENTION_DAYS`) | `retention_cleanup` |
| Ranker snapshots (what the matcher showed) | 365 days (`RANKER_SNAPSHOT_RETENTION_DAYS`) | `retention_cleanup` |
| Payment webhook records | 90 days (`WEBHOOK_EVENT_RETENTION_DAYS`); skipped until payments exist | `retention_cleanup` |
| Database backups | 30 days | The bucket's lifecycle rule (`deploy/gcp/backup-lifecycle.json`), NOT code |
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
