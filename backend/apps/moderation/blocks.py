"""Blocking a member (Stage 6). One service, used by the profile menu and by the chat menu.

A block works both ways: neither person sees the other in matches, Daily Drop, Pulse, Live wire, intros, circuits or Inbox
(the read paths all go through social.relations.blocked_ids). Blocking also cleans up what already exists between the two:
the connection and any connection requests are removed, the chat is closed, pending intros that involve both stop, and
proposed or active circuits that contain both end. Nobody is told who blocked them.
"""

from django.db import transaction
from django.db.models import Q

from apps.accounts.models import Connection, ConnectionRequest, Member
from apps.circuits.models import Circuit
from apps.circuits.services import nudge
from apps.events.services import record
from apps.intros.models import IntroRequest
from apps.messaging.models import Conversation
from apps.moderation.models import Block
from apps.moderation.services import can_contact_or_see
from apps.notifications.services import notify_many
from core.errors import ApiError, NotFound


def _pair(a_id: int, b_id: int) -> tuple[int, int]:
    x, y = sorted((a_id, b_id))
    return x, y


def _end_intros(a_id: int, b_id: int) -> int:
    a, b = a_id, b_id
    both = (
        Q(requester_id=a, target_id=b)
        | Q(requester_id=b, target_id=a)
        | Q(via_id=a, requester_id=b)
        | Q(via_id=a, target_id=b)
        | Q(via_id=b, requester_id=a)
        | Q(via_id=b, target_id=a)
    )
    return IntroRequest.objects.filter(both, status=IntroRequest.Status.PENDING).update(
        status=IntroRequest.Status.EXPIRED, stage=IntroRequest.Stage.STOPPED
    )


def _end_circuits(blocker: Member, other_id: int) -> int:
    """Proposed and active circuits with both people end as declined. Everyone else is told, in the same neutral words as any decline."""
    circuits = list(
        Circuit.objects.filter(status__in=[Circuit.Status.PROPOSED, Circuit.Status.ACTIVE])
        .filter(legs__giver_id=blocker.pk)
        .filter(legs__giver_id=other_id)
        .distinct()
    )
    for circuit in circuits:
        circuit.status = Circuit.Status.DECLINED
        circuit.save(update_fields=["status"])
        nudge(circuit.pk)
        others = [g for g in circuit.legs.values_list("giver_id", flat=True) if g != blocker.pk]
        notify_many(others, "circuit.declined", circuit_id=circuit.pk)  # no actor: a block looks like any other "no"
    return len(circuits)


@transaction.atomic
def block(member: Member, other_id: int) -> Block:
    """Block someone you can see or have been in contact with (anyone else is a 404, so ids cannot be probed). Safe to repeat."""
    if other_id == member.pk:
        raise ApiError(422, "self_block", "You cannot block yourself")
    other = Member.objects.filter(pk=other_id, deleted_at__isnull=True).first()
    already = Block.objects.filter(blocker=member, blocked_id=other_id).first()
    if already:
        return already
    if other is None or not can_contact_or_see(member, other.pk):
        raise NotFound()
    row = Block.objects.create(blocker=member, blocked=other)
    x, y = _pair(member.pk, other.pk)
    Connection.objects.filter(member_a_id=x, member_b_id=y).delete()
    ConnectionRequest.objects.filter(
        Q(sender=member, recipient=other) | Q(sender=other, recipient=member), status=ConnectionRequest.Status.PENDING
    ).delete()
    Conversation.objects.filter(member_a_id=x, member_b_id=y).exclude(status=Conversation.Status.BLOCKED).update(
        status=Conversation.Status.BLOCKED
    )
    intros = _end_intros(member.pk, other.pk)
    circuits = _end_circuits(member, other.pk)
    record("member.blocked", actor=member, target_type="member", target_id=other.pk, intros_ended=intros, circuits_ended=circuits)
    return row


@transaction.atomic
def unblock(member: Member, other_id: int) -> None:
    """Lift my block. Their chat comes back as a request (the connection is gone), unless they also blocked me."""
    deleted, _ = Block.objects.filter(blocker=member, blocked_id=other_id).delete()
    if not deleted:
        raise NotFound()
    if not Block.objects.filter(blocker_id=other_id, blocked=member).exists():
        x, y = _pair(member.pk, other_id)
        Conversation.objects.filter(member_a_id=x, member_b_id=y, status=Conversation.Status.BLOCKED).update(
            status=Conversation.Status.REQUEST
        )
    record("member.unblocked", actor=member, target_type="member", target_id=other_id)


def blocked_by(member: Member) -> list[Member]:
    """The people I blocked, newest first (never the people who blocked me: that stays private)."""
    rows = Block.objects.filter(blocker=member).select_related("blocked").order_by("-created_at", "-id")
    return [b.blocked for b in rows]
