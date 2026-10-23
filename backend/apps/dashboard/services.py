"""Partner dashboard (F8): numbers about one organisation's members, never about individuals.

Every function takes the organisation id of the signed-in partner admin and nothing else, so there is no way to ask
about another organisation. A count below DASHBOARD_MIN_COUNT is never returned: it comes back as hidden.
"""

from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db.models import Count, QuerySet
from django.utils import timezone

from apps.accounts.models import Member
from apps.circuits.models import Circuit
from apps.intros.models import IntroRequest
from apps.jobs.models import Application
from apps.matching.models import Capability, MatchResult, Need, Offer
from core.cache import get_cache
from core.permissions import NETWORK_ROLES

CACHE_PREFIX = "dash:"


def count(n: int) -> dict:
    """A count that is safe to show: below the threshold only the fact that it is small is returned."""
    return {"value": n, "hidden": False} if n >= settings.DASHBOARD_MIN_COUNT else {"value": None, "hidden": True}


def org_members(org_id: int) -> QuerySet[Member]:
    return Member.objects.filter(organisation_id=org_id, suspended_at__isnull=True, role__in=NETWORK_ROLES)


def _cached(org_id: int, name: str, build) -> Any:
    """Postgres is the truth; Redis only saves repeating the same aggregate queries for a few minutes."""
    key = f"{CACHE_PREFIX}{org_id}:{name}"
    cache = get_cache()
    hit = cache.get_json(key)
    if hit is None:
        hit = build()
        cache.set_json(key, hit, ttl=settings.DASHBOARD_CACHE_SECONDS)
    return hit


# -- gaps ------------------------------------------------------------------------------------------------------
def gaps(org_id: int) -> list[dict]:
    """Per capability: how many members need it, how many offer it, how many people outside could. Biggest gaps first."""
    return _cached(org_id, "gaps", lambda: _gaps(org_id))


def _gaps(org_id: int) -> list[dict]:
    members = org_members(org_id)
    needed = dict(
        Need.objects.filter(is_active=True, member__in=members)
        .values_list("capability_id")
        .annotate(n=Count("member", distinct=True))
    )
    offered = dict(
        Offer.objects.filter(is_active=True, member__in=members)
        .values_list("capability_id")
        .annotate(n=Count("member", distinct=True))
    )
    outside_pool = Member.objects.filter(
        suspended_at__isnull=True, role__in=NETWORK_ROLES, profile_visibility__in=[Member.Visibility.PUBLIC, Member.Visibility.MEMBERS]
    ).exclude(organisation_id=org_id)  # fmt: skip
    outside = dict(
        Offer.objects.filter(is_active=True, member__in=outside_pool)
        .values_list("capability_id")
        .annotate(n=Count("member", distinct=True))
    )
    caps = {c.pk: c for c in Capability.objects.filter(pk__in=set(needed) | set(offered))}
    rows = []
    for cid, cap in caps.items():
        n, o, x = needed.get(cid, 0), offered.get(cid, 0), outside.get(cid, 0)
        rows.append(
            {
                "capability": cap.slug,
                "name": cap.name,
                "category": cap.category,
                "needed_by": count(n),
                "offered_by": count(o),
                "offered_outside": count(x),
                "is_gap": n >= settings.DASHBOARD_MIN_COUNT and o * 2 < n,
                "_sort": n - o,
            }  # fmt: skip
        )
    rows = [
        r for r in rows if not (r["needed_by"]["hidden"] and r["offered_by"]["hidden"])
    ]  # nothing to learn from two small numbers
    rows.sort(key=lambda r: (-r["_sort"], r["capability"]))
    for r in rows:
        del r["_sort"]
    return rows


# -- heatmap ---------------------------------------------------------------------------------------------------
def heatmap(org_id: int, capability: str | None) -> dict:
    return _cached(org_id, f"heatmap:{capability or '-'}", lambda: _heatmap(org_id, capability))


def _heatmap(org_id: int, capability: str | None) -> dict:
    members = org_members(org_id).filter(location__isnull=False)
    if capability:
        needers = Need.objects.filter(is_active=True, capability__slug=capability).values("member_id")
        members = members.filter(pk__in=needers)  # a subquery, so two members at one point are still two
    size = settings.HEATMAP_CELL_DEGREES
    cells: Counter[tuple[int, int]] = Counter()
    for point in members.values_list("location", flat=True):
        if point is None:
            continue
        cells[(round(point.y / size), round(point.x / size))] += 1
    shown = [
        {"lat": round(r * size, 4), "lng": round(c * size, 4), "count": n}
        for (r, c), n in sorted(cells.items())
        if n >= settings.DASHBOARD_MIN_COUNT  # small cells are left out entirely, not shown as zero
    ]
    return {"cell_degrees": size, "capability": capability, "cells": shown}


# -- network and acceptance --------------------------------------------------------------------------------------
def network(org_id: int) -> dict:
    return _cached(org_id, "network", lambda: _network(org_id))


def _network(org_id: int) -> dict:
    members = org_members(org_id)
    since = timezone.now() - timedelta(days=30)
    intros = IntroRequest.objects.filter(requester__in=members)
    return {
        "members": count(members.count()),
        "new_members_30d": count(members.filter(created_at__gte=since).count()),
        "members_with_matches": count(MatchResult.objects.filter(member__in=members).values("member").distinct().count()),
        "intros_requested": count(intros.count()),
        "intros_accepted": count(intros.filter(status__in=[IntroRequest.Status.ACCEPTED, IntroRequest.Status.COMPLETED]).count()),
        "circuits_completed": count(Circuit.objects.filter(status=Circuit.Status.COMPLETED, legs__giver__in=members).distinct().count()),
        "applications": count(Application.objects.filter(student__in=members).exclude(status=Application.Status.WITHDRAWN).count()),
    }  # fmt: skip


def acceptance(org_id: int) -> dict:
    return _cached(org_id, "acceptance", lambda: _acceptance(org_id))


def _acceptance(org_id: int) -> dict:
    """Intros asked for by the organisation's members, split into local and Bridge by how the two were matched.

    The rate is only shown when both the asks and the accepts are at least the minimum: otherwise it would give away
    a small accepted count.
    """
    members = org_members(org_id)
    bridge_pairs = set(MatchResult.objects.filter(member__in=members, is_bridge=True).values_list("member_id", "candidate_id"))
    asked: dict[str, int] = defaultdict(int)
    accepted: dict[str, int] = defaultdict(int)
    for requester, target, status in IntroRequest.objects.filter(requester__in=members).values_list(
        "requester_id", "target_id", "status"
    ):
        kind = "bridge" if (requester, target) in bridge_pairs else "local"
        asked[kind] += 1
        accepted[kind] += status in (IntroRequest.Status.ACCEPTED, IntroRequest.Status.COMPLETED)
    out = {}
    for kind in ("local", "bridge"):
        show_rate = asked[kind] >= settings.DASHBOARD_MIN_COUNT and accepted[kind] >= settings.DASHBOARD_MIN_COUNT
        out[kind] = {
            "requested": count(asked[kind]), "accepted": count(accepted[kind]),
            "rate_percent": round(100 * accepted[kind] / asked[kind]) if show_rate else None,
        }  # fmt: skip
    return out
