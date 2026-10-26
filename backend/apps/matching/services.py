"""Matching (F4). `compute_all` is the batch job behind `manage.py compute_matches`; `matches_for` is what the API reads.

Heavy work never runs in a request: users only read the MatchResult rows (and their Redis copy) computed here.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta

import structlog
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from pgvector.django import CosineDistance

from apps.accounts.models import Connection, Member, Role
from apps.events.services import record
from apps.intros.models import IntroRequest
from apps.matching import scoring
from apps.matching.models import Capability, MatchResult, MemberTrait, Need, Offer, Trait
from apps.matching.ranker import features as feat
from apps.matching.ranker.base import Ranker
from apps.matching.ranker.serving import RULE, Serving, load_serving
from apps.matching.scoring import PairScore, Side
from apps.moderation.models import Block
from apps.social import media
from apps.startups.models import StartupMember
from core.cache import get_cache
from core.embeddings import get_embedder
from core.errors import ApiError
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


def load_world(now, simulated: bool = False) -> World:
    """Everyone who can be matched. Simulated members (Stage 4c) live in a world of their own: never mixed with real ones."""
    members = {
        m.pk: m
        for m in Member.objects.filter(suspended_at__isnull=True, is_simulated=simulated)
        .exclude(role__in=NOT_MATCHED_ROLES)
        .select_related(None)
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


def candidate_ids(mid: int, side: Side, offered_by: dict, needed_by: dict, simulated: bool = False) -> set[int]:
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
                    model.objects.filter(is_active=True, member__is_simulated=simulated)
                    .alias(dist=CosineDistance("embedding", vec))
                    .filter(dist__lte=limit)
                    .order_by("dist")
                    .values_list("member_id", flat=True)[: settings.MATCH_KNN]
                )
                found |= set(near_rows)
    found.discard(mid)
    return found


# -- ranker inputs -------------------------------------------------------------------------------------
def load_extras(now) -> feat.Extras:
    """Who is connected to whom and how often each person says yes, for the ranker's features. Loaded once per run."""
    friends: dict[int, set[int]] = defaultdict(set)
    for a, b in Connection.objects.values_list("member_a_id", "member_b_id"):
        friends[a].add(b)
        friends[b].add(a)
    answered: dict[int, int] = defaultdict(int)
    said_yes: dict[int, int] = defaultdict(int)
    since = now - timedelta(days=settings.RANKER_RESPONSE_DAYS)
    for target, status in IntroRequest.objects.filter(created_at__gte=since).values_list("target_id", "status"):
        if status in ("accepted", "completed", "declined"):
            answered[target] += 1
            said_yes[target] += status != "declined"
    rate = {t: round(said_yes[t] / n, 4) for t, n in answered.items() if n >= 3}  # fewer than 3 answers: unknown, not 0
    return feat.Extras({k: frozenset(v) for k, v in friends.items()}, rate)


def profile_of(m: Member) -> feat.Profile:
    return feat.Profile(m.role, m.verification_level, m.location.y if m.location else None, m.location.x if m.location else None)


@dataclass
class Context:
    """Everything `rank_member` needs that is the same for every member in one run."""

    world: World
    offered_by: dict[str, set[int]]
    needed_by: dict[str, set[int]]
    extras: feat.Extras
    serving: Serving
    cap_names: dict[str, str]
    trait_names: dict[str, str]
    similarity: feat.SimilarityIndex
    simulated: bool = False
    appearances: dict[int, int] = field(default_factory=lambda: defaultdict(int))


def make_context(now, simulated: bool = False, serving: Serving | None = None) -> Context:
    world = load_world(now, simulated)
    offered_by: dict[str, set[int]] = defaultdict(set)
    needed_by: dict[str, set[int]] = defaultdict(set)
    for mid, side in world.sides.items():
        for cap in side.offers:
            offered_by[cap].add(mid)
        for cap in side.needs:
            needed_by[cap].add(mid)
    return Context(
        world, offered_by, needed_by, load_extras(now), serving if serving is not None else load_serving(),
        dict(Capability.objects.values_list("slug", "name")), dict(Trait.objects.values_list("slug", "name")),
        feat.SimilarityIndex(world.sides), simulated,
    )  # fmt: skip


@dataclass
class Ranked:
    candidate_id: int
    ps: PairScore
    features: dict
    position: int
    arm: str  # "rule" or "model": which ranker ordered the list
    model_version: str
    model_score: float | None


def _safe_scores(ranker, rows: list[dict], member_id: int) -> list[float] | None:
    try:
        out = ranker.score(rows)
        if len(out) != len(rows):
            raise ValueError("wrong number of scores")
        return out
    except Exception as exc:  # noqa: BLE001 - a model must never break matching: the rule takes over
        log.warning("ranker_failed", version=ranker.version, member_id=member_id, error=type(exc).__name__)
        return None


def rank_member(ctx: Context, mid: int) -> list[Ranked]:
    """Candidates for one member, scored by the rule, then ordered by the rule or by the model that serves this member.

    Who may be shown is decided by the rule and the hard filters alone. A model only changes the order (and so which of
    the eligible ones make the top N), and any model error means the rule's order.
    """
    world, me, side = ctx.world, ctx.world.members[mid], ctx.world.sides[mid]
    hops = neighbours(mid)  # {member: {hops, path, strength}} up to two hops
    scored: list[tuple[int, PairScore, str | None]] = []
    rows: dict[int, dict] = {}
    for cid in sorted(candidate_ids(mid, side, ctx.offered_by, ctx.needed_by, ctx.simulated)):
        other = world.members.get(cid)
        if other is None or ctx.appearances[cid] >= settings.MATCH_MAX_APPEARANCES or not allowed(me, other, world, hops):
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
            rows[cid] = {
                **feat.build(
                    side,
                    world.sides[cid],
                    ps,
                    profile_of(me),
                    profile_of(other),
                    mid,
                    cid,
                    h["strength"] if h else 0.0,
                    ctx.extras,
                    ctx.similarity.best(mid, cid),
                ),
                "rule_score": ps.score,
            }
    ordering = ctx.serving.orders(mid)
    cids = [c for c, _, _ in scored]
    order = None
    scores: dict[int, float] | None = None
    ranker: Ranker = RULE
    if ordering and scored:
        got = _safe_scores(ordering, [rows[c] for c in cids], mid)
        if got is not None:
            ranker, scores = ordering, dict(zip(cids, got))
            order = scores
    if scores is None and ctx.serving.shadow and scored:  # shadow: score and log, but the rule orders
        got = _safe_scores(ctx.serving.shadow, [rows[c] for c in cids], mid)
        if got is not None:
            ranker, scores = ctx.serving.shadow, dict(zip(cids, got))
    top = scoring.rank(scored, settings.MATCH_TOP_N, settings.MATCH_BRIDGE_SHARE, settings.MATCH_MAX_PER_SECTOR, order)
    arm = "model" if order is not None else "rule"
    out = []
    for pos, (cid, ps) in enumerate(top):
        feats = {k: v for k, v in rows[cid].items() if k != "rule_score"}
        out.append(
            Ranked(cid, ps, feats, pos, arm, ranker.version if scores is not None else "", scores[cid] if scores else None)
        )
        ctx.appearances[cid] += 1
    return out


def _store_member(ctx: Context, cache, mid: int, now) -> tuple[int, int, bool]:
    """Rank one member, replace their stored matches and refresh their cached list. Returns (matches, bridge matches, model-ordered)."""
    ranked = rank_member(ctx, mid)
    rows = [
        MatchResult(
            member_id=mid, candidate_id=r.candidate_id, score=r.ps.score, components=r.ps.components, is_bridge=r.ps.is_bridge,
            reason=scoring.reason(r.ps, ctx.cap_names, ctx.trait_names), features=r.features, position=r.position, arm=r.arm,
            model_version=r.model_version, model_score=r.model_score,
        )
        for r in ranked
    ]  # fmt: skip
    with transaction.atomic():
        MatchResult.objects.filter(member_id=mid).delete()
        MatchResult.objects.bulk_create(rows)
    cache.set_json(cache_key(mid), [_cached(r) for r in rows], ttl=settings.MATCH_CACHE_TTL)
    return len(rows), sum(r.is_bridge for r in rows), bool(ranked) and ranked[0].arm == "model"


def compute_for(member_ids) -> dict:
    """Matches for just these members (new sign-ups waiting for their first Daily Drop). Same ranking as the full run; the
    other members' lists are left alone until the next full `compute_matches`. Safe to run again."""
    now = timezone.now()
    backfill_embeddings()  # a new member's needs and offers have no embedding yet
    ctx = make_context(now)
    cache, done = get_cache(), 0
    for mid in sorted(set(member_ids) & set(ctx.world.members)):
        _store_member(ctx, cache, mid, now)
        done += 1
    return {"members": done}


# -- the batch job -----------------------------------------------------------------------------------
def compute_all() -> dict:
    """Recompute every member's matches. Safe to run again: each member's rows are replaced, never added to."""
    started, now = time.monotonic(), timezone.now()
    embedded = backfill_embeddings()
    ctx = make_context(now)
    world = ctx.world
    cache, total, bridges, model_lists = get_cache(), 0, 0, 0
    for mid in sorted(world.members):  # fixed order, so the appearance cap is applied the same way every run
        n, b, model = _store_member(ctx, cache, mid, now)
        total += n
        bridges += b
        model_lists += model
    stale = MatchResult.objects.exclude(member_id__in=world.members)  # suspended or removed since the last run
    for mid in set(stale.values_list("member_id", flat=True)):
        cache.delete(cache_key(mid))
    stale.delete()
    stats = {
        "members": len(world.members), "matches": total, "bridge_matches": bridges, "embedded": embedded,
        "model_lists": model_lists, "seconds": round(time.monotonic() - started, 2),
    }  # fmt: skip
    record("matches.computed", members=stats["members"], matches=stats["matches"], bridge_matches=stats["bridge_matches"])
    log.info("matches_computed", **stats)
    return stats


def _cached(r: MatchResult) -> dict:
    return {"candidate_id": r.candidate_id, "score": r.score, "reason": r.reason, "is_bridge": r.is_bridge}


def strength_for(score: float) -> str | None:
    """Match strength in words. Below the 'good' line there is no label, and the API never shows a low number."""
    if score >= settings.MATCH_STRONG:
        return "strong"
    if score >= settings.MATCH_GOOD:
        return "good"
    return None


# -- the read path -------------------------------------------------------------------------------------
WITHIN_KM_CHOICES = (5, 10, 25, 50)  # coarse on purpose: an exact distance to a person could be narrowed down by moving around


def matches_for(
    member: Member,
    bridge: bool | None = None,
    role: str | None = None,
    verified: bool | None = None,
    capability: str | None = None,
    within_km: int | None = None,
) -> list[dict]:
    """Precomputed matches, best first. Redis first, Postgres if Redis is down or cold.

    Eligibility is checked again here: someone suspended, hidden or blocked since the last run disappears at once.
    Filters (all optional): role, verified (level 2 or 3), capability (one of their offers) and within_km (5, 10, 25 or 50 from my
    location or the city centre). Only a yes/no distance filter is offered: the distance itself is never returned.
    """
    if within_km is not None and within_km not in WITHIN_KM_CHOICES:
        raise ApiError(422, "validation_error", f"within_km must be one of {', '.join(map(str, WITHIN_KM_CHOICES))}")
    cache = get_cache()
    rows = cache.get_json(cache_key(member.pk))
    if rows is None:
        rows = [_cached(r) for r in MatchResult.objects.filter(member=member).order_by("position", "-score", "candidate_id")]
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
    if role:
        people = {k: m for k, m in people.items() if m.role == role}
    if verified:
        people = {k: m for k, m in people.items() if m.verification_level >= 2}
    if within_km is not None:
        from django.contrib.gis.geos import Point
        from django.contrib.gis.measure import D

        from apps.startups.services import default_centre

        lat, lng = default_centre(member)
        near = Member.objects.filter(
            pk__in=list(people), location__distance_lte=(Point(lng, lat, srid=4326), D(km=within_km))
        ).values_list("pk", flat=True)
        people = {k: m for k, m in people.items() if k in set(near)}
    offers: dict[int, list[tuple[str, str]]] = {}
    for mid, slug, name in (
        Offer.objects.filter(member_id__in=list(people))
        .order_by("id")
        .values_list("member_id", "capability__slug", "capability__name")
    ):
        offers.setdefault(mid, []).append((slug, name))
    if capability:
        people = {k: m for k, m in people.items() if any(slug == capability for slug, _ in offers.get(k, []))}
    sectors = member_sectors(people)
    media.prime_photos(people.values())
    out = []
    for r in rows:
        p = people.get(r["candidate_id"])
        if p is None or (bridge is not None and r["is_bridge"] != bridge):
            continue
        out.append(
            {
                "candidate_id": p.pk, "display_name": p.display_name, "role": p.role, "verification_level": p.verification_level,
                "city": p.city, "sector": sectors.get(p.pk), "score": r["score"], "strength": strength_for(r["score"]),
                "reason": r["reason"], "is_bridge": r["is_bridge"], "photo": media.photo_of(p),
                "headline": (p.bio or "").strip()[:140], "capabilities": [name for _, name in offers.get(p.pk, [])[:3]],
            }
        )  # fmt: skip
    return out
