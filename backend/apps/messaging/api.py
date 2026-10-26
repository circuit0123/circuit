from datetime import datetime
from typing import Literal

from ninja import Query, Router, Schema, Status
from pydantic import Field

from apps.messaging import services
from apps.messaging.models import Conversation
from apps.social.schemas import AuthorOut
from core.auth import current_member
from core.pagination import CursorParams

router = Router()


class MessageImageOut(Schema):
    width: int | None
    height: int | None
    w1440: str  # signed link, valid about an hour
    w480: str


class MessageOut(Schema):
    id: int
    conversation_id: int
    mine: bool
    body: str  # empty if a moderator removed the message
    image: MessageImageOut | None
    removed: bool
    created_at: datetime
    read_at: datetime | None  # my own messages only, and only when both of us switched read receipts on (else null)


class ConversationOut(Schema):
    id: int
    status: Literal["request", "active"]
    other: AuthorOut
    started_by_me: bool
    last_message_at: datetime | None
    unread: int  # only I see this
    last_message: MessageOut | None


class FolderParams(Schema):
    folder: Literal["chats", "requests"] = "chats"


class StartIn(Schema):
    member_id: int
    body: str = Field("", max_length=2000)
    upload_id: int | None = None


class SendIn(Schema):
    body: str = Field("", max_length=2000)
    upload_id: int | None = Field(None, description="A finished upload with purpose=message")


class StartedOut(Schema):
    conversation: ConversationOut
    message: MessageOut


class MessagePage(Schema):
    items: list[MessageOut]  # newest first
    next_cursor: str | None


class UnreadOut(Schema):
    marked: int


class UnreadCountsOut(Schema):
    chats: int  # conversations with something I have not read
    requests: int  # always 0 for members under 18


def _conv(member, conv: Conversation) -> dict:
    return services.conversation_rows(member, [conv])[0]


@router.get(
    "",
    response=list[ConversationOut],
    summary="My conversations",
    description="folder=chats (accepted) or requests (first messages from people I am not connected to). Latest first. "
    "Members under 18 never get requests from strangers.",
)
def list_conversations(request, params: FolderParams = Query(...)):
    return services.list_conversations(current_member(request), params.folder)


@router.get(
    "/unread-count",
    response=UnreadCountsOut,
    summary="Unread conversations",
    description="How many chats and requests have something I have not read: for the Inbox tab dot and the desktop rail.",
)
def unread_count(request):
    return services.unread_counts(current_member(request))


@router.post(
    "",
    response={201: StartedOut},
    summary="Start a conversation",
    description="Sends the first message. Connected people chat directly; others receive it as a request. "
    "Someone I may not message (under-18 rules, blocks, hidden profiles) is a 404.",
)
def start(request, body: StartIn):
    member = current_member(request)
    conv, msg = services.start(member, body.member_id, body.body, body.upload_id)
    conv.refresh_from_db()
    return Status(201, {"conversation": _conv(member, conv), "message": services.message_rows(member, msg)})


@router.get(
    "/{conversation_id}",
    response=ConversationOut,
    summary="One conversation",
    description="404 unless I am one of the two people.",
)
def get_conversation(request, conversation_id: int):
    member = current_member(request)
    return _conv(member, services.get_conversation(member, conversation_id))


@router.get(
    "/{conversation_id}/messages",
    response=MessagePage,
    summary="Messages in a conversation",
    description="Newest first. Pass next_cursor as cursor to load older ones. `read_at` on my own messages is set only when both of us have read receipts on.",
)
def list_messages(request, conversation_id: int, params: CursorParams = Query(...)):
    from core.pagination import decode_cursor, encode_cursor

    before = decode_cursor(params.cursor, 1)[0] if params.cursor else None
    items, nxt = services.messages(current_member(request), conversation_id, before, params.limit)
    return {"items": items, "next_cursor": encode_cursor(nxt) if nxt else None}


@router.get(
    "/{conversation_id}/messages/{message_id}",
    response=MessageOut,
    summary="One message",
    description="What the client fetches after a Realtime nudge. 404 unless I am in the conversation.",
)
def get_message(request, conversation_id: int, message_id: int):
    return services.message_by_id(current_member(request), conversation_id, message_id)


@router.post(
    "/{conversation_id}/messages",
    response={201: MessageOut},
    summary="Send a message",
    description="Text up to 2000 characters, an image, or both. In a request the sender gets one message until the other "
    "person answers; answering accepts the request.",
)
def send(request, conversation_id: int, body: SendIn):
    member = current_member(request)
    return Status(201, services.message_rows(member, services.send(member, conversation_id, body.body, body.upload_id)))


@router.post(
    "/{conversation_id}/accept",
    response=ConversationOut,
    summary="Accept a request",
    description="Only the person the request was sent to.",
)
def accept(request, conversation_id: int):
    member = current_member(request)
    return _conv(member, services.accept(member, conversation_id))


@router.post(
    "/{conversation_id}/decline",
    response={204: None},
    summary="Decline a request",
    description="'No thanks' to a request I received. It disappears for me; the sender is not told. Only the person the request "
    "was sent to; a conversation that is not a request is a 409 `not_a_request`.",
)
def decline(request, conversation_id: int):
    services.decline(current_member(request), conversation_id)
    return Status(204, None)


@router.post(
    "/{conversation_id}/block",
    response={204: None},
    summary="Block the other person",
    description="Closes the conversation and blocks them everywhere (matches, posts, messages, intros).",
)
def block(request, conversation_id: int):
    services.block(current_member(request), conversation_id)
    return Status(204, None)


@router.post(
    "/{conversation_id}/read",
    response=UnreadOut,
    summary="Mark messages as read",
    description="Marks what the other person sent as read.",
)
def read(request, conversation_id: int):
    return {"marked": services.mark_read(current_member(request), conversation_id)}
