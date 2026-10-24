"""1-to-1 messages (F17). The server decides who may talk to whom; Realtime only nudges the other side.

Rules: connected people chat directly. Otherwise the first message makes a `request` the other person must accept
(replying also accepts); the sender gets one message until then. Under-18s can only talk to their connections and
to staff of their own organisation (relations.may_message), checked on every send, not just at the start.
A conversation you are not in is a 404, like one that does not exist.
"""

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.accounts.models import Member
from apps.events.services import record
from apps.messaging import realtime
from apps.messaging.models import Conversation, Message
from apps.notifications.models import Notification
from apps.notifications.services import notify
from apps.social import media
from apps.social.models import MediaUpload
from apps.social.relations import MESSAGING_ROLES, blocked_ids, is_connected, may_message
from apps.social.schemas import author
from core.errors import ApiError, Conflict, Forbidden, NotFound
from core.ratelimit import check_rate

C = Conversation.Status


def require_messaging(member: Member) -> None:
    if member.role not in MESSAGING_ROLES:
        raise Forbidden()


def _other(conv: Conversation, member: Member) -> Member:
    return conv.member_b if conv.member_a_id == member.pk else conv.member_a


def get_conversation(member: Member, conversation_id: int) -> Conversation:
    require_messaging(member)
    conv = (
        Conversation.objects.select_related("member_a", "member_b")
        .filter(Q(member_a=member) | Q(member_b=member), pk=conversation_id)
        .exclude(status=C.BLOCKED)
        .first()
    )
    if conv is None:
        raise NotFound()
    return conv


def _message_out(msg: Message, me: Member, image_urls: dict | None = None) -> dict:
    gone = msg.removed_at is not None
    return {
        "id": msg.pk, "conversation_id": msg.conversation_id, "mine": msg.sender_id == me.pk,
        "body": "" if gone else msg.body, "image": None if gone or msg.image_id is None else (image_urls or {}).get(msg.image_id),
        "removed": gone, "created_at": msg.created_at,
    }  # fmt: skip


def _urls(messages) -> dict:
    return media.urls_for(m.image for m in messages if m.image_id and m.removed_at is None)


def conversation_rows(member: Member, convs: list[Conversation]) -> list[dict]:
    ids = [c.pk for c in convs]
    unread = dict(
        Message.objects.filter(conversation_id__in=ids, read_at__isnull=True, removed_at__isnull=True)
        .exclude(sender=member)
        .values_list("conversation_id")
        .annotate(n=Count("id"))
    )
    last = {}
    for m in (
        Message.objects.filter(conversation_id__in=ids)
        .select_related("image")
        .order_by("conversation_id", "-id")
        .distinct("conversation_id")
    ):
        last[m.conversation_id] = m
    rows = []
    for c in convs:
        lm = last.get(c.pk)
        rows.append(
            {
                "id": c.pk, "status": c.status, "other": author(_other(c, member)), "started_by_me": c.started_by_id == member.pk,
                "last_message_at": c.last_message_at, "unread": unread.get(c.pk, 0),
                "last_message": _message_out(lm, member) if lm else None,
            }
        )  # fmt: skip
    return rows


def list_conversations(member: Member, folder: str) -> list[dict]:
    require_messaging(member)
    status = C.ACTIVE if folder == "chats" else C.REQUEST
    convs = list(
        Conversation.objects.select_related("member_a", "member_b")
        .filter(Q(member_a=member) | Q(member_b=member), status=status)
        .exclude(member_a__suspended_at__isnull=False)
        .exclude(member_b__suspended_at__isnull=False)
        .exclude(member_a_id__in=blocked_ids(member.pk))
        .exclude(member_b_id__in=blocked_ids(member.pk))
        .order_by("-last_message_at", "-id")[:100]
    )
    return conversation_rows(member, convs)


def _can_talk(member: Member, other: Member) -> bool:
    return may_message(member, other)


def start(member: Member, member_id: int, body: str, upload_id: int | None) -> tuple[Conversation, Message]:
    require_messaging(member)
    if member_id == member.pk:
        raise ApiError(422, "self_message", "You cannot message yourself")
    other = Member.objects.filter(pk=member_id).first()
    if other is None or not _can_talk(member, other):
        raise NotFound()
    x, y = sorted((member.pk, other.pk))
    conv = Conversation.objects.select_related("member_a", "member_b").filter(member_a_id=x, member_b_id=y).first()
    if conv is not None and conv.status == C.BLOCKED:
        raise NotFound()
    if conv is None:
        check_rate(member.pk, "conversation_start")
        try:
            with transaction.atomic():
                conv = Conversation.objects.create(
                    member_a_id=x, member_b_id=y, started_by=member,
                    status=C.ACTIVE if is_connected(member.pk, other.pk) else C.REQUEST,
                )  # fmt: skip
                record("conversation.started", actor=member, target_type="conversation", target_id=conv.pk, status=conv.status)
        except IntegrityError:  # both people wrote first at the same moment
            conv = Conversation.objects.get(member_a_id=x, member_b_id=y)
        conv = Conversation.objects.select_related("member_a", "member_b").get(pk=conv.pk)
    return conv, send(member, conv.pk, body, upload_id)


def send(member: Member, conversation_id: int, body: str, upload_id: int | None) -> Message:
    require_messaging(member)
    body = body.strip()
    if not body and upload_id is None:
        raise ApiError(422, "empty_message", "Write something or add an image")
    with transaction.atomic():
        conv = (
            Conversation.objects.select_for_update().filter(Q(member_a=member) | Q(member_b=member), pk=conversation_id).first()
        )
        if conv is None or conv.status == C.BLOCKED:
            raise NotFound()
        other = Member.objects.get(pk=conv.member_b_id if conv.member_a_id == member.pk else conv.member_a_id)
        if not _can_talk(member, other):
            raise NotFound()
        if conv.status == C.REQUEST:
            if conv.started_by_id == member.pk and Message.objects.filter(conversation=conv).exists():
                raise Conflict("Wait for a reply before sending more", "awaiting_reply")
            if conv.started_by_id != member.pk:  # answering a request accepts it
                conv.status = C.ACTIVE
                record("conversation.accepted", actor=member, target_type="conversation", target_id=conv.pk)
        check_rate(member.pk, "message")
        image = media.claim_uploads(member, [upload_id], MediaUpload.Purpose.MESSAGE)[0] if upload_id is not None else None
        msg = Message.objects.create(conversation=conv, sender=member, body=body, image=image)
        conv.last_message_at = msg.created_at
        conv.save(update_fields=["status", "last_message_at"])
        record("message.sent", actor=member, target_type="conversation", target_id=conv.pk, has_image=image is not None)
        _notify_once(other, conv, member)
        transaction.on_commit(lambda: realtime.broadcast(conv.pk, msg.pk))
    return msg


def _notify_once(recipient: Member, conv: Conversation, sender: Member) -> None:
    """One unread 'new message' notification per conversation, not one per message (no pile-ups, no guilt)."""
    if not Notification.objects.filter(
        member=recipient, kind="message.new", read_at__isnull=True, payload__conversation_id=conv.pk
    ).exists():
        notify(recipient, "message.new", actor=sender, conversation_id=conv.pk)


def messages(member: Member, conversation_id: int, before: int | None, limit: int) -> tuple[list[dict], int | None]:
    """Newest first. `before` is a message id; the next cursor is the oldest id returned, or None at the start."""
    conv = get_conversation(member, conversation_id)
    qs = Message.objects.filter(conversation=conv).select_related("image").order_by("-id")
    if before is not None:
        qs = qs.filter(pk__lt=before)
    page = list(qs[: limit + 1])
    more = len(page) > limit
    page = page[:limit]
    urls = _urls(page)
    return [_message_out(m, member, urls) for m in page], (page[-1].pk if more and page else None)


def message_by_id(member: Member, conversation_id: int, message_id: int) -> dict:
    conv = get_conversation(member, conversation_id)
    msg = Message.objects.select_related("image").filter(pk=message_id, conversation=conv).first()
    if msg is None:
        raise NotFound()
    return _message_out(msg, member, _urls([msg]))


def message_rows(member: Member, msg: Message) -> dict:
    return _message_out(msg, member, _urls([msg]))


def accept(member: Member, conversation_id: int) -> Conversation:
    conv = get_conversation(member, conversation_id)
    if conv.started_by_id == member.pk:
        raise NotFound()  # the person who asked cannot accept their own request
    if conv.status != C.REQUEST:
        raise Conflict("This conversation is not a request", "not_a_request")
    conv.status = C.ACTIVE
    conv.save(update_fields=["status"])
    record("conversation.accepted", actor=member, target_type="conversation", target_id=conv.pk)
    return conv


def block(member: Member, conversation_id: int) -> None:
    """Block from the chat menu: the same block as from a profile (apps/moderation/blocks.py), plus the chat event."""
    from apps.moderation import blocks

    conv = get_conversation(member, conversation_id)
    with transaction.atomic():
        blocks.block(member, _other(conv, member).pk)
        record("conversation.blocked", actor=member, target_type="conversation", target_id=conv.pk)


def mark_read(member: Member, conversation_id: int) -> int:
    conv = get_conversation(member, conversation_id)
    n = Message.objects.filter(conversation=conv, read_at__isnull=True).exclude(sender=member).update(read_at=timezone.now())
    Notification.objects.filter(member=member, kind="message.new", read_at__isnull=True, payload__conversation_id=conv.pk).update(
        read_at=timezone.now()
    )
    return n
