"""Pulse: a calm, chronological feed (F15). Not ranked, not endless.

Shows what is new since the member last marked Pulse as seen (at most 7 days), then "You're caught up".
`include_seen=true` lets the client show "earlier this week". Kinds: post, role, activity, skills_in_demand.
Every post goes through the same visibility rule as everywhere else (relations.visible_posts).
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.utils import timezone

from apps.accounts.models import Member
from apps.circuits.models import Circuit
from apps.events.models import Event
from apps.events.services import record
from apps.intros.models import IntroRequest
from apps.jobs.services import list_jobs
from apps.social import services
from apps.social.models import Follow
from apps.social.relations import blocked_ids, connected_ids, org_mate_ids, visible_posts
from apps.startups.models import Startup
from apps.startups.services import default_centre, team_member_ids
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
MAX_ROLES = 5
SLACK = 10  # extra rows per source, so items sharing a timestamp are not lost at a page edge


@dataclass
class Item:
    at: datetime
    kind: str
    id: int
    data: dict

    @property
    def key(self) -> tuple:
        return ((self.at - EPOCH) // timedelta(microseconds=1), self.kind, self.id)  # exact integer microseconds


def followed_startups(member: Member) -> list[Startup]:
    return [f.startup for f in Follow.objects.filter(member=member).select_related("startup")]


def author_circle(member: Member, startups: list[Startup] | None = None) -> set[int]:
    """People whose build logs may appear for me: connections, my organisation, and the teams of startups I follow."""
    ids = connected_ids(member.pk) | org_mate_ids(member)
    for s in startups if startups is not None else followed_startups(member):
        ids.update(team_member_ids(s))
    return ids - blocked_ids(member.pk) - {member.pk}


def post_items(member: Member, since: datetime, upto: datetime, circle: set[int], limit: int) -> list[Item]:
    qs = visible_posts(member).filter(author_id__in=circle, created_at__gte=since, created_at__lte=upto)
    return [Item(c, "post", i, {}) for i, c in qs.order_by("-created_at", "-id").values_list("id", "created_at")[:limit]]


def role_items(member: Member, since: datetime, upto: datetime, startups: list[Startup], window_start: datetime) -> list[Item]:
    """New open roles at startups I follow, plus (students) roles near me that match my skills.

    At most MAX_ROLES in the whole window, newest first, however far I have scrolled: roles are a nudge, not the feed.
    """
    followed = {s.pk for s in startups}
    items = []
    for row in list_jobs(member, {}):
        if row["created_at"] < window_start:
            continue
        near_match = (
            member.role == "student"
            and (row["skill_match"] or 0) > 0
            and row["distance_km"] is not None
            and row["distance_km"] <= settings.STUDENT_MAX_DISTANCE_KM
        )
        if row["startup_id"] in followed or near_match:
            items.append(Item(row["created_at"], "role", row["id"], row))
    items.sort(key=lambda i: i.key, reverse=True)
    return [i for i in items[:MAX_ROLES] if since <= i.at <= upto]


def activity_items(member: Member, since: datetime, upto: datetime) -> list[Item]:
    """Circuits closed by people I know, my intros that worked, startups newly claimed near me."""
    items: list[Item] = []
    friends = connected_ids(member.pk) | {member.pk}
    done = Event.objects.filter(type="circuit.completed", created_at__gte=since, created_at__lte=upto).order_by("-created_at")[
        :50
    ]
    circuits = {c.pk: c for c in Circuit.objects.filter(pk__in=[e.target_id for e in done]).prefetch_related("legs__giver")}
    for e in done:
        c = circuits.get(e.target_id or 0)
        people = [leg.giver for leg in c.legs.all()] if c else []
        if c and any(p.pk in friends for p in people) and not any(p.pk in blocked_ids(member.pk) for p in people):
            items.append(
                Item(
                    e.created_at,
                    "activity",
                    c.pk,
                    {"type": "circuit_completed", "circuit_id": c.pk, "members": [p.pk for p in people]},
                )
            )
    worked = IntroRequest.objects.filter(
        requester=member, status__in=["accepted", "completed"], stage="done", responded_at__gte=since, responded_at__lte=upto
    )
    for intro in worked:
        items.append(
            Item(
                cast(datetime, intro.responded_at),
                "activity",
                intro.pk,
                {"type": "intro_accepted", "intro_id": intro.pk, "target_id": intro.target_id},
            )
        )
    lat, lng = default_centre(member)
    claimed = Startup.objects.filter(
        claimed_at__gte=since,
        claimed_at__lte=upto,
        location__distance_lte=(Point(lng, lat, srid=4326), D(km=settings.STUDENT_MAX_DISTANCE_KM)),
    ).order_by("-claimed_at")[:20]
    for s in claimed:
        items.append(
            Item(
                cast(datetime, s.claimed_at),
                "activity",
                s.pk,
                {"type": "startup_claimed", "startup_id": s.pk, "startup_name": s.name},
            )
        )
    return items


def ist_day_start(now: datetime) -> datetime:
    tz = ZoneInfo(settings.DROP_TZ)
    return now.astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0)


def skills_item(member: Member, since: datetime, upto: datetime, now: datetime) -> list[Item]:
    """At most one 'Skills in demand near you' card, dated the start of today (IST). Role counts, never people counts."""
    at = ist_day_start(now)
    if not (since <= at <= upto):
        return []
    lat, lng = default_centre(member)
    centre = Point(lng, lat, srid=4326)
    from apps.jobs.models import JobCapability

    counts: dict[str, tuple[str, int]] = {}
    qs = JobCapability.objects.filter(
        job__is_open=True,
        job__created_at__gte=now - timedelta(days=settings.PULSE_WINDOW_DAYS),
        job__startup__location__distance_lte=(centre, D(km=settings.STUDENT_MAX_DISTANCE_KM)),
    ).values_list("capability__slug", "capability__name")
    for slug, name in qs:
        counts[slug] = (name, counts.get(slug, (name, 0))[1] + 1)
    top = sorted(counts.items(), key=lambda kv: (-kv[1][1], kv[0]))[:3]
    if not top:
        return []
    return [Item(at, "skills_in_demand", 0, {"skills": [{"slug": s, "name": n, "open_roles": c} for s, (n, c) in top]})]


def pulse(member: Member, cursor: str | None, limit: int, include_seen: bool) -> dict:
    services.require_social(member)
    now = timezone.now()
    since = now - timedelta(days=settings.PULSE_WINDOW_DAYS)
    seen_at = member.pulse_seen_at
    if seen_at and not include_seen:
        since = max(since, seen_at)
    upto = now
    after = None
    if cursor:
        micros, kind, ident = decode_cursor(cursor, 3)
        if not (isinstance(micros, int) and isinstance(kind, str) and isinstance(ident, int)):
            raise ApiError(422, "bad_cursor", "That page marker is not valid. Reload from the top.")
        upto = EPOCH + timedelta(microseconds=micros)
        after = (micros, kind, ident)
    startups = followed_startups(member)
    circle = author_circle(member, startups)
    n = limit + SLACK
    items = (
        post_items(member, since, upto, circle, n)
        + role_items(member, since, upto, startups, now - timedelta(days=settings.PULSE_WINDOW_DAYS))
        + activity_items(member, since, upto)
        + skills_item(member, since, upto, now)
    )
    if after:
        items = [i for i in items if i.key < (after[0], after[1], after[2])]
    items.sort(key=lambda i: i.key, reverse=True)
    page, more = items[:limit], len(items) > limit
    posts = {r["id"]: r for r in services.post_rows(member, _posts_by_id(member, [i.id for i in page if i.kind == "post"]))}
    out = []
    for i in page:
        row = {"kind": i.kind, "key": f"{i.kind}:{i.id}", "created_at": i.at, "seen": bool(seen_at and i.at <= seen_at)}
        if i.kind == "post":
            if i.id not in posts:
                continue
            row["post"] = posts[i.id]
        elif i.kind == "role":
            row["role"] = i.data
        elif i.kind == "skills_in_demand":
            row["skills_in_demand"] = i.data
        else:
            row["activity"] = i.data
        out.append(row)
    nxt = encode_cursor(*page[-1].key) if more and page else None
    return {"items": out, "next_cursor": nxt, "caught_up": nxt is None}


def _posts_by_id(member: Member, ids: list[int]):
    order = {pk: n for n, pk in enumerate(ids)}
    return sorted(visible_posts(member).filter(pk__in=ids).select_related("author"), key=lambda p: order[p.pk])


def mark_seen(member: Member) -> None:
    services.require_social(member)
    member.pulse_seen_at = timezone.now()
    member.save(update_fields=["pulse_seen_at"])
    record("pulse.seen", actor=member)
