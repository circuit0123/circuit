"""In-app notifications. Payloads hold ids and enums only (no names or emails): the app looks details up itself."""

from django.utils import timezone

from apps.accounts.models import Member
from apps.events.services import record
from apps.notifications.models import Notification
from core.errors import NotFound


def notify(member: Member | int, kind: str, **payload) -> Notification:
    return Notification.objects.create(member_id=getattr(member, "pk", member), kind=kind, payload=payload)


def notify_many(members, kind: str, **payload) -> None:
    ids = {getattr(m, "pk", m) for m in members}
    Notification.objects.bulk_create([Notification(member_id=i, kind=kind, payload=payload) for i in sorted(ids)])


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
    updated = Notification.objects.filter(member=member, read_at__isnull=True).update(read_at=timezone.now())
    if updated:
        record("notification.read_all", actor=member, count=updated)
    return updated
