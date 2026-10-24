"""Delete my account (DPDP right to erasure).

Two steps, so the person is out at once and the slow, failure-prone work happens in a job:

1. `request_deletion` (POST /api/me/deletion, after a typed confirmation): marks the account. From that moment every call with
   its token answers 403 `account_deleted`, so nothing more can happen while the job has not run.
2. `erase` (the `delete_accounts` job; also used by the retention job): removes the Supabase sign-in, the files, the profile and
   everything personal, and turns the member row into a "Deleted member" tombstone that old content points at.

What is kept, and why:
- Posts, replies and messages stay, now written by "Deleted member": other people's conversations and threads still make sense.
- Events stay: they are pseudonymous (ids and enums only).
- Orders, payments and invoices stay for FINANCIAL_RECORD_RETENTION_YEARS (tax law; the accountant confirms the period).
  Nothing deletes them: the tombstone row they point at is never removed. Payments arrive in Stage 4e.
- Consent records and reports stay (proof of consent; moderation history).
- The tombstone keeps its auth_user_id so a token that is still valid cannot create a brand-new account (see core/auth.py).

Order inside `erase`: Supabase user first, then files, then one database transaction. Each step is safe to repeat, so a failure
anywhere leaves a locked-out account that the next run finishes.
"""

import structlog
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import Connection, ConnectionRequest, DataExport, Member, Role, WorkEmailVerification
from apps.beta.models import BetaAccess, InviteCode, WaitlistEntry
from apps.circuits.models import Circuit
from apps.circuits.services import nudge
from apps.events.services import record
from apps.intros.models import IntroRequest
from apps.jobs.models import Application, Job
from apps.matching.models import MatchResult, MemberSkill, MemberTrait, Need, Offer
from apps.moderation.models import Block
from apps.notifications.models import Notification
from apps.notifications.services import notify_many
from apps.social.models import DailyDrop, Follow, MediaUpload, Reaction, UpdateView
from apps.startups.models import ClaimRequest, Startup, StartupInterest, StartupMember
from apps.startups.services import on_startup_unclaimed
from core import supabase_admin
from core.errors import Forbidden
from core.models import OutboundEmail
from core.storage import get_storage

log = structlog.get_logger("deletion")
DELETED_NAME = "Deleted member"


def request_deletion(member: Member) -> Member:
    """Lock the account and queue the erase. Safe to repeat."""
    if member.role == Role.SUPER_ADMIN:
        raise Forbidden("Circuit admins are removed by another admin")
    if member.deletion_requested_at is None:
        member.deletion_requested_at = timezone.now()
        member.save(update_fields=["deletion_requested_at", "updated_at"])
        record("account.deletion_requested", actor=member, target_type="member", target_id=member.pk)
    return member


# -- the job ---------------------------------------------------------------------------------------------
def _delete_files(member: Member) -> int:
    """Remove every stored file of this member: picture variants (and any leftover original) and export zips."""
    storage = get_storage()
    by_bucket: dict[str, list[str]] = {}
    for upload in MediaUpload.objects.filter(owner=member):
        bucket = settings.STORAGE_BUCKETS[upload.purpose]
        names = [f"w{w}.webp" for w in settings.MEDIA_VARIANT_WIDTHS] + ["original"]
        by_bucket.setdefault(bucket, []).extend(f"{upload.path}/{n}" for n in names)
    exports = [p for p in DataExport.objects.filter(member=member).values_list("path", flat=True) if p]
    if exports:
        by_bucket.setdefault(settings.STORAGE_BUCKETS["export"], []).extend(exports)
    for bucket, paths in by_bucket.items():
        storage.delete(bucket, paths)
    return sum(len(p) for p in by_bucket.values())


def _end_circuits(member: Member) -> None:
    for circuit in Circuit.objects.filter(
        status__in=[Circuit.Status.PROPOSED, Circuit.Status.ACTIVE], legs__giver=member
    ).distinct():
        circuit.status = Circuit.Status.DECLINED
        circuit.save(update_fields=["status"])
        nudge(circuit.pk)
        others = [g for g in circuit.legs.values_list("giver_id", flat=True) if g != member.pk]
        notify_many(others, "circuit.declined", circuit_id=circuit.pk)  # the same neutral notice as any "no"


def _hand_over_startups(member: Member) -> None:
    """A startup I claimed goes to another member of its team, or becomes unclaimed. Its data is never overwritten or deleted."""
    for startup in Startup.objects.filter(claimed_by=member):
        successor = (
            StartupMember.objects.filter(
                startup=startup, member__deletion_requested_at__isnull=True, member__suspended_at__isnull=True
            )
            .exclude(member=member)
            .order_by("id")
            .first()
        )
        if successor:
            startup.claimed_by_id = successor.member_id
            startup.save(update_fields=["claimed_by"])
        else:
            startup.claimed_by, startup.claimed_at = None, None
            startup.save(update_fields=["claimed_by", "claimed_at"])
            # nobody manages these roles any more: close the ones this member posted rather than leave them dangling
            Job.objects.filter(startup=startup, posted_by=member, is_open=True).update(is_open=False)
            if not Job.objects.filter(startup=startup, is_open=True).exists():
                Startup.objects.filter(pk=startup.pk).update(hiring=False)
        on_startup_unclaimed(startup, transferred_to=successor.member_id if successor else None)
    ClaimRequest.objects.filter(member=member, status=ClaimRequest.Status.PENDING).update(status=ClaimRequest.Status.EXPIRED)
    StartupMember.objects.filter(member=member).delete()


def _erase_rows(member: Member) -> None:
    _end_circuits(member)
    IntroRequest.objects.filter(
        Q(requester=member) | Q(target=member) | Q(via=member), status=IntroRequest.Status.PENDING
    ).update(status=IntroRequest.Status.EXPIRED, stage=IntroRequest.Stage.STOPPED)
    IntroRequest.objects.filter(requester=member).update(message="")
    _hand_over_startups(member)
    # personal data and everything that only exists because of this person
    Connection.objects.filter(Q(member_a=member) | Q(member_b=member)).delete()
    ConnectionRequest.objects.filter(Q(sender=member) | Q(recipient=member)).delete()
    for model in (Need, Offer, MemberSkill, MemberTrait, Reaction, Follow, StartupInterest, Notification, DailyDrop, UpdateView):
        model.objects.filter(**{"viewer" if model is UpdateView else "member": member}).delete()
    MatchResult.objects.filter(Q(member=member) | Q(candidate=member)).delete()
    Application.objects.filter(student=member).delete()
    Block.objects.filter(Q(blocker=member) | Q(blocked=member)).delete()
    WorkEmailVerification.objects.filter(member=member).delete()
    BetaAccess.objects.filter(member=member).delete()
    InviteCode.objects.filter(created_by=member, revoked_at__isnull=True).update(revoked_at=timezone.now())
    if member.email:
        WaitlistEntry.objects.filter(email__iexact=member.email).delete()
    MediaUpload.objects.filter(owner=member).delete()  # picture rows; posts keep their text, messages lose the image
    DataExport.objects.filter(member=member).delete()
    OutboundEmail.objects.filter(member=member).delete()  # queued and sent mail keeps their address and text: gone with them
    # the tombstone: old posts, replies and messages now read "Deleted member"
    member.display_name, member.email, member.bio = DELETED_NAME, "", ""
    member.location, member.city, member.college, member.organisation = None, "", "", None
    member.role, member.verification_level, member.open_intro_slots = Role.STUDENT, 1, 0
    member.circuits_opt_in = member.visible_to_org = member.is_tester = member.allow_requests = False
    member.profile_visibility = Member.Visibility.HIDDEN if member.is_minor else Member.Visibility.MEMBERS
    member.appearance, member.notification_prefs, member.pulse_seen_at = {}, {}, None
    member.deleted_at = timezone.now()
    member.save()


def erase(member: Member) -> str:
    """Finish one deletion. Returns "erased", or "already" if this member was done before. Raises if Supabase or storage fail."""
    member = Member.objects.get(pk=member.pk)
    if member.deleted_at is not None:
        return "already"
    supabase_admin.delete_auth_user(member.auth_user_id)  # raises AuthDeleteFailed: the account stays locked, the job retries
    files = _delete_files(member)
    with transaction.atomic():
        _erase_rows(member)
        record("account.deleted", target_type="member", target_id=member.pk)
    log.info("account_erased", member_id=member.pk, files=files)
    return "erased"


def erase_requested(limit: int = 20) -> dict[str, int]:
    """The `delete_accounts` job: finish every requested deletion. One failure does not stop the others."""
    counts = {"erased": 0, "failed": 0}
    pending = Member.objects.filter(deletion_requested_at__isnull=False, deleted_at__isnull=True).order_by(
        "deletion_requested_at"
    )
    for member in pending[:limit]:
        try:
            if erase(member) == "erased":
                counts["erased"] += 1
        except Exception as exc:  # leave the account locked; the next run tries again
            counts["failed"] += 1
            log.warning("account_erase_failed", member_id=member.pk, error=type(exc).__name__)
    return counts
