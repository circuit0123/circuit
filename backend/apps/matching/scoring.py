"""Pure scoring functions: no database, no network, so they are easy to test on hand-built examples."""

import math
from dataclasses import dataclass, field


def skill_match(skills: dict[int, int], required: set[int], optional: set[int] | None = None) -> float:
    """How well a student's skills cover a job or startup, 0..1.

    `skills` maps capability id -> level (1-3). Required capabilities carry 80% of the score and optional ones 20%;
    a level-1 skill counts 0.6, level 2 counts 0.8, level 3 counts 1.0. With nothing required, only optional counts.
    The college is never an input: matching is on skills and proof of work.
    """
    optional = optional or set()

    def coverage(wanted: set[int]) -> float:
        if not wanted:
            return 0.0
        return sum(0.4 + 0.2 * min(skills[c], 3) for c in wanted if c in skills) / len(wanted)

    if required and optional:
        return round(0.8 * coverage(required) + 0.2 * coverage(optional), 4)
    if required:
        return round(coverage(required), 4)
    return round(coverage(optional), 4)


# -- member-to-member matching (F4) ---------------------------------------------------------------------------
# Everything below is pure: profiles in, numbers and a sentence out. The database work is in services.py.
Vector = list[float] | None
COMPLEMENT_ONE_WAY = 0.6  # a match where only one person can help the other still counts, but less than a two-way one
PARTIAL_MATCH = 0.8  # a similar-but-not-identical capability is worth at most this much of an exact match
MAX_REASON = 300


@dataclass(frozen=True)
class Side:
    """One member as the matcher sees them. Capabilities are slugs; vectors come from the need/offer text."""

    needs: dict[str, Vector] = field(default_factory=dict)
    offers: dict[str, Vector] = field(default_factory=dict)
    traits: frozenset[str] = frozenset()
    sector: str | None = None  # from the startup they run or belong to; None for students, mentors and so on
    open_slots: int = 2
    active_days: float = 0.0  # days since their newest active need or offer


@dataclass(frozen=True)
class PairScore:
    score: float
    components: dict[str, float]
    is_bridge: bool
    they_give: tuple[str, str] | None  # (my need, their offer) that matched best
    i_give: tuple[str, str] | None
    shared_traits: tuple[str, ...]
    hops: int | None
    ab: float = 0.0  # how well their offers cover my needs, 0..1 (kept for the ranker's features; not part of the score itself)
    ba: float = 0.0  # how well my offers cover their needs


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def one_way(needs: dict[str, Vector], offers: dict[str, Vector], min_similarity: float) -> tuple[float, tuple[str, str] | None]:
    """How well `offers` cover `needs`: the mean over the needs of their best match, plus the best (need, offer) pair.

    Same capability = 1.0. Otherwise the closest offer by text embedding, if it is at least `min_similarity`,
    worth `PARTIAL_MATCH` times the similarity. A need nobody covers scores 0.
    """
    if not needs:
        return 0.0, None
    total = 0.0
    best: tuple[float, tuple[str, str] | None] = (0.0, None)
    for cap in sorted(needs):
        if cap in offers:
            value, pair = 1.0, (cap, cap)
        else:
            value, pair = 0.0, None
            vec = needs[cap]
            for ocap in sorted(offers):
                ovec = offers[ocap]
                sim = cosine(vec, ovec) if vec and ovec else 0.0
                if sim >= min_similarity and PARTIAL_MATCH * sim > value:
                    value, pair = PARTIAL_MATCH * sim, (cap, ocap)
        total += value
        if value > best[0]:
            best = (value, pair)
    return total / len(needs), best[1]


def complementarity(score_ab: float, score_ba: float) -> float:
    """Both directions: two people who can help each other beat a one-sided match."""
    hi, lo = max(score_ab, score_ba), min(score_ab, score_ba)
    return COMPLEMENT_ONE_WAY * hi + (1 - COMPLEMENT_ONE_WAY) * lo


def affinity(a: frozenset[str], b: frozenset[str]) -> float:
    """Shared traits (Jaccard): 0 with nothing in common, 1 for identical sets."""
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def trust_path(hops: int | None, strength: float) -> float:
    """A direct connection counts for most, a friend-of-a-friend for about half as much, strangers for nothing."""
    if hops == 1:
        return 0.5 + 0.5 * strength
    if hops == 2:
        return 0.5 * (0.5 + 0.5 * strength)
    return 0.0


def timing(active_days: float) -> float:
    """Fresh needs and offers beat stale ones; after 90 days they count for nothing."""
    return max(0.0, 1.0 - active_days / 90)


def load_penalty(open_slots: int) -> float:
    """Candidates with few free intro slots are ranked lower; 3 or more free slots carry no penalty."""
    return min(1.0, max(0.0, 1.0 - open_slots / 3))


def is_bridge(sector_a: str | None, sector_b: str | None, comp: float) -> bool:
    """A Bridge match connects two different, known sectors and rests on a real need/offer fit."""
    return bool(sector_a and sector_b and sector_a != sector_b and comp > 0)


def score_pair(
    me: Side,
    other: Side,
    hops: tuple[int, float] | None,
    weights: dict[str, float],
    min_similarity: float,
) -> PairScore:
    """Score `other` as a match for `me`. Timing and load describe `other`, the person being recommended."""
    ab, they_give = one_way(me.needs, other.offers, min_similarity)
    ba, i_give = one_way(other.needs, me.offers, min_similarity)
    comp = complementarity(ab, ba)
    aff = affinity(me.traits, other.traits)
    trust = trust_path(hops[0], hops[1]) if hops else 0.0
    comps = {
        "complementarity": comp, "affinity": aff, "trust_path": trust, "timing": timing(other.active_days),
        "load_penalty": load_penalty(other.open_slots),
    }  # fmt: skip
    raw = sum(weights[k] * v for k, v in comps.items() if k != "load_penalty") - weights["load_penalty"] * comps["load_penalty"]
    return PairScore(
        score=round(min(1.0, max(0.0, raw)), 4),
        components={k: round(v, 4) for k, v in comps.items()},
        is_bridge=is_bridge(me.sector, other.sector, comp),
        they_give=they_give if ab > 0 else None,
        i_give=i_give if ba > 0 else None,
        shared_traits=tuple(sorted(me.traits & other.traits)),
        hops=hops[0] if hops else None,
        ab=round(ab, 4),
        ba=round(ba, 4),
    )


def reason(p: PairScore, cap_names: dict[str, str], trait_names: dict[str, str]) -> str:
    """One plain sentence on why these two fit. Never contains a name, email or other personal detail."""

    def cap(slug: str) -> str:
        return cap_names.get(slug, slug).lower()

    if p.they_give and p.i_give:
        head = f"You can help each other: they offer {cap(p.they_give[1])} and you offer {cap(p.i_give[1])}."
    elif p.they_give:
        head = f"They offer {cap(p.they_give[1])}, which you need."
    elif p.i_give:
        head = f"You offer {cap(p.i_give[1])}, which they need."
    else:
        head = "A possible fit."
    tail = []
    if p.shared_traits:
        shown = [trait_names.get(t, t).lower() for t in p.shared_traits[:3]]
        tail.append("You both deal with " + ", ".join(shown) + ".")
    if p.hops == 1:
        tail.append("You are already connected.")
    elif p.hops == 2:
        tail.append("You have a mutual connection.")
    return " ".join([head, *tail])[:MAX_REASON]


def rank(
    scored: list[tuple[int, PairScore, str | None]],
    limit: int,
    bridge_share: float,
    max_per_sector: int,
    order: dict[int, float] | None = None,
) -> list[tuple[int, PairScore]]:
    """Pick up to `limit` matches, best first. `scored` holds (candidate id, score, candidate sector).

    `order` (candidate id -> number) replaces the score as the sort key, which is how a learned ranker reorders the list.
    Diversity and Bridge share still apply, and who is *allowed* in a list never depends on it.

    Diversity: no more than `max_per_sector` from one sector. Bridge share: about `bridge_share` of the list is
    Bridge matches when enough exist, and if there are too few the rest of the list is filled with the next best.
    """

    def key(t: tuple) -> float:  # (candidate id, score, ...)
        return order.get(t[0], t[1].score) if order is not None else t[1].score

    pool = sorted(scored, key=lambda t: (-key(t), t[0]))
    taken_per_sector: dict[str, int] = {}
    diverse = []
    for cid, ps, sector in pool:
        if sector:
            if taken_per_sector.get(sector, 0) >= max_per_sector:
                continue
            taken_per_sector[sector] = taken_per_sector.get(sector, 0) + 1
        diverse.append((cid, ps))
    bridge_slots = math.ceil(limit * bridge_share)
    bridges = [t for t in diverse if t[1].is_bridge][:bridge_slots]
    chosen = {cid for cid, _ in bridges}
    locals_ = [t for t in diverse if t[0] not in chosen and not t[1].is_bridge][: limit - len(bridges)]
    chosen |= {cid for cid, _ in locals_}
    picked = bridges + locals_
    if len(picked) < limit:  # too few local matches: let more bridge matches in
        picked += [t for t in diverse if t[0] not in chosen][: limit - len(picked)]
    return sorted(picked, key=lambda t: (-key(t), t[0]))


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))
