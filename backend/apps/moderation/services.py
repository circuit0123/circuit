"""Reports (F12/F15): a member flags a post, reply, message or profile for the moderators in Django admin.

You can only report what you are allowed to see; anything else is a 404. Reporting twice is safe (one open report).
"""

from apps.accounts.models import ConnectionRequest, Member
from apps.accounts.services import visible_member
from apps.events.services import record
from apps.messaging.models import Conversation, Message
from apps.moderation.models import Report
from apps.social.models import Post, Reply
from apps.social.relations import can_see_post, is_connected
from core.errors import ApiError, Forbidden, NotFound
from core.ratelimit import check_rate

TARGET_TYPES = ("post", "reply", "message", "member")


def _can_report(reporter: Member, target_type: str, target_id: int) -> bool:
    if target_type == "post":
        post = Post.objects.select_related("author").filter(pk=target_id).first()
        return post is not None and post.author_id != reporter.pk and can_see_post(reporter, post)
    if target_type == "reply":
        reply = Reply.objects.select_related("post__author").filter(pk=target_id).first()
        return reply is not None and reply.author_id != reporter.pk and can_see_post(reporter, reply.post)
    if target_type == "message":
        msg = Message.objects.select_related("conversation").filter(pk=target_id).first()
        c = msg.conversation if msg else None
        return bool(c and reporter.pk in (c.member_a_id, c.member_b_id) and msg and msg.sender_id != reporter.pk)
    if target_id == reporter.pk:
        return False
    try:
        visible_member(reporter, target_id)
        return True
    except NotFound:
        pass
    # People who reached me without a visible profile (a message, a connection request, a connection) can be reported too.
    x, y = sorted((reporter.pk, target_id))
    return (
        Conversation.objects.filter(member_a_id=x, member_b_id=y).exists()
        or ConnectionRequest.objects.filter(sender_id=target_id, recipient=reporter).exists()
        or is_connected(reporter.pk, target_id)
    )


def create_report(reporter: Member, target_type: str, target_id: int, reason: str) -> Report:
    if reporter.role in ("super_admin",):
        raise Forbidden()
    if target_type not in TARGET_TYPES:
        raise ApiError(422, "bad_target", f"target_type must be one of {', '.join(TARGET_TYPES)}")
    reason = reason.strip()
    if not reason:
        raise ApiError(422, "empty_reason", "Tell us what is wrong")
    if not _can_report(reporter, target_type, target_id):
        raise NotFound()
    existing = Report.objects.filter(
        reporter=reporter, target_type=target_type, target_id=target_id, status=Report.Status.OPEN
    ).first()
    if existing:
        return existing
    check_rate(reporter.pk, "report")
    report = Report.objects.create(reporter=reporter, target_type=target_type, target_id=target_id, reason=reason)
    record("report.created", actor=reporter, target_type=target_type, target_id=target_id)
    return report
