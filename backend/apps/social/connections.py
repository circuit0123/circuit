"""Connections (F17): ask with a note, the other person accepts, and the pair becomes a Connection (feeds warm paths).

Under-18s: a request to or from a minor must stay inside one organisation (relations.may_request_connection).
Anyone not allowed to be reached is a 404, the same as someone who does not exist.
"""

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import Connection, ConnectionRequest, Member
from apps.events.services import record
from apps.social import services
from apps.social.relations import blocked_ids, connected_ids, is_connected, may_request_connection
from apps.social.schemas import author
from core.errors import ApiError, Conflict, NotFound
from core.ratelimit import check_rate

S = ConnectionRequest.Status
REASK_AFTER = timedelta(days=30)  # after a decline, the sender cannot ask again for this long


def list_connections(member: Member) -> list[dict]:
    services.require_social(member)
    ids = connected_ids(member.pk) - blocked_ids(member.pk)
    people = Member.objects.filter(pk__in=ids, suspended_at__isnull=True).order_by("display_name", "pk")
    return [author(p) for p in people]


def remove_connection(member: Member, other_id: int) -> None:
    services.require_social(member)
    x, y = sorted((member.pk, other_id))
    deleted, _ = Connection.objects.filter(member_a_id=x, member_b_id=y).delete()
    if not deleted:
        raise NotFound()
    record("connection.removed", actor=member, target_type="member", target_id=other_id)


def _connect(a_id: int, b_id: int) -> None:
    x, y = sorted((a_id, b_id))
    Connection.objects.get_or_create(member_a_id=x, member_b_id=y, defaults={"strength": 0.5, "source": "request"})


def send_request(member: Member, recipient_id: int, note: str) -> ConnectionRequest:
    services.require_social(member)
    if recipient_id == member.pk:
        raise ApiError(422, "self_request", "You cannot connect with yourself")
    recipient = Member.objects.filter(pk=recipient_id).first()
    if recipient is None or not may_request_connection(member, recipient):
        raise NotFound()
    if is_connected(member.pk, recipient.pk):
        raise Conflict("You are already connected", "already_connected")
    mine = ConnectionRequest.objects.filter(sender=member, recipient=recipient)
    if mine.filter(status=S.PENDING).exists():
        raise Conflict("You already asked this person", "already_requested")
    if mine.filter(status=S.DECLINED, responded_at__gte=timezone.now() - REASK_AFTER).exists():
        raise Conflict("This request was declined recently", "recently_declined")
    check_rate(member.pk, "connection_request")
    with transaction.atomic():
        reverse = (
            ConnectionRequest.objects.select_for_update().filter(sender=recipient, recipient=member, status=S.PENDING).first()
        )
        if reverse is not None:  # they already asked me: asking back is a yes
            _answer(reverse, accept=True)
            return reverse
        try:
            req = ConnectionRequest.objects.create(sender=member, recipient=recipient, note=note.strip())
        except IntegrityError:
            raise Conflict("You already asked this person", "already_requested") from None
        record("connection.requested", actor=member, target_type="member", target_id=recipient.pk)
    return req


def _answer(req: ConnectionRequest, accept: bool) -> None:
    req.status = S.ACCEPTED if accept else S.DECLINED
    req.responded_at = timezone.now()
    req.save(update_fields=["status", "responded_at"])
    if accept:
        _connect(req.sender_id, req.recipient_id)
    record("connection.responded", actor=req.recipient_id, target_type="member", target_id=req.sender_id, accepted=accept)


def respond(member: Member, request_id: int, accept: bool) -> ConnectionRequest:
    services.require_social(member)
    with transaction.atomic():
        req = (
            ConnectionRequest.objects.select_for_update().select_related("sender").filter(pk=request_id, recipient=member).first()
        )
        if req is None or req.sender.suspended_at or req.sender_id in blocked_ids(member.pk):
            raise NotFound()
        if req.status != S.PENDING:
            raise Conflict("This request was already answered", "already_answered")
        _answer(req, accept)
    return req


def list_requests(member: Member, box: str) -> list[ConnectionRequest]:
    services.require_social(member)
    hidden = blocked_ids(member.pk)
    if box == "incoming":
        qs = ConnectionRequest.objects.filter(recipient=member, sender__suspended_at__isnull=True).exclude(sender_id__in=hidden)
    else:
        qs = ConnectionRequest.objects.filter(sender=member, recipient__suspended_at__isnull=True).exclude(
            recipient_id__in=hidden
        )
    return list(qs.filter(status=S.PENDING).select_related("sender", "recipient").order_by("-created_at", "-id")[:100])
