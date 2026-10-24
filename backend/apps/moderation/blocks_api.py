"""Block endpoints: from a profile or a chat menu, plus the list in Settings so a block can be lifted."""

from ninja import Router, Schema, Status

from apps.moderation import blocks
from core.auth import current_member
from core.ratelimit import check_rate
from core.schemas import PersonOut, person

router = Router()


class BlockedOut(Schema):
    items: list[PersonOut]


@router.get(
    "/me/blocks",
    response=BlockedOut,
    summary="People I blocked",
    description="Only the people I blocked, newest first. Who blocked me is never shown.",
)
def my_blocks(request):
    return {"items": [person(m) for m in blocks.blocked_by(current_member(request))]}


@router.post(
    "/members/{member_id}/block",
    response={204: None},
    summary="Block a member",
    description="Works both ways: neither of you sees the other in matches, Daily Drop, Pulse, Live wire, intros, circuits or "
    "Inbox. Removes the connection, closes the chat, stops pending intros between you and ends shared circuits. "
    "Anyone you cannot see or have not been in contact with is a 404. Safe to repeat. Rate limited.",
)
def block_member(request, member_id: int):
    member = current_member(request)
    check_rate(member.pk, "block")
    blocks.block(member, member_id)
    return Status(204, None)


@router.delete(
    "/members/{member_id}/block",
    response={204: None},
    summary="Unblock a member",
    description="Lifts my block. A closed chat comes back as a request; the connection is not restored. 404 if I had not blocked them.",
)
def unblock_member(request, member_id: int):
    blocks.unblock(current_member(request), member_id)
    return Status(204, None)
