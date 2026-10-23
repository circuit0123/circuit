"""The Today strip (F16): circles for people and startups who posted or opened a role in the last 24 hours.

Who: my connections, my organisation, and the startups I follow. A circle is unseen until I open it; it turns
unseen again only if something newer arrives. Items are included, so the story viewer needs no second call.
"""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.accounts.models import Member
from apps.events.services import record
from apps.jobs.models import Job
from apps.social import services
from apps.social.models import Post, StoryView
from apps.social.pulse import followed_startups, ist_day_start
from apps.social.relations import blocked_ids, connected_ids, org_mate_ids, visible_posts
from apps.social.schemas import author
from apps.startups.models import Startup
from apps.startups.services import team_member_ids
from core.errors import ApiError, NotFound

KINDS = ("member", "startup")


def _day(now):
    return ist_day_start(now).date()


def today_strip(member: Member) -> list[dict]:
    services.require_social(member)
    now = timezone.now()
    since = now - timedelta(hours=settings.TODAY_WINDOW_HOURS)
    startups = followed_startups(member)
    people = (connected_ids(member.pk) | org_mate_ids(member)) - blocked_ids(member.pk) - {member.pk}
    posts = list(
        visible_posts(member)
        .filter(author_id__in=people, created_at__gte=since)
        .select_related("author")
        .order_by("-created_at", "-id")
    )
    by_author: dict[int, list[Post]] = {}
    for p in posts:
        by_author.setdefault(p.author_id, []).append(p)
    views = {
        (v.author_id, v.startup_id): v.viewed_at
        for v in StoryView.objects.filter(viewer=member, date__gte=_day(now - timedelta(days=1)))
    }
    circles: list[dict] = []
    for author_id, plist in by_author.items():
        newest = plist[0].created_at
        viewed = views.get((author_id, None))
        circles.append(
            {
                "kind": "member", "id": author_id, "name": plist[0].author.display_name, "latest_at": newest,
                "seen": bool(viewed and viewed >= newest), "author": author(plist[0].author),
                "posts": services.post_rows(member, plist), "roles": [],
            }
        )  # fmt: skip
    for s in startups:
        roles = list(Job.objects.filter(startup=s, is_open=True, created_at__gte=since).order_by("-created_at"))
        team = set(team_member_ids(s)) - blocked_ids(member.pk)
        team_posts = [p for p in posts if p.author_id in team] if team else []
        if not roles and not team_posts:
            continue
        newest = max([r.created_at for r in roles] + [p.created_at for p in team_posts])
        viewed = views.get((None, s.pk))
        circles.append(
            {
                "kind": "startup", "id": s.pk, "name": s.name, "latest_at": newest, "seen": bool(viewed and viewed >= newest),
                "author": None, "posts": services.post_rows(member, team_posts),
                "roles": [{"id": r.pk, "title": r.title, "kind": r.kind, "startup_id": s.pk, "created_at": r.created_at} for r in roles],
            }
        )  # fmt: skip
    circles.sort(key=lambda c: (c["seen"], -c["latest_at"].timestamp()))  # unseen first, newest first
    return circles


def mark_viewed(member: Member, kind: str, ident: int) -> None:
    """Called when the viewer opens a circle. Only circles that are actually in my strip can be marked."""
    services.require_social(member)
    if kind not in KINDS:
        raise ApiError(422, "bad_kind", "kind must be member or startup")
    strip = {(c["kind"], c["id"]) for c in today_strip(member)}
    if (kind, ident) not in strip:
        raise NotFound()
    day = _day(timezone.now())
    if kind == "member":
        StoryView.objects.update_or_create(viewer=member, author_id=ident, startup=None, date=day)
    else:
        StoryView.objects.update_or_create(viewer=member, startup=Startup.objects.get(pk=ident), author=None, date=day)
    record("today.viewed", actor=member, target_type=kind, target_id=ident)
