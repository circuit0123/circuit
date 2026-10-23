"""Eval set for matching: do our scores agree with human judgement? Pure scoring on hand-written profiles, no database.

tests/eval/pairs.json lists preference pairs ("for this member, A is a better match than B"). Agreement is the share of
pairs where the score puts A above B. A scoring change must not lower it (CLAUDE.md), so `eval_matching` compares
against tests/eval/baseline.json.
"""

import json
from pathlib import Path

from django.conf import settings

from apps.matching import scoring
from apps.matching.scoring import Side, Vector
from core.embeddings import get_embedder

EVAL_DIR = Path(settings.BASE_DIR) / "tests" / "eval"


def load_pairs(path: Path | None = None) -> dict:
    return json.loads((path or EVAL_DIR / "pairs.json").read_text())


def build_sides(profiles: dict) -> dict[str, Side]:
    """Turn the JSON profiles into Sides. Need/offer texts are embedded in one batch, like compute_matches does."""
    texts = [t for p in profiles.values() for kind in ("needs", "offers") for t in p[kind].values()]
    vecs = iter(get_embedder().embed(texts)) if texts else iter(())
    sides = {}
    for key, p in profiles.items():
        needs: dict[str, Vector] = {cap: next(vecs) for cap in p["needs"]}  # dicts keep order, so this matches `texts`
        offers: dict[str, Vector] = {cap: next(vecs) for cap in p["offers"]}
        sides[key] = Side(
            needs=needs, offers=offers, traits=frozenset(p["traits"]), sector=p["sector"], open_slots=p["open_slots"],
            active_days=p["active_days"],
        )  # fmt: skip
    return sides


def evaluate(data: dict) -> tuple[float, list[dict]]:
    """Returns (agreement 0..1, the pairs we disagree with)."""
    sides = build_sides(data["profiles"])
    links = {k: tuple(v) for k, v in data.get("links", {}).items()}

    def score(member: str, other: str) -> float:
        hops = links.get(f"{member}|{other}") or links.get(f"{other}|{member}")
        return scoring.score_pair(sides[member], sides[other], hops, settings.MATCH_WEIGHTS, settings.MATCH_MIN_SIMILARITY).score

    misses = []
    for pair in data["pairs"]:
        better, worse = score(pair["member"], pair["better"]), score(pair["member"], pair["worse"])
        if not better > worse:  # a tie is a disagreement: the order would be arbitrary
            misses.append({**pair, "better_score": better, "worse_score": worse})
    total = len(data["pairs"])
    return ((total - len(misses)) / total if total else 1.0), misses
