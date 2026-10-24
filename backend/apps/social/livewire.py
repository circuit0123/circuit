"""The Live wire (F16): the most relevant things that happened in my world in the last 24 hours.

Five kinds: shipped (a build log), hiring (a new role), needs (someone asked for help), joined (someone joined my
organisation) and circuit_closed. Up to 12, ranked by how much each matters to me: shared capabilities, mutual
connections, distance. Every source uses the rules the rest of the social app uses (visible_posts, blocks, minors), and
nothing here returns a count of views or reactions.
"""

import math
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.accounts.models import Member
from apps.events.models import Event
from apps.events.services import record
from apps.matching.models import Need, Offer
from apps.social import pulse, services
from apps.social.models import UpdateView
from apps.social.relations import blocked_ids, connected_ids, org_mate_ids, visible_posts
from apps.social.schemas import author
from core.errors import NotFound

MAX_ITEMS = 12
PER_KIND = {"needs": 3, "joined": 2}  # a mix, not a wall of one kind; every other kind may fill up to 6
DEFAULT_PER_KIND = 6
Candidate = dict[str, Any]


def _km(a: Member, b: Member | None) -> float | None:
    """Straight-line distance in km between two members who have a location."""
    if b is None or a.location is None or b.location is None:
        return None
    (lat1, lng1), (lat2, lng2) = (a.location.y, a.location.x), (b.location.y, b.location.x)
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def _mine(member: Member) -> dict[str, dict[str, str]]:
    """My capabilities by slug (to name): what I need, what I offer, and what I can do."""
    from apps.matching.models import MemberSkill

    def names(qs) -> dict[str, str]:
        return {slug: name for slug, name in qs.values_list("capability__slug", "capability__name")}

    return {
        "needs": names(Need.objects.filter(member=member, is_active=True)),
        "offers": names(Offer.objects.filter(member=member, is_active=True)),
        "skills": names(MemberSkill.objects.filter(member=member)),
    }


def _reason(cand: Candidate, mine: dict[str, dict[str, str]], friends: set[int], me: Member) -> tuple[float, str]:
    """(relevance, one line on why this matters to me). The line never names anyone I could not already see."""
    parts: list[str] = []
    score = 0.0
    can_do = {**mine["offers"], **mine["skills"]}
    shared_do = [s for s in cand["caps"] if s in can_do]
    shared_need = [s for s in cand["caps"] if s in mine["needs"]]
    names = {**mine["needs"], **can_do}
    if cand["kind"] == "needs" and shared_do:
        parts.append(f"You offer {names[shared_do[0]]}, which they need")
    elif cand["kind"] == "needs" and shared_need:
        parts.append(f"You both need {names[shared_need[0]]}")
    elif shared_need:
        parts.append(f"Works with {names[shared_need[0]]}, which you need")
    elif shared_do:
        parts.append(
            f"Matches your skills in {names[shared_do[0]]}"
            if cand["kind"] == "hiring"
            else f"You both work with {names[shared_do[0]]}"
        )
    score += 3 * min(len(set(shared_do) | set(shared_need)), 2)
    actor = cand.get("member")
    if actor is not None:
        mutuals = len((connected_ids(actor.pk) & friends) - {me.pk, actor.pk})
        if mutuals:
            parts.append(f"{mutuals} mutual connection{'s' if mutuals > 1 else ''}")
        score += min(mutuals, 3)
    km = cand.get("km")
    if km is None:
        km = _km(me, actor)
    if km is not None and km <= 50:
        parts.append("under 1 km away" if km < 1 else f"{km:.0f} km away")
        score += 1 if km <= 5 else 0.5 if km <= 25 else 0
    return score, " · ".join(parts) or (actor.city if actor is not None and actor.city else "In your network")


def _image(row: dict) -> dict | None:
    m = row["media"][0] if row["media"] else None
    return {"w480": m["w480"], "w1440": m["w1440"], "alt": m["alt_text"]} if m else None


def _shipped(member: Member, since, circle: set[int]) -> list[Candidate]:
    posts = list(
        visible_posts(member)
        .filter(author_id__in=circle, created_at__gte=since)
        .select_related("author")
        .order_by("-created_at", "-id")[:60]
    )
    newest: dict[int, Any] = {}
    for p in posts:
        newest.setdefault(p.author_id, p)  # one node per person: their newest build log
    rows = {r["id"]: r for r in services.post_rows(member, newest.values())}
    out = []
    for p in newest.values():
        row = rows[p.pk]
        body = " ".join(p.body.split())
        out.append(
            {
                "key": f"post:{p.pk}", "kind": "shipped", "at": p.created_at, "member": p.author,
                "headline": body if len(body) <= 140 else body[:137].rstrip() + "...",
                "image": _image(row), "caps": [c["slug"] for c in row["capabilities"]],
                "action": {"kind": "intro", "target_id": p.author_id},
            }
        )  # fmt: skip
    return out


def _hiring(member: Member, since) -> list[Candidate]:
    startups = pulse.followed_startups(member)
    out = []
    for i in pulse.role_items(member, since, timezone.now(), startups, since):
        r = i.data
        out.append(
            {
                "key": f"job:{r['id']}", "kind": "hiring", "at": i.at, "member": None,
                "startup": {"id": r["startup_id"], "name": r["startup_name"]},
                "headline": f"{r['startup_name']} is hiring: {r['title']}", "image": None,
                "caps": [c["slug"] for c in r["capabilities"]], "km": r.get("distance_km"),
                "action": {"kind": "view_role", "target_id": r["id"]},
            }
        )  # fmt: skip
    return out


def _needs(member: Member, since, circle: set[int]) -> list[Candidate]:
    rows = (
        Need.objects.filter(member_id__in=circle, is_active=True, created_at__gte=since, member__suspended_at__isnull=True)
        .select_related("member", "capability")
        .order_by("-created_at", "-id")[:60]
    )
    newest: dict[int, Need] = {}
    for n in rows:
        if n.member.is_minor or n.member.role not in services.SOCIAL_ROLES:
            continue
        newest.setdefault(n.member_id, n)
    out = []
    for n in newest.values():
        text = f"Needs help with {n.capability.name}"
        if n.description.strip():
            text += f": {n.description.strip()}"
        out.append(
            {
                "key": f"need:{n.pk}", "kind": "needs", "at": n.created_at, "member": n.member,
                "headline": text if len(text) <= 140 else text[:137].rstrip() + "...", "image": None, "caps": [n.capability.slug],
                "action": {"kind": "intro", "target_id": n.member_id},
            }
        )  # fmt: skip
    return out


def _joined(member: Member, since, circle: set[int]) -> list[Candidate]:
    org = member.organisation
    if org is None:
        return []
    mates = org_mate_ids(member)
    events = Event.objects.filter(type="org.joined", created_at__gte=since, actor_id__in=mates & circle).order_by("-created_at")
    people = {m.pk: m for m in Member.objects.filter(pk__in=[e.actor_id for e in events], is_minor=False)}
    out, seen = [], set()
    for e in events:
        m = people.get(e.actor_id or 0)
        if m is None or m.pk in seen or m.organisation_id != member.organisation_id:
            continue
        seen.add(m.pk)
        out.append(
            {
                "key": f"joined:{e.pk}", "kind": "joined", "at": e.created_at, "member": m,
                "headline": f"Joined {org.name}", "image": None, "caps": [],
                "action": {"kind": "intro", "target_id": m.pk},
            }
        )  # fmt: skip
    return out


def _circuits(member: Member, since, friends: set[int]) -> list[Candidate]:
    out = []
    for i in pulse.activity_items(member, since, timezone.now()):
        if i.data["type"] != "circuit_completed":
            continue
        others = [pk for pk in i.data["members"] if pk in friends and pk != member.pk]
        if not others:
            continue
        who = Member.objects.get(pk=others[0])
        extra = len(i.data["members"]) - 1
        out.append(
            {
                "key": f"circuit:{i.id}", "kind": "circuit_closed", "at": i.at, "member": who,
                "headline": f"{who.display_name} closed a circuit with {extra} other{'s' if extra != 1 else ''}",
                "image": None, "caps": [], "action": {"kind": "reply", "target_id": who.pk},
            }
        )  # fmt: skip
    return out


def live_wire(member: Member) -> list[dict]:
    services.require_social(member)
    now = timezone.now()
    since = now - timedelta(hours=settings.TODAY_WINDOW_HOURS)
    circle = pulse.author_circle(member)
    friends = connected_ids(member.pk) - blocked_ids(member.pk)
    candidates = (
        _shipped(member, since, circle)
        + _hiring(member, since)
        + _needs(member, since, circle)
        + (_joined(member, since, circle) if member.organisation_id else [])
        + _circuits(member, since, friends)
    )
    mine = _mine(member)
    for c in candidates:
        c["score"], c["reason"] = _reason(c, mine, friends, member)
    viewed = set(UpdateView.objects.filter(viewer=member, key__in=[c["key"] for c in candidates]).values_list("key", flat=True))
    candidates.sort(key=lambda c: (c["key"] in viewed, -c["score"], -c["at"].timestamp()))
    picked: list[Candidate] = []
    per_kind: dict[str, int] = {}
    for c in candidates:
        if per_kind.get(c["kind"], 0) < PER_KIND.get(c["kind"], DEFAULT_PER_KIND):
            per_kind[c["kind"]] = per_kind.get(c["kind"], 0) + 1
            picked.append(c)
    return [
        {
            "key": c["key"], "kind": c["kind"], "actor": author(c["member"]) if c["member"] else None,
            "startup": c.get("startup"), "image": c["image"], "headline": c["headline"], "reason": c["reason"],
            "action": c["action"], "created_at": c["at"], "seen": c["key"] in viewed,
        }
        for c in picked[:MAX_ITEMS]
    ]  # fmt: skip


def mark_viewed(member: Member, key: str) -> None:
    """Called when an update is opened. An update that is not on my wire is a 404, so keys cannot be probed."""
    if key not in {u["key"] for u in live_wire(member)}:
        raise NotFound()
    UpdateView.objects.update_or_create(viewer=member, key=key, defaults={"date": pulse.ist_day_start(timezone.now()).date()})
    record("livewire.viewed", actor=member, target_type="update", key=key)
