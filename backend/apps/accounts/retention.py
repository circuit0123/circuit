"""Retention cleanup (PRODUCTION.md §5): the daily job that removes what we no longer need to keep.

- Unverified accounts: signed in more than UNVERIFIED_ACCOUNT_DAYS ago and never accepted the terms (they never got past the
  Welcome screen). Removed through the same deletion pipeline as "delete my account". Staff roles are never purged.
- Export files whose link has expired (the zip is deleted from the private bucket; the row stays as a record).
- Rejected waitlist entries older than REJECTED_WAITLIST_DAYS.
- Ranker snapshots (what the matcher showed and saw) older than RANKER_SNAPSHOT_RETENTION_DAYS.
- Free-tier housekeeping (the database is limited to 500 MB, PRODUCTION.md §11): product events older than EVENT_RETENTION_DAYS,
  notifications (read ones after NOTIFICATION_READ_RETENTION_DAYS, any after NOTIFICATION_RETENTION_DAYS) and payment webhook
  records older than WEBHOOK_EVENT_RETENTION_DAYS. Orders, payments and invoices are never touched here (financial records).

Request-log retention (30 days) is NOT done here: it is a Cloud Logging setting (RUNBOOK.md "Retention").
Idempotent, and it logs counts only: no names, emails or ids.
"""

from datetime import timedelta

import structlog
from django.apps import apps
from django.conf import settings
from django.db import connection, transaction
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.accounts import deletion, export
from apps.accounts.models import Consent, Member, Role
from apps.beta.models import WaitlistEntry
from apps.events.services import record
from apps.matching.models import FeatureSnapshot
from apps.notifications.models import Notification

log = structlog.get_logger("retention")
STAFF = (Role.SUPER_ADMIN, Role.PARTNER_ADMIN)
BATCH = 5000  # rows per DELETE: keeps each statement short and the locks brief on a small database


def purge_unverified(now=None) -> int:
    cutoff = (now or timezone.now()) - timedelta(days=settings.UNVERIFIED_ACCOUNT_DAYS)
    stale = (
        Member.objects.filter(
            created_at__lt=cutoff, deleted_at__isnull=True, is_simulated=False
        )  # simulated members never consent
        .exclude(role__in=STAFF)
        .exclude(pk__in=Consent.objects.values("member_id"))
        .order_by("pk")
    )
    count = 0
    for member in stale:
        try:
            deletion.request_deletion(member)
            if deletion.erase(member) == "erased":
                count += 1
        except Exception as exc:  # one stubborn account must not stop the rest; the next run tries again
            log.warning("retention_unverified_failed", error=type(exc).__name__)
    return count


def purge_waitlist(now=None) -> int:
    cutoff = (now or timezone.now()) - timedelta(days=settings.REJECTED_WAITLIST_DAYS)
    qs = WaitlistEntry.objects.filter(status=WaitlistEntry.Status.REJECTED).annotate(since=Coalesce("reviewed_at", "created_at"))
    deleted, _ = qs.filter(since__lt=cutoff).delete()
    return deleted


def purge_snapshots(now=None) -> int:
    cutoff = (now or timezone.now()) - timedelta(days=settings.RANKER_SNAPSHOT_RETENTION_DAYS)
    deleted, _ = FeatureSnapshot.objects.filter(shown_at__lt=cutoff, viewer__is_simulated=False).delete()
    return deleted


def _delete_in_batches(queryset) -> int:
    total = 0
    model = queryset.model
    while True:
        pks = list(queryset.order_by("pk").values_list("pk", flat=True)[:BATCH])
        if not pks:
            return total
        total += model.objects.filter(pk__in=pks).delete()[0]


def purge_events(now=None) -> int:
    """Old product events. The table refuses DELETE (apps/events/migrations/0002), except in a transaction that says it is the
    retention job: `set_config(..., true)` lasts for that transaction only, so it also works through Supabase's transaction pooler."""
    cutoff = (now or timezone.now()) - timedelta(days=settings.EVENT_RETENTION_DAYS)
    total = 0
    while True:
        with transaction.atomic(), connection.cursor() as cur:
            cur.execute("SELECT set_config('circuit.purge_events', 'on', true)")
            cur.execute(
                "DELETE FROM events_event WHERE id IN (SELECT id FROM events_event WHERE created_at < %s ORDER BY id LIMIT %s)",
                [cutoff, BATCH],
            )
            deleted = cur.rowcount
        total += deleted
        if deleted < BATCH:
            return total


def purge_notifications(now=None) -> int:
    now = now or timezone.now()
    read = Notification.objects.filter(
        read_at__isnull=False, created_at__lt=now - timedelta(days=settings.NOTIFICATION_READ_RETENTION_DAYS)
    )
    old = Notification.objects.filter(created_at__lt=now - timedelta(days=settings.NOTIFICATION_RETENTION_DAYS))
    return _delete_in_batches(read) + _delete_in_batches(old)


def purge_webhook_events(now=None) -> int:
    """Payment webhook records (CLAUDE.md data model: webhook_events). Skipped while the payments app is not built (B3c)."""
    app_label, model_name = (
        "payments",
        "WebhookEvent",
    )  # variables, so the type checker does not look for an app that is not built yet
    try:
        model = apps.get_model(app_label, model_name)
    except LookupError:
        return 0
    cutoff = (now or timezone.now()) - timedelta(days=settings.WEBHOOK_EVENT_RETENTION_DAYS)
    return _delete_in_batches(model.objects.filter(received_at__lt=cutoff))


def run() -> dict[str, int]:
    counts = {
        "unverified_accounts": purge_unverified(),
        "export_files": export.expire_old(),
        "waitlist_entries": purge_waitlist(),
        "ranker_snapshots": purge_snapshots(),
        "events": purge_events(),
        "notifications": purge_notifications(),
        "webhook_events": purge_webhook_events(),
    }
    log.info("retention_cleanup", **counts)
    record("retention.cleaned", counts=counts)
    return counts
