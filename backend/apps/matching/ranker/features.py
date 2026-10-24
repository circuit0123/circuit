"""What a ranker may look at. One fixed, ordered list: the model, the snapshots and the tests all use `FEATURE_NAMES`.

Matching on skills over pedigree is the product (CLAUDE.md), so nothing here knows a college, its tier, a gender, a
religion, a caste, a language, a name, an organisation or an email. `Profile` has no field that could carry them, and
`build` takes nothing else about a person. The fairness check reads college tiers elsewhere (training.py), never here.
"""

import math
from dataclasses import dataclass

from apps.matching import scoring
from apps.matching.scoring import PairScore, Side

# role -> a small integer, so a tree model can split on it. New roles are appended, never renumbered.
ROLE_CODES = {"student": 0, "founder": 1, "mentor": 2, "investor": 3, "partner_admin": 4, "super_admin": 5}

FEATURE_NAMES: tuple[str, ...] = (
    # need / offer fit
    "comp_they_give", "comp_i_give", "complementarity", "embedding_similarity", "shared_capabilities",
    # traits
    "shared_traits", "affinity",
    # place and network
    "distance_km", "mutual_connections", "hops", "path_strength", "trust_path",
    # the candidate's state
    "active_days", "timing", "open_slots", "load_penalty",
    # trust and role
    "viewer_level", "candidate_level", "viewer_role", "candidate_role",
    # other
    "is_bridge", "candidate_response_rate",
)  # fmt: skip

# Words that must never appear in a feature name (a test checks this list against FEATURE_NAMES and the Profile fields).
BANNED_TERMS = (
    "college", "tier", "school", "university", "gender", "sex", "religion", "caste", "language", "name", "organisation",
    "organization", "email", "phone", "age", "minor", "city",
)  # fmt: skip


@dataclass(frozen=True)
class Profile:
    """The only facts about a person the feature builder gets: role, verification level and where they are."""

    role: str
    level: int
    lat: float | None = None
    lng: float | None = None


@dataclass(frozen=True)
class Extras:
    """Network facts loaded once per run: who is connected to whom, and how often each person says yes to an intro."""

    friends: dict[int, frozenset[int]]
    response_rate: dict[int, float]


def _best_similarity(a: Side, b: Side) -> float:
    """Closest need/offer text pair in either direction (0 when no text has been embedded)."""
    best = 0.0
    for mine, theirs in ((a.needs, b.offers), (b.needs, a.offers)):
        for v in mine.values():
            for w in theirs.values():
                if v and w:
                    best = max(best, scoring.cosine(v, w))
    return best


class SimilarityIndex:
    """Closest need/offer text pair between two members, fast: each member's vectors become one normalised matrix, once.

    Same number as `_best_similarity`, which is the plain-Python version kept for the eval set and as the test oracle.
    numpy is imported here, not at the top, so the web process (which never ranks) does not load it.
    """

    def __init__(self, sides: dict[int, Side]) -> None:
        self._sides = sides
        self._mats: dict[int, tuple] = {}

    def _of(self, mid: int) -> tuple:
        if mid not in self._mats:
            import numpy as np

            def matrix(vectors: dict) -> "np.ndarray | None":
                rows = [v for v in vectors.values() if v]
                if not rows:
                    return None
                a = np.array(rows, dtype=float)
                norms = np.linalg.norm(a, axis=1, keepdims=True)
                norms[norms == 0] = 1.0
                return a / norms

            side = self._sides[mid]
            self._mats[mid] = (matrix(side.needs), matrix(side.offers))
        return self._mats[mid]

    def best(self, a: int, b: int) -> float:
        a_needs, a_offers = self._of(a)
        b_needs, b_offers = self._of(b)
        best = 0.0
        for mine, theirs in ((a_needs, b_offers), (b_needs, a_offers)):
            if mine is not None and theirs is not None:
                best = max(best, float((mine @ theirs.T).max()))
        return best


def build(
    me: Side,
    other: Side,
    ps: PairScore,
    me_profile: Profile,
    other_profile: Profile,
    me_id: int,
    other_id: int,
    path_strength: float,
    extras: Extras,
    similarity: float | None = None,
) -> dict[str, float | None]:
    """Features for showing `other` to `me`. Plain numbers (None = unknown), so they store as JSON and replay exactly."""
    distance = None
    if None not in (me_profile.lat, me_profile.lng, other_profile.lat, other_profile.lng):
        distance = round(scoring.haversine_km(me_profile.lat, me_profile.lng, other_profile.lat, other_profile.lng), 3)  # type: ignore[arg-type]
    mine, theirs = extras.friends.get(me_id, frozenset()), extras.friends.get(other_id, frozenset())
    shared_caps = len(set(me.needs) & set(other.offers)) + len(set(me.offers) & set(other.needs))
    out: dict[str, float | None] = {
        "comp_they_give": ps.ab,
        "comp_i_give": ps.ba,
        "complementarity": ps.components["complementarity"],
        "embedding_similarity": round(_best_similarity(me, other) if similarity is None else similarity, 4),
        "shared_capabilities": shared_caps,
        "shared_traits": len(ps.shared_traits),
        "affinity": ps.components["affinity"],
        "distance_km": distance,
        "mutual_connections": len(mine & theirs),
        "hops": ps.hops if ps.hops is not None else 0,  # 0 = no path within two hops
        "path_strength": round(path_strength, 4),
        "trust_path": ps.components["trust_path"],
        "active_days": round(min(other.active_days, 365.0), 2),
        "timing": ps.components["timing"],
        "open_slots": other.open_slots,
        "load_penalty": ps.components["load_penalty"],
        "viewer_level": me_profile.level,
        "candidate_level": other_profile.level,
        "viewer_role": ROLE_CODES.get(me_profile.role, -1),
        "candidate_role": ROLE_CODES.get(other_profile.role, -1),
        "is_bridge": int(ps.is_bridge),
        "candidate_response_rate": extras.response_rate.get(other_id),
    }
    assert tuple(out) == FEATURE_NAMES  # order is part of the contract with trained models
    return out


def to_row(features: dict) -> list[float]:
    """Features in model order, with unknowns as NaN (LightGBM treats NaN as missing)."""
    return [math.nan if features.get(k) is None else float(features[k]) for k in FEATURE_NAMES]
