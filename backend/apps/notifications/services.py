"""Notifications: the one place that decides whether, where and when a member hears about something.

    notify(member, "intro.received", actor=requester, intro_id=7)

Nothing is sent when the recipient is suspended or deleted, when the actor and the recipient have blocked each other, when the
kind belongs to a feature that is off for the recipient, or when the recipient turned that type off for that channel. Otherwise:

- in-app: a row, then a Realtime nudge to the channel `member:<id>` ({notification_id} only; the app fetches the rest);
- email: a row in the email outbox with unsubscribe headers. Under-18 members get no email outside 09:00-19:00 IST: it waits
  for 09:00. A failing email provider never fails the caller (the outbox retries; see core/email.py).

Payloads hold ids and enums only (no names or emails): the app and the email copy look details up themselves.
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import structlog
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import Member
from apps.events.services import record
from apps.notifications import copy, prefs, unsubscribe
from apps.notifications.models import Notification
from apps.social.relations import is_blocked
from core import email as outbox
from core import flags, realtime
from core.errors import NotFound

log = structlog.get_logger("notifications")

# A notification kind belongs to a feature flag by its prefix; when the flag is off for me it is left out.
KIND_FLAGS = {"circuit.": "circuits", "post.": "pulse"}


def visible(member: Member):
    """My notifications, minus those of features switched off for me and those from people I have blocked (or who blocked me).
    Nothing is deleted."""
    from apps.social.relations import blocked_ids

    qs = Notification.objects.filter(member=member)
    for prefix, flag in KIND_FLAGS.items():
        if not flags.enabled(flag, member):
            qs = qs.exclude(kind__startswith=prefix)
    blocked = blocked_ids(member.pk)
    if blocked:
        # has_key matters: without it NULL semantics would also drop every notification that has no actor (circuits, status updates)
        qs = qs.exclude(Q(payload__has_key="actor_id") & Q(payload__actor_id__in=blocked))
    return qs


# -- sending ---------------------------------------------------------------------------------------
def _reachable(recipient: Member) -> bool:
    return recipient.suspended_at is None and recipient.deletion_requested_at is None and recipient.deleted_at is None


def _flag_on(kind: str, recipient: Member) -> bool:
    return all(flags.enabled(flag, recipient) for prefix, flag in KIND_FLAGS.items() if kind.startswith(prefix))


def email_send_time(recipient: Member, now: datetime | None = None) -> datetime:
    """When an email to this member may go out: now, except under-18s only get email between 09:00 and 19:00 IST."""
    now = now or timezone.now()
    if not recipient.is_minor:
        return now
    tz = ZoneInfo(settings.NOTIFICATION_TZ)
    start, end = settings.QUIET_HOURS_IST
    local = now.astimezone(tz)
    if start <= local.hour < end:
        return now
    day = local.date() if local.hour < start else local.date() + timedelta(days=1)
    return datetime.combine(day, time(start), tzinfo=tz)


def _queue_email(recipient: Member, kind: str, actor: Member | None) -> bool:
    if not recipient.email:
        return False
    who = actor.display_name if actor and not actor.is_minor and actor.deleted_at is None and actor.display_name else None
    parts = copy.email_parts(kind, who)
    if parts is None:
        return False
    subject, line, path = parts
    type_ = prefs.type_for(kind)
    if type_ is None:
        return False
    token = unsubscribe.make_token(recipient.pk, type_)
    body = (
        f"{line}\n\nOpen it in Circuit: {settings.APP_URL.rstrip('/')}{path}\n\n"
        f"You get this email because it is switched on for {copy.TYPE_LABELS[type_]}.\n"
        f"Stop these emails: {unsubscribe.page_url(token)}\n"
        f"Change what you get: {settings.APP_URL.rstrip('/')}/settings/notifications\n"
    )
    outbox.queue_email(
        recipient.email,
        f"notification.{type_}",
        subject,
        body,
        headers=unsubscribe.headers_for(token),
        member=recipient,
        send_at=email_send_time(recipient),
    )
    return True


def _send(recipient: Member, kind: str, actor: Member | None, payload: dict) -> Notification | None:
    if not _reachable(recipient) or not _flag_on(kind, recipient):
        return None
    if actor is not None and (actor.pk == recipient.pk or is_blocked(actor.pk, recipient.pk)):
        return None  # nobody is told about their own actions, or about someone they blocked
    row = None
    if prefs.wants(recipient, kind, "in_app"):
        data = dict(payload)
        if actor is not None:
            data["actor_id"] = actor.pk
        row = Notification.objects.create(member=recipient, kind=kind, payload=data)
        transaction.on_commit(lambda: realtime.send(f"member:{recipient.pk}", "notification", {"notification_id": row.pk}))
    if prefs.wants(recipient, kind, "email"):
        try:
            _queue_email(recipient, kind, actor)
        except Exception as exc:  # an email problem must never fail the action that caused the notification
            log.warning("notification_email_not_queued", kind=kind, error=type(exc).__name__)
    return row


def notify(member: Member | int, kind: str, *, actor: Member | int | None = None, **payload) -> Notification | None:
    """Tell one member. Returns the in-app row, or None when nothing was written (see the module docstring)."""
    sent = _send_many([member], kind, actor, payload)
    return sent[0] if sent else None


def notify_many(members, kind: str, *, actor: Member | int | None = None, **payload) -> int:
    """Tell several members the same thing. Returns how many in-app notifications were written."""
    return len(_send_many(members, kind, actor, payload))


def _send_many(members, kind: str, actor, payload: dict) -> list[Notification]:
    ids = sorted({getattr(m, "pk", m) for m in members})
    recipients = {m.pk: m for m in Member.objects.filter(pk__in=ids)}
    actor_member = actor if isinstance(actor, Member) or actor is None else Member.objects.filter(pk=actor).first()
    sent = [_send(recipients[i], kind, actor_member, payload) for i in ids if i in recipients]
    return [n for n in sent if n is not None]


# -- reading ---------------------------------------------------------------------------------------
def mark_read(member: Member, notification_id: int) -> Notification:
    """Someone else's notification is a 404, same as one that does not exist."""
    n = Notification.objects.filter(pk=notification_id, member=member).first()
    if n is None:
        raise NotFound()
    if n.read_at is None:
        n.read_at = timezone.now()
        n.save(update_fields=["read_at"])
        record("notification.read", actor=member, target_type="notification", target_id=n.pk)
    return n


def mark_all_read(member: Member) -> int:
    updated = visible(member).filter(read_at__isnull=True).update(read_at=timezone.now())
    if updated:
        record("notification.read_all", actor=member, count=updated)
    return updated
