"""Build logs, reactions, replies and follows (F15, F17). Routers stay thin; the rules live here.

"No public counts": post_rows() gives reaction totals and the reply count only to the post's own author.
Anything the viewer may not see is a 404, the same as a post that does not exist.
"""

from datetime import UTC, datetime

from django.db import IntegrityError, transaction
from django.db.models import Count, Q

from apps.accounts.models import Member
from apps.events.services import record
from apps.matching.models import Capability
from apps.notifications.services import notify
from apps.social import media
from apps.social.models import Follow, MediaUpload, Post, PostMedia, Reaction, Reply
from apps.social.relations import SOCIAL_ROLES, can_see_post, is_blocked, visible_posts
from apps.social.schemas import author
from apps.startups.models import Startup
from apps.startups.services import get_startup
from core.errors import ApiError, Forbidden, NotFound
from core.pagination import decode_cursor, encode_cursor
from core.ratelimit import check_rate

MAX_MEDIA = 4
MAX_TAGS = 3
V = Post.Visibility


def require_social(member: Member) -> None:
    if member.role not in SOCIAL_ROLES:
        raise Forbidden()


# -- posts ----------------------------------------------------------------------------------------------
def create_post(member: Member, data: dict) -> Post:
    require_social(member)
    visibility = data["visibility"]
    if member.is_minor and (visibility != V.ORGANISATION or member.organisation_id is None):
        raise Forbidden("Members under 18 can post to their organisation only")
    if visibility == V.ORGANISATION and member.organisation_id is None:
        raise ApiError(422, "no_organisation", "Join an organisation to post to it")
    images = data.get("media", [])
    if not data.get("body", "").strip() and not images:
        raise ApiError(422, "empty_post", "Add some text or an image")
    if len(images) > MAX_MEDIA:
        raise ApiError(422, "too_many_images", f"A build log can have up to {MAX_MEDIA} images")
    slugs = list(dict.fromkeys(data.get("capabilities", [])))
    if len(slugs) > MAX_TAGS:
        raise ApiError(422, "too_many_tags", f"Pick up to {MAX_TAGS} capabilities")
    caps = list(Capability.objects.filter(slug__in=slugs))
    if len(caps) != len(slugs):
        raise ApiError(422, "unknown_capability", "One of the capabilities is not in our list")
    check_rate(member.pk, "post")
    uploads = media.claim_uploads(member, [m["upload_id"] for m in images], MediaUpload.Purpose.POST)
    with transaction.atomic():
        post = Post.objects.create(
            author=member, body=data.get("body", "").strip(), link=data.get("link") or "", visibility=visibility
        )
        post.capabilities.set(caps)
        PostMedia.objects.bulk_create(
            [
                PostMedia(post=post, upload=u, alt_text=m["alt_text"].strip(), order=i)
                for i, (u, m) in enumerate(zip(uploads, images))
            ]
        )
        record("post.created", actor=member, target_type="post", target_id=post.pk, visibility=visibility, images=len(uploads))
    return post


def get_post(viewer: Member, post_id: int) -> Post:
    require_social(viewer)
    post = Post.objects.select_related("author").filter(pk=post_id).first()
    if post is None or not can_see_post(viewer, post):
        raise NotFound()
    return post


def delete_post(member: Member, post_id: int) -> None:
    post = Post.objects.filter(pk=post_id, author=member).first()
    if post is None:
        raise NotFound()
    uploads = [pm.upload for pm in post.media.select_related("upload")]
    record("post.deleted", actor=member, target_type="post", target_id=post.pk)
    post.delete()
    for u in uploads:
        u.delete()
    media.delete_files(uploads)


def post_rows(viewer: Member, posts) -> list[dict]:
    """Posts as the viewer sees them. Totals only for the author's own posts; `my_reactions` is just the viewer's own."""
    posts = list(posts)
    media.prime_photos(p.author for p in posts)
    ids = [p.pk for p in posts]
    mine: dict[int, list[str]] = {}
    for post_id, kind in Reaction.objects.filter(post_id__in=ids, member=viewer).values_list("post_id", "kind"):
        mine.setdefault(post_id, []).append(kind)
    own = [p.pk for p in posts if p.author_id == viewer.pk]
    totals: dict[int, dict[str, int]] = {}
    for post_id, kind, n in Reaction.objects.filter(post_id__in=own).values_list("post_id", "kind").annotate(n=Count("id")):
        totals.setdefault(post_id, {})[kind] = n
    reply_counts = dict(
        Reply.objects.filter(post_id__in=own, status=Post.Status.VISIBLE).values_list("post_id").annotate(n=Count("id"))
    )
    media_by_post: dict[int, list[PostMedia]] = {}
    for pm in PostMedia.objects.filter(post_id__in=ids).select_related("upload"):
        media_by_post.setdefault(pm.post_id, []).append(pm)
    urls = media.urls_for(pm.upload for pms in media_by_post.values() for pm in pms)
    caps: dict[int, list[dict]] = {}
    for post_id, slug, name in Post.capabilities.through.objects.filter(post_id__in=ids).values_list(
        "post_id", "capability__slug", "capability__name"
    ):
        caps.setdefault(post_id, []).append({"slug": slug, "name": name})
    rows = []
    for p in posts:
        row = {
            "id": p.pk, "author": author(p.author), "body": p.body, "link": p.link, "visibility": p.visibility,
            "status": p.status, "created_at": p.created_at, "capabilities": caps.get(p.pk, []),
            "media": [{"alt_text": pm.alt_text, **urls[pm.upload_id]} for pm in sorted(media_by_post.get(p.pk, []), key=lambda x: x.order)],
            "my_reactions": sorted(mine.get(p.pk, [])),
        }  # fmt: skip
        if p.author_id == viewer.pk:
            row["private_stats"] = {"reactions": totals.get(p.pk, {}), "replies": reply_counts.get(p.pk, 0)}
        rows.append(row)
    return rows


def member_posts(viewer: Member, member_id: int, cursor: str | None = None, limit: int = 20) -> tuple[list[Post], str | None]:
    """One page of a member's build logs, newest first, plus the cursor for the next page (None on the last one)."""
    from apps.social.relations import is_connected, same_org

    require_social(viewer)
    target = Member.objects.filter(pk=member_id).first()
    if target is None or target.suspended_at or is_blocked(viewer.pk, target.pk) or target.role not in SOCIAL_ROLES:
        raise NotFound()
    if target.pk != viewer.pk and (target.is_minor or target.profile_visibility == Member.Visibility.HIDDEN):
        if not (is_connected(viewer.pk, target.pk) or same_org(viewer, target)):
            raise NotFound()  # a stranger cannot tell a hidden member from one who does not exist
    qs = visible_posts(viewer).filter(author=target).select_related("author").order_by("-created_at", "-id")
    if cursor:
        micros, post_id = decode_cursor(cursor, 2)
        if not isinstance(micros, int) or not isinstance(post_id, int):
            raise ApiError(422, "bad_cursor", "That page marker is not valid. Reload from the top.")
        before = datetime.fromtimestamp(micros / 1_000_000, tz=UTC)
        qs = qs.filter(Q(created_at__lt=before) | Q(created_at=before, pk__lt=post_id))
    page = list(qs[: limit + 1])
    more = len(page) > limit
    page = page[:limit]
    nxt = encode_cursor(int(page[-1].created_at.timestamp() * 1_000_000), page[-1].pk) if more else None
    return page, nxt


# -- reactions ------------------------------------------------------------------------------------------
def react(member: Member, post_id: int, kind: str) -> None:
    post = get_post(member, post_id)
    check_rate(member.pk, "reaction")
    try:
        with transaction.atomic():
            _, created = Reaction.objects.get_or_create(post=post, member=member, kind=kind)
    except IntegrityError:  # two taps at once
        created = False
    if created:
        record("reaction.added", actor=member, target_type="post", target_id=post.pk, kind=kind)


def unreact(member: Member, post_id: int, kind: str) -> None:
    post = get_post(member, post_id)
    deleted, _ = Reaction.objects.filter(post=post, member=member, kind=kind).delete()
    if deleted:
        record("reaction.removed", actor=member, target_type="post", target_id=post.pk, kind=kind)


# -- replies --------------------------------------------------------------------------------------------
def reply_to(member: Member, post_id: int, body: str, parent_id: int | None) -> Reply:
    post = get_post(member, post_id)
    body = body.strip()
    if not body:
        raise ApiError(422, "empty_reply", "Write something first")
    parent = None
    if parent_id is not None:
        parent = Reply.objects.filter(pk=parent_id, post=post, status=Post.Status.VISIBLE).first()
        if parent is None:
            raise NotFound()
        if parent.parent_id is not None:
            raise ApiError(422, "reply_too_deep", "Replies go one level deep")
        if is_blocked(member.pk, parent.author_id):
            raise NotFound()
    check_rate(member.pk, "reply")
    reply = Reply.objects.create(post=post, author=member, body=body, parent=parent)
    record("reply.created", actor=member, target_type="post", target_id=post.pk, reply_id=reply.pk)
    if post.author_id != member.pk:
        notify(post.author_id, "post.reply", actor=member, post_id=post.pk, reply_id=reply.pk)
    return reply


def list_replies(viewer: Member, post_id: int) -> list[dict]:
    from apps.social.relations import blocked_ids

    post = get_post(viewer, post_id)
    hidden = blocked_ids(viewer.pk)
    replies = (
        Reply.objects.filter(post=post, status=Post.Status.VISIBLE, author__suspended_at__isnull=True)
        .exclude(author_id__in=hidden)
        .select_related("author")
        .order_by("created_at", "id")
    )
    tops: list[dict] = []
    by_id: dict[int, dict] = {}
    for r in replies:
        row = {"id": r.pk, "author": author(r.author), "body": r.body, "created_at": r.created_at, "replies": []}
        by_id[r.pk] = row
        if r.parent_id is None:
            tops.append(row)
        elif r.parent_id in by_id:
            by_id[r.parent_id]["replies"].append(row)
    return tops


def delete_reply(member: Member, reply_id: int) -> None:
    """The reply's author or the post's author may delete it."""
    reply = Reply.objects.select_related("post").filter(pk=reply_id).first()
    if reply is None or member.pk not in (reply.author_id, reply.post.author_id) or not can_see_post(member, reply.post):
        raise NotFound()
    record("reply.deleted", actor=member, target_type="post", target_id=reply.post_id, reply_id=reply.pk)
    reply.delete()


# -- follows --------------------------------------------------------------------------------------------
def follow(member: Member, startup_id: int) -> None:
    require_social(member)
    startup = get_startup(startup_id)
    _, created = Follow.objects.get_or_create(member=member, startup=startup)
    if created:
        record("follow.added", actor=member, target_type="startup", target_id=startup.pk)


def unfollow(member: Member, startup_id: int) -> None:
    require_social(member)
    deleted, _ = Follow.objects.filter(member=member, startup_id=startup_id).delete()
    if deleted:
        record("follow.removed", actor=member, target_type="startup", target_id=startup_id)


def my_follows(member: Member) -> list[Startup]:
    require_social(member)
    return [f.startup for f in Follow.objects.filter(member=member).select_related("startup").order_by("-created_at")]


def picture_tiles(viewer: Member, author_ids, limit: int) -> list[dict]:
    """The first picture of each of the latest build logs by these people that the viewer may see (Startup page, Profile grid).
    Empty when Pulse is off for the viewer. Posts with no picture are skipped."""
    from core import flags

    if not flags.enabled("pulse", viewer):
        return []
    posts = list(
        visible_posts(viewer)
        .filter(author_id__in=list(author_ids), status=Post.Status.VISIBLE, media__isnull=False)
        .order_by("-created_at", "-id")
        .distinct()[:limit]
    )
    first: dict[int, PostMedia] = {}
    for pm in PostMedia.objects.filter(post__in=posts).select_related("upload").order_by("-order"):
        first[pm.post_id] = pm  # ends on order 0, the first picture
    urls = media.urls_for(pm.upload for pm in first.values())
    return [
        {"post_id": p.pk, "image": {"alt_text": first[p.pk].alt_text, **urls[first[p.pk].upload_id]}}
        for p in posts
        if p.pk in first
    ]
