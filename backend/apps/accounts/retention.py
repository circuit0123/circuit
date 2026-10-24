"""Retention cleanup (PRODUCTION.md §5): the daily job that removes what we no longer need to keep.

- Unverified accounts: signed in more than UNVERIFIED_ACCOUNT_DAYS ago and never accepted the terms (they never got past the
  Welcome screen). Removed through the same deletion pipeline as "delete my account". Staff roles are never purged.
- Export files whose link has expired (the zip is deleted from the private bucket; the row stays as a record).
- Rejected waitlist entries older than REJECTED_WAITLIST_DAYS.

Request-log retention (30 days) is NOT done here: it is a Cloud Logging setting (RUNBOOK.md "Retention").
Idempotent, and it logs counts only: no names, emails or ids.
"""

from datetime import timedelta

import structlog
from django.conf import settings
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.accounts import deletion, export
from apps.accounts.models import Consent, Member, Role
from apps.beta.models import WaitlistEntry
from apps.events.services import record

log = structlog.get_logger("retention")
STAFF = (Role.SUPER_ADMIN, Role.PARTNER_ADMIN)


def purge_unverified(now=None) -> int:
    cutoff = (now or timezone.now()) - timedelta(days=settings.UNVERIFIED_ACCOUNT_DAYS)
    stale = (
        Member.objects.filter(created_at__lt=cutoff, deleted_at__isnull=True)
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


def run() -> dict[str, int]:
    counts = {
        "unverified_accounts": purge_unverified(),
        "export_files": export.expire_old(),
        "waitlist_entries": purge_waitlist(),
    }
    log.info("retention_cleanup", **counts)
    record("retention.cleaned", counts=counts)
    return counts
