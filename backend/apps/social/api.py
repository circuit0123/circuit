from datetime import date, datetime
from typing import Literal
from urllib.parse import urlparse

from ninja import Query, Router, Schema, Status
from pydantic import Field, field_validator

from apps.accounts.models import ConnectionRequest
from apps.jobs.api import JobOut
from apps.social import connections, drop, media, pulse, services, today
from apps.social.models import Post
from apps.social.schemas import AuthorOut, author
from core.auth import current_member
from core.pagination import CursorParams

router = Router()
Visibility = Literal["everyone", "connections", "organisation"]


# -- media -----------------------------------------------------------------------------------------
class UploadIn(Schema):
    purpose: Literal["post", "message"]
    content_type: Literal["image/jpeg", "image/png", "image/webp"]
    size: int = Field(gt=0)


class UploadOut(Schema):
    id: int
    upload_url: str  # PUT the file here; then call complete
    status: str


class UploadDoneOut(Schema):
    id: int
    status: str
    width: int | None
    height: int | None


@router.post(
    "/media/uploads",
    response={201: UploadOut},
    summary="Start an image upload",
    description="Returns a short-lived signed URL for one JPEG, PNG or WebP image of at most 5 MB. Upload the file to it, "
    "then call complete. The browser resizes to 1440px first; the server re-encodes and removes metadata.",
)
def start_upload(request, body: UploadIn):
    upload, url = media.create_upload(current_member(request), body.purpose, body.content_type, body.size)
    return Status(201, {"id": upload.pk, "upload_url": url, "status": upload.status})


@router.post(
    "/media/uploads/{upload_id}/complete",
    response=UploadDoneOut,
    summary="Finish an image upload",
    description="Checks the uploaded file really is an image, strips metadata and stores two sizes. Safe to repeat. "
    "Someone else's upload is a 404.",
)
def complete_upload(request, upload_id: int):
    u = media.complete_upload(current_member(request), upload_id)
    return {"id": u.pk, "status": u.status, "width": u.width, "height": u.height}


# -- posts -----------------------------------------------------------------------------------------
class MediaIn(Schema):
    upload_id: int
    alt_text: str = Field(min_length=1, max_length=300, description="What the image shows, for people using a screen reader")


class PostIn(Schema):
    body: str = Field("", max_length=500)
    link: str = Field("", max_length=500)
    visibility: Visibility
    capabilities: list[str] = Field(default_factory=list, max_length=3, description="Capability slugs from our list")
    media: list[MediaIn] = Field(default_factory=list, max_length=4)

    @field_validator("link")
    @classmethod
    def _http_only(cls, v: str) -> str:
        if v and (urlparse(v).scheme not in ("http", "https") or not urlparse(v).netloc):
            raise ValueError("Use a full http(s) link")
        return v


class CapabilityTagOut(Schema):
    slug: str
    name: str


class PostMediaOut(Schema):
    alt_text: str
    w1440: str
    w480: str
    width: int | None
    height: int | None


class PrivateStatsOut(Schema):
    reactions: dict[str, int]
    replies: int


class PostOut(Schema):
    id: int
    author: AuthorOut
    body: str
    link: str
    visibility: str
    status: str
    created_at: datetime
    capabilities: list[CapabilityTagOut]
    media: list[PostMediaOut]
    my_reactions: list[str]
    private_stats: PrivateStatsOut | None = None  # the author's own totals; always None for everyone else


def _post(viewer, post: Post) -> dict:
    return services.post_rows(viewer, [post])[0]


@router.post(
    "/posts",
    response={201: PostOut},
    summary="Post a build log",
    description="Up to 4 images (each with alt text), 500 characters, 3 capability tags and an optional link. "
    "Members under 18 can only post to their organisation.",
)
def create_post(request, body: PostIn):
    member = current_member(request)
    post = services.create_post(member, body.dict())
    return Status(201, _post(member, Post.objects.select_related("author").get(pk=post.pk)))


@router.get(
    "/posts/{post_id}",
    response=PostOut,
    summary="One build log",
    description="404 unless the post's visibility lets me see it. Reaction totals appear only on my own posts.",
)
def get_post(request, post_id: int):
    member = current_member(request)
    return _post(member, services.get_post(member, post_id))


@router.delete(
    "/posts/{post_id}", response={204: None}, summary="Delete my build log", description="Author only; anyone else gets a 404."
)
def delete_post(request, post_id: int):
    services.delete_post(current_member(request), post_id)
    return Status(204, None)


@router.get(
    "/members/{member_id}/posts",
    response=list[PostOut],
    summary="A member's build logs",
    description="Newest first, only the ones I am allowed to see. 404 for members I cannot see.",
)
def member_posts(request, member_id: int):
    member = current_member(request)
    return services.post_rows(member, services.member_posts(member, member_id))


# -- reactions and replies -----------------------------------------------------------------------------
ReactionKind = Literal["helpful", "intro_me", "lets_talk"]


@router.put(
    "/posts/{post_id}/reactions/{kind}",
    response={204: None},
    summary="React to a build log",
    description="Helpful, intro_me or lets_talk. Safe to repeat. Nobody but the author sees totals.",
)
def react(request, post_id: int, kind: ReactionKind):
    services.react(current_member(request), post_id, kind)
    return Status(204, None)


@router.delete(
    "/posts/{post_id}/reactions/{kind}", response={204: None}, summary="Remove my reaction", description="Safe to repeat."
)
def unreact(request, post_id: int, kind: ReactionKind):
    services.unreact(current_member(request), post_id, kind)
    return Status(204, None)


class ReplyIn(Schema):
    body: str = Field(min_length=1, max_length=300)
    parent_id: int | None = Field(None, description="Reply to a top-level reply (one level deep only)")


class ReplyOut(Schema):
    id: int
    author: AuthorOut
    body: str
    created_at: datetime
    replies: list["ReplyOut"]


@router.get(
    "/posts/{post_id}/replies",
    response=list[ReplyOut],
    summary="Replies to a build log",
    description="Oldest first, nested one level. Replies from people I blocked or who blocked me are left out.",
)
def list_replies(request, post_id: int):
    return services.list_replies(current_member(request), post_id)


@router.post(
    "/posts/{post_id}/replies",
    response={201: ReplyOut},
    summary="Reply to a build log",
    description="Up to 300 characters. The post's author is notified.",
)
def reply(request, post_id: int, body: ReplyIn):
    member = current_member(request)
    r = services.reply_to(member, post_id, body.body, body.parent_id)
    return Status(201, {"id": r.pk, "author": author(member), "body": r.body, "created_at": r.created_at, "replies": []})


@router.delete(
    "/replies/{reply_id}",
    response={204: None},
    summary="Delete a reply",
    description="The reply's author or the post's author. Anyone else gets a 404.",
)
def delete_reply(request, reply_id: int):
    services.delete_reply(current_member(request), reply_id)
    return Status(204, None)


# -- pulse, today, drop ---------------------------------------------------------------------------------
class ActivityOut(Schema):
    type: str  # circuit_completed, intro_accepted, startup_claimed
    circuit_id: int | None = None
    members: list[int] | None = None
    intro_id: int | None = None
    target_id: int | None = None
    startup_id: int | None = None
    startup_name: str | None = None


class SkillDemandOut(Schema):
    slug: str
    name: str
    open_roles: int


class SkillsInDemandOut(Schema):
    skills: list[SkillDemandOut]


class PulseItemOut(Schema):
    kind: Literal["post", "role", "activity", "skills_in_demand"]
    key: str
    created_at: datetime
    seen: bool
    post: PostOut | None = None
    role: JobOut | None = None
    activity: ActivityOut | None = None
    skills_in_demand: SkillsInDemandOut | None = None


class PulseOut(Schema):
    items: list[PulseItemOut]
    next_cursor: str | None
    caught_up: bool  # true when there is nothing more that is new: show "You're caught up"


class PulseParams(CursorParams):
    include_seen: bool = False


@router.get(
    "/pulse",
    response=PulseOut,
    summary="Pulse feed",
    description="Chronological, last 7 days, never ranked. Shows what is new since I last marked Pulse as seen; "
    "include_seen=true shows earlier items too. Ends with caught_up=true.",
)
def get_pulse(request, params: PulseParams = Query(...)):
    return pulse.pulse(current_member(request), params.cursor, params.limit, params.include_seen)


@router.post(
    "/pulse/seen",
    response={204: None},
    summary="Mark Pulse as seen",
    description="Call when the member reaches the end. The next visit shows only newer items.",
)
def pulse_seen(request):
    pulse.mark_seen(current_member(request))
    return Status(204, None)


class StoryRoleOut(Schema):
    id: int
    title: str
    kind: str
    startup_id: int
    created_at: datetime


class CircleOut(Schema):
    kind: Literal["member", "startup"]
    id: int
    name: str
    latest_at: datetime
    seen: bool
    author: AuthorOut | None
    posts: list[PostOut]
    roles: list[StoryRoleOut]


@router.get(
    "/today",
    response=list[CircleOut],
    summary="Today strip",
    description="Circles for connections, my organisation and startups I follow who posted or opened a role in the last "
    "24 hours. Unseen first. Items are included, so the story viewer needs no second call.",
)
def get_today(request):
    return today.today_strip(current_member(request))


class ViewedIn(Schema):
    kind: Literal["member", "startup"]
    id: int


@router.post(
    "/today/seen",
    response={204: None},
    summary="Mark a circle as viewed",
    description="Call when a circle is opened. A circle that is not in my strip is a 404.",
)
def today_seen(request, body: ViewedIn):
    today.mark_viewed(current_member(request), body.kind, body.id)
    return Status(204, None)


class DropCardOut(Schema):
    member: AuthorOut
    reason: str
    is_bridge: bool
    outcome: Literal["intro", "skip"] | None


class DropOut(Schema):
    date: date
    cards: list[DropCardOut]
    done: bool
    next_drop_at: datetime


@router.get(
    "/drop/today",
    response=DropOut,
    summary="Today's Daily Drop",
    description="Up to 3 people, ready at 08:00 IST. Empty until the daily job has run. Members under 18 get no drop.",
)
def get_drop(request):
    return drop.today_drop(current_member(request))


class SwipeIn(Schema):
    direction: Literal["intro", "skip"]


@router.post(
    "/drop/today/{member_id}/swipe",
    response=DropOut,
    summary="Answer a Daily Drop card",
    description="intro or skip. This records the choice only; to ask for the intro, call the intros endpoint next. "
    "A person who is not in today's drop is a 404.",
)
def swipe(request, member_id: int, body: SwipeIn):
    return drop.swipe(current_member(request), member_id, body.direction)


# -- follows ------------------------------------------------------------------------------------------
class FollowedStartupOut(Schema):
    id: int
    name: str
    sector: str
    hiring: bool


@router.post("/startups/{startup_id}/follow", response={204: None}, summary="Follow a startup", description="Safe to repeat.")
def follow(request, startup_id: int):
    services.follow(current_member(request), startup_id)
    return Status(204, None)


@router.delete("/startups/{startup_id}/follow", response={204: None}, summary="Unfollow a startup", description="Safe to repeat.")
def unfollow(request, startup_id: int):
    services.unfollow(current_member(request), startup_id)
    return Status(204, None)


@router.get(
    "/me/follows",
    response=list[FollowedStartupOut],
    summary="Startups I follow",
    description="Newest first. Only I can see this list.",
)
def my_follows(request):
    return [
        {"id": s.pk, "name": s.name, "sector": s.sector, "hiring": s.hiring} for s in services.my_follows(current_member(request))
    ]


# -- connections ---------------------------------------------------------------------------------------
class ConnectionRequestIn(Schema):
    member_id: int
    note: str = Field("", max_length=300)


class ConnectionRequestOut(Schema):
    id: int
    sender: AuthorOut
    recipient: AuthorOut
    note: str
    status: str
    created_at: datetime


class RespondIn(Schema):
    accept: bool


class RequestParams(Schema):
    box: Literal["incoming", "outgoing"] = "incoming"


def _request_out(r: ConnectionRequest) -> dict:
    return {
        "id": r.pk, "sender": author(r.sender), "recipient": author(r.recipient), "note": r.note, "status": r.status,
        "created_at": r.created_at,
    }  # fmt: skip


@router.get(
    "/connections",
    response=list[AuthorOut],
    summary="My connections",
    description="People I am connected to. Only I see this list; there are no public counts.",
)
def list_connections(request):
    return connections.list_connections(current_member(request))


@router.post(
    "/connections/requests",
    response={201: ConnectionRequestOut},
    summary="Ask to connect",
    description="With an optional note of up to 300 characters. If they already asked me, this accepts it. "
    "A request to or from someone under 18 must stay inside one organisation; anyone I may not reach is a 404.",
)
def send_request(request, body: ConnectionRequestIn):
    r = connections.send_request(current_member(request), body.member_id, body.note)
    return Status(201, _request_out(ConnectionRequest.objects.select_related("sender", "recipient").get(pk=r.pk)))


@router.get(
    "/connections/requests",
    response=list[ConnectionRequestOut],
    summary="Pending connection requests",
    description="box=incoming (default) or outgoing. Pending ones only, newest first.",
)
def list_requests(request, params: RequestParams = Query(...)):
    return [_request_out(r) for r in connections.list_requests(current_member(request), params.box)]


@router.post(
    "/connections/requests/{request_id}/respond",
    response=ConnectionRequestOut,
    summary="Accept or decline a connection request",
    description="Only the person it was sent to. Accepting makes us connections.",
)
def respond(request, request_id: int, body: RespondIn):
    r = connections.respond(current_member(request), request_id, body.accept)
    return _request_out(ConnectionRequest.objects.select_related("sender", "recipient").get(pk=r.pk))


# Declared last: '/connections/{member_id}' would otherwise swallow '/connections/requests'.
@router.delete(
    "/connections/{member_id}", response={204: None}, summary="Remove a connection", description="404 if we are not connected."
)
def remove_connection(request, member_id: int):
    connections.remove_connection(current_member(request), member_id)
    return Status(204, None)
