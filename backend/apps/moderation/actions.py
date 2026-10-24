"""What a moderator can do about a report. The Django admin calls `apply`; it does the work and writes the report's outcome.

    hide     post/reply: hidden · message: removed · startup: hidden from the map and roles · member: profile hidden
    remove   post/reply: removed · message: removed · startup: hidden (same as hide) · member: nothing (suspend instead)
    warn     tells the author (or the startup's claimant) in the app and by email
    suspend  locks the author (or the startup's claimant) out
    dismiss  no action needed

The admin writes the audit-log row (core/adminbase.audit); this module returns what changed so the row can say so.
Content is never deleted, so a decision can be reversed from Django admin.
"""

from django.conf import settings
from django.utils import timezone

from apps.accounts.models import Member, Role
from apps.events.services import record
from apps.messaging.models import Message
from apps.moderation.models import Report
from apps.notifications.services import notify
from apps.social.models import Post, Reply
from apps.startups.models import Startup
from core import email as outbox

ACTIONS = {a.value for a in Report.Action}


def _subject_member_id(report: Report) -> int | None:
    """The person a warning or suspension is about: the author, the sender, the member, the startup's claimant."""
    t, i = report.target_type, report.target_id
    if t == "post":
        return Post.objects.filter(pk=i).values_list("author_id", flat=True).first()
    if t == "reply":
        return Reply.objects.filter(pk=i).values_list("author_id", flat=True).first()
    if t == "message":
        return Message.objects.filter(pk=i).values_list("sender_id", flat=True).first()
    if t == "startup":
        return Startup.objects.filter(pk=i).values_list("claimed_by_id", flat=True).first()
    return i


def _hide(report: Report, remove: bool) -> bool:
    t, i = report.target_type, report.target_id
    if t in ("post", "reply"):
        model = Post if t == "post" else Reply
        status = Post.Status.REMOVED if remove else Post.Status.HIDDEN
        return bool(model.objects.filter(pk=i).exclude(status=status).update(status=status))
    if t == "message":
        return bool(Message.objects.filter(pk=i, removed_at__isnull=True).update(removed_at=timezone.now()))
    if t == "startup":
        return bool(Startup.objects.filter(pk=i, hidden_at__isnull=True).update(hidden_at=timezone.now()))
    if t == "member" and not remove:
        return bool(Member.objects.filter(pk=i).exclude(profile_visibility=Member.Visibility.HIDDEN).update(
            profile_visibility=Member.Visibility.HIDDEN
        ))  # fmt: skip
    return False


def _subject(report: Report, **filters) -> Member | None:
    subject_id = _subject_member_id(report)
    return Member.objects.filter(pk=subject_id, **filters).first() if subject_id is not None else None


def _warn(report: Report) -> bool:
    member = _subject(report, deleted_at__isnull=True)
    if member is None:
        return False
    notify(member, "moderation.warning", report_id=report.pk)
    if member.email:  # a safety notice is not a marketing type: it ignores email preferences, and has no unsubscribe link
        outbox.queue_email(
            member.email,
            "moderation.warning",
            "A message from the Circuit moderators",
            "A moderator reviewed something you shared on Circuit and asked you to follow the community guidelines.\n\n"
            f"Read them here: {settings.APP_URL.rstrip('/')}/help/community-guidelines\n"
            f"If you think this is a mistake, write to {settings.SUPPORT_EMAIL}.\n",
            member=member,
        )
    return True


def _suspend(report: Report) -> bool:
    member = _subject(report)
    if member is None or member.role == Role.SUPER_ADMIN or member.suspended_at is not None:
        return False
    member.suspended_at = timezone.now()
    member.visible_to_org = False
    member.save(update_fields=["suspended_at", "visible_to_org", "updated_at"])
    return True


def apply(report: Report, action: str, staff_user) -> dict:
    """Do `action` for `report`, close the report and return {"action", "changed"} for the audit log."""
    if action not in ACTIONS:
        raise ValueError(f"Unknown moderation action {action!r}")
    if action == Report.Action.DISMISS:
        changed = False
    elif action == Report.Action.HIDE:
        changed = _hide(report, remove=False)
    elif action == Report.Action.REMOVE:
        changed = _hide(report, remove=True)
    elif action == Report.Action.WARN:
        changed = _warn(report)
    else:
        changed = _suspend(report)
    report.action = action
    report.status = Report.Status.DISMISSED if action == Report.Action.DISMISS else Report.Status.ACTIONED
    report.handled_by, report.handled_at = staff_user, timezone.now()
    report.save(update_fields=["action", "status", "handled_by", "handled_at"])
    record("report.actioned", target_type=report.target_type, target_id=report.target_id, report_id=report.pk, action=action)
    return {"action": action, "changed": changed, "target_type": report.target_type, "target_id": report.target_id}
