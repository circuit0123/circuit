"""Matching (F4). `compute_all` is the batch job behind `manage.py compute_matches`; `matches_for` is what the API reads.

Heavy work never runs in a request: users only read the MatchResult rows (and their Redis copy) computed here.
"""

import time
from collections import defaultdict
from dataclasses import dataclass

import structlog
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from pgvector.django import CosineDistance

from apps.accounts.models import Member, Role
from apps.events.services import record
from apps.matching import scoring
from apps.matching.models import Capability, MatchResult, MemberTrait, Need, Offer, Trait
from apps.matching.scoring import PairScore, Side
from apps.moderation.models import Block
from apps.startups.models import StartupMember
from core.cache import get_cache
from core.embeddings import get_embedder
from core.graph import neighbours

log = structlog.get_logger("matching")
NOT_MATCHED_ROLES = (Role.PARTNER_ADMIN, Role.SUPER_ADMIN)  # they run dashboards and moderation, not exchanges
EMBED_BATCH = 64


def cache_key(member_id: int) -> str:
    return f"matches:{member_id}"


# -- inputs ----------------------------------------------------------------------------------------
def backfill_embeddings() -> int:
    """Needs and offers get their embedding here, not in the request that saved them."""
    done = 0
    embedder = get_embedder()
    for model in (Need, Offer):
        rows: list = list(model.objects.filter(embedding__isnull=True).select_related("capability"))
        for i in range(0, len(rows), EMBED_BATCH):
            batch = rows[i : i + EMBED_BATCH]
            for row, vec in zip(batch, embedder.embed([r.description or r.capability.name for r in batch])):
                row.embedding = vec
            model.objects.bulk_update(batch, ["embedding"])
            done += len(batch)
    return done


def member_sectors(member_ids) -> dict[int, str]:
    """Sector of the startup a member belongs to (or runs). People without one (students, mentors) have none."""
    out: dict[int, str] = {}
    for mid, sector in (
        StartupMember.objects.filter(member_id__in=member_ids).order_by("startup_id").values_list("member_id", "startup__sector")
    ):
        if sector:
            out.setdefault(mid, sector)
    return out


def _vec(embedding) -> list[float] | None:
    return None if embedding is None else [float(x) for x in embedding]


@dataclass
class World:
    members: dict[int, Member]
    sides: dict[int, Side]
    blocked: set[tuple[int, int]]


def load_world(now) -> World:
    members = {
        m.pk: m for m in Member.objects.filter(suspended_at__isnull=True).exclude(role__in=NOT_MATCHED_ROLES).select_related(None)
    }
    needs: dict[int, dict[str, list[float] | None]] = defaultdict(dict)
    offers: dict[int, dict[str, list[float] | None]] = defaultdict(dict)
    newest: dict[int, object] = {}
    for model, bucket in ((Need, needs), (Offer, offers)):
        for mid, slug, emb, created in model.objects.filter(is_active=True, member_id__in=members).values_list(
            "member_id", "capability__slug", "embedding", "created_at"
        ):
            bucket[mid][slug] = _vec(emb)
            if mid not in newest or created > newest[mid]:  # type: ignore[operator]
                newest[mid] = created
    traits: dict[int, set[str]] = defaultdict(set)
    for mid, slug in MemberTrait.objects.filter(member_id__in=members).values_list("member_id", "trait__slug"):
        traits[mid].add(slug)
    sectors = member_sectors(members)
    sides = {
        mid: Side(
            needs=needs.get(mid, {}), offers=offers.get(mid, {}), traits=frozenset(traits.get(mid, ())), sector=sectors.get(mid),
            open_slots=m.open_intro_slots,
            active_days=(now - newest[mid]).total_seconds() / 86400 if mid in newest else 9999.0,  # type: ignore[operator]
        )
        for mid, m in members.items()
    }  # fmt: skip
    blocked = set()
    for a, b in Block.objects.values_list("blocker_id", "blocked_id"):
        blocked |= {(a, b), (b, a)}
    return World(members, sides, blocked)


# -- candidates --------------------------------------------------------------------------------------
def near(a: Member, b: Member) -> bool:
    """Students' hard distance filter. Without two locations, fall back to the same city; with neither, not near."""
    if a.location and b.location:
        return scoring.haversine_km(a.location.y, a.location.x, b.location.y, b.location.x) <= settings.STUDENT_MAX_DISTANCE_KM
    return bool(a.city) and a.city.strip().lower() == b.city.strip().lower()


def allowed(a: Member, b: Member, world: World, hops: dict) -> bool:
    """May `b` be recommended to `a`? Blocks, hidden profiles, full intro slots, minors and distance all say no."""
    if a.pk == b.pk or (a.pk, b.pk) in world.blocked:
        return False
    if b.profile_visibility == Member.Visibility.HIDDEN or b.open_intro_slots <= 0:
        return False
    if (a.is_minor or b.is_minor) and not (
        (a.organisation_id and a.organisation_id == b.organisation_id) or hops.get(b.pk, {}).get("hops") == 1
    ):
        return False  # under-18s: no matches with strangers
    return not (Role.STUDENT in (a.role, b.role) and not near(a, b))


def candidate_ids(mid: int, side: Side, offered_by: dict, needed_by: dict) -> set[int]:
    """Everyone whose offers meet my needs or whose needs meet my offers: exact capability first, then similar text."""
    found: set[int] = set()
    for cap in side.needs:
        found |= offered_by.get(cap, set())
    for cap in side.offers:
        found |= needed_by.get(cap, set())
    limit = 1 - settings.MATCH_MIN_SIMILARITY
    for mine, model in ((side.needs, Offer), (side.offers, Need)):
        for vec in mine.values():
            if vec:
                near_rows = (
                    model.objects.filter(is_active=True)
                    .alias(dist=CosineDistance("embedding", vec))
                    .filter(dist__lte=limit)
                    .order_by("dist")
                    .values_list("member_id", flat=True)[: settings.MATCH_KNN]
                )
                found |= set(near_rows)
    found.discard(mid)
    return found


# -- the batch job -----------------------------------------------------------------------------------
def compute_all() -> dict:
    """Recompute every member's matches. Safe to run again: each member's rows are replaced, never added to."""
    started, now = time.monotonic(), timezone.now()
    embedded = backfill_embeddings()
    world = load_world(now)
    cap_names = dict(Capability.objects.values_list("slug", "name"))
    trait_names = dict(Trait.objects.values_list("slug", "name"))
    offered_by: dict[str, set[int]] = defaultdict(set)
    needed_by: dict[str, set[int]] = defaultdict(set)
    for mid, side in world.sides.items():
        for cap in side.offers:
            offered_by[cap].add(mid)
        for cap in side.needs:
            needed_by[cap].add(mid)
    appearances: dict[int, int] = defaultdict(int)
    cache, total, bridges = get_cache(), 0, 0
    for mid in sorted(world.members):  # fixed order, so the appearance cap is applied the same way every run
        me, side = world.members[mid], world.sides[mid]
        hops = neighbours(mid)  # {member: {hops, path, strength}} up to two hops
        scored: list[tuple[int, PairScore, str | None]] = []
        for cid in sorted(candidate_ids(mid, side, offered_by, needed_by)):
            other = world.members.get(cid)
            if other is None or appearances[cid] >= settings.MATCH_MAX_APPEARANCES or not allowed(me, other, world, hops):
                continue
            h = hops.get(cid)
            ps = scoring.score_pair(
                side,
                world.sides[cid],
                (h["hops"], h["strength"]) if h else None,
                settings.MATCH_WEIGHTS,
                settings.MATCH_MIN_SIMILARITY,
            )
            if ps.components["complementarity"] >= settings.MATCH_MIN_COMPLEMENTARITY:
                scored.append((cid, ps, world.sides[cid].sector))
        top = scoring.rank(scored, settings.MATCH_TOP_N, settings.MATCH_BRIDGE_SHARE, settings.MATCH_MAX_PER_SECTOR)
        rows = [
            MatchResult(
                member_id=mid, candidate_id=cid, score=ps.score, components=ps.components, is_bridge=ps.is_bridge,
                reason=scoring.reason(ps, cap_names, trait_names),
            )
            for cid, ps in top
        ]  # fmt: skip
        with transaction.atomic():
            MatchResult.objects.filter(member_id=mid).delete()
            MatchResult.objects.bulk_create(rows)
        for cid, _ in top:
            appearances[cid] += 1
        cache.set_json(cache_key(mid), [_cached(r) for r in rows], ttl=settings.MATCH_CACHE_TTL)
        total += len(rows)
        bridges += sum(r.is_bridge for r in rows)
    stale = MatchResult.objects.exclude(member_id__in=world.members)  # suspended or removed since the last run
    for mid in set(stale.values_list("member_id", flat=True)):
        cache.delete(cache_key(mid))
    stale.delete()
    stats = {
        "members": len(world.members), "matches": total, "bridge_matches": bridges, "embedded": embedded,
        "seconds": round(time.monotonic() - started, 2),
    }  # fmt: skip
    record("matches.computed", members=stats["members"], matches=stats["matches"], bridge_matches=stats["bridge_matches"])
    log.info("matches_computed", **stats)
    return stats


def _cached(r: MatchResult) -> dict:
    return {"candidate_id": r.candidate_id, "score": r.score, "reason": r.reason, "is_bridge": r.is_bridge}


# -- the read path -------------------------------------------------------------------------------------
def matches_for(member: Member, bridge: bool | None = None) -> list[dict]:
    """Precomputed matches, best first. Redis first, Postgres if Redis is down or cold.

    Eligibility is checked again here: someone suspended, hidden or blocked since the last run disappears at once.
    """
    cache = get_cache()
    rows = cache.get_json(cache_key(member.pk))
    if rows is None:
        rows = [_cached(r) for r in MatchResult.objects.filter(member=member).order_by("-score", "candidate_id")]
        cache.set_json(cache_key(member.pk), rows, ttl=settings.MATCH_CACHE_TTL)
    ids = [r["candidate_id"] for r in rows]
    gone = set(Block.objects.filter(blocker=member).values_list("blocked_id", flat=True))
    gone |= set(Block.objects.filter(blocked=member).values_list("blocker_id", flat=True))
    people = {
        m.pk: m
        for m in Member.objects.filter(pk__in=ids, suspended_at__isnull=True)
        .exclude(profile_visibility=Member.Visibility.HIDDEN)
        .exclude(pk__in=gone)
    }
    sectors = member_sectors(people)
    out = []
    for r in rows:
        p = people.get(r["candidate_id"])
        if p is None or (bridge is not None and r["is_bridge"] != bridge):
            continue
        out.append(
            {
                "candidate_id": p.pk, "display_name": p.display_name, "role": p.role, "verification_level": p.verification_level,
                "city": p.city, "sector": sectors.get(p.pk), "score_percent": round(r["score"] * 100),
                "reason": r["reason"], "is_bridge": r["is_bridge"],
            }
        )  # fmt: skip
    return out
