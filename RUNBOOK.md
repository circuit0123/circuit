# Circuit — runbook

What to do when something needs a human. Sections are added by the stage that builds the thing (LAUNCH.md Stage 11 completes this file:
deploy, rollback, restore, rotate secrets, outage, takedown). Commands are `make` targets (COMMANDS.md).

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
