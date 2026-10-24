"""Training data, training, offline evaluation and the fairness check for the learned ranker.

Labels (CLAUDE.md "Matching ML"): 0 shown and nothing happened, 1 intro requested, 2 intro accepted, 3 met and rated
helpful (4-5 stars). An intro is credited to the latest snapshot of the same pair shown up to RANKER_LABEL_WINDOW_DAYS
before it. Intro events carry only the intro's id, so the pair and outcome are read from IntroRequest, which the events
mirror.

Under-18s are never in the training data (their snapshots are not even written). In production, simulated people are left
out of the set altogether. lightgbm and numpy are imported inside functions: the web process never loads them.
"""

import bisect
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings

from apps.intros.models import IntroRequest
from apps.matching import evaluation, scoring
from apps.matching.models import FeatureSnapshot
from apps.matching.ranker import features as feat

TIERS_FILE = Path(__file__).with_name("college_tiers.json")
NDCG_AT = 10
ACCEPT_TOP = 3
TEST_SHARE = 20  # percent of members (by a stable hash of their id) held out for evaluation
PARAMS = {
    "objective": "lambdarank", "metric": "ndcg", "ndcg_eval_at": [NDCG_AT], "learning_rate": 0.05, "num_leaves": 15,
    "min_data_in_leaf": 10, "lambdarank_truncation_level": 20, "seed": 7, "deterministic": True, "force_row_wise": True,
    "num_threads": 1, "verbose": -1,
}  # fmt: skip
ROUNDS = 120


def tier_of(college: str) -> int | None:
    tiers = json.loads(TIERS_FILE.read_text())["tiers"]
    lowered = {k.lower(): v for k, v in tiers.items()}
    return lowered.get((college or "").strip().lower())


@dataclass
class TrainingSet:
    """Rows are sorted by group; `sizes` says how many rows each group has (LambdaRank's `group`)."""

    features: list[dict] = field(default_factory=list)
    labels: list[int] = field(default_factory=list)
    rule_scores: list[float] = field(default_factory=list)
    tiers: list[int | None] = field(default_factory=list)  # the candidate's college tier: fairness check only
    viewers: list[int] = field(default_factory=list)
    simulated: list[bool] = field(default_factory=list)
    sizes: list[int] = field(default_factory=list)
    snapshot_ids: list[int] = field(default_factory=list)

    @property
    def groups(self) -> int:
        return len(self.sizes)

    @property
    def simulated_rows(self) -> int:
        return sum(self.simulated)

    @property
    def real_rows(self) -> int:
        return len(self.labels) - self.simulated_rows

    def histogram(self) -> dict[int, int]:
        return {k: self.labels.count(k) for k in range(4)}

    def data_hash(self) -> str:
        """Same data, same features, same settings -> same hash, so the job does not train the same model twice."""
        h = hashlib.sha256(json.dumps([list(feat.FEATURE_NAMES), PARAMS, ROUNDS]).encode())
        h.update(evaluation.EVAL_DIR.joinpath("pairs.json").read_bytes())
        for sid, label in sorted(zip(self.snapshot_ids, self.labels)):
            h.update(f"{sid}:{label};".encode())
        return h.hexdigest()

    def split(self) -> tuple["TrainingSet", "TrainingSet"]:
        """Train / test by member, so nobody's lists are on both sides."""
        train, test = TrainingSet(), TrainingSet()
        start = 0
        for size in self.sizes:
            part = (
                test
                if int(hashlib.sha256(f"split:{self.viewers[start]}".encode()).hexdigest()[:8], 16) % 100 < TEST_SHARE
                else train
            )
            sl = slice(start, start + size)
            for name in ("features", "labels", "rule_scores", "tiers", "viewers", "simulated", "snapshot_ids"):
                getattr(part, name).extend(getattr(self, name)[sl])
            part.sizes.append(size)
            start += size
        return train, test

    def group_slices(self):
        start = 0
        for size in self.sizes:
            yield slice(start, start + size)
            start += size


def credit_labels(shown: list[tuple[int, int, int, datetime]]) -> dict[int, int]:
    """`shown` is (snapshot id, viewer id, candidate id, shown_at). Returns {snapshot id: label 1-3} for snapshots an intro is credited to."""
    # credit each intro to the latest snapshot of the same pair shown shortly before it
    by_pair: dict[tuple[int, int], list[tuple]] = {}
    for sid, viewer, cand, shown_at in shown:
        by_pair.setdefault((viewer, cand), []).append((shown_at, sid))
    window = timedelta(days=settings.RANKER_LABEL_WINDOW_DAYS)
    label_of: dict[int, int] = {}
    for req, target, created, status, rating in IntroRequest.objects.filter(requester_id__in={s[1] for s in shown}).values_list(
        "requester_id", "target_id", "created_at", "status", "outcome_rating"
    ):
        seen = sorted(by_pair.get((req, target), []))
        i = bisect.bisect_right([t for t, _ in seen], created) - 1
        if i < 0 or created - seen[i][0] > window:
            continue
        label = 1
        if status in ("accepted", "completed"):
            label = 2
        if rating is not None and rating >= 4:
            label = 3
        sid = seen[i][1]
        label_of[sid] = max(label_of.get(sid, 0), label)
    return label_of


def build_training_set(include_simulated: bool | None = None) -> TrainingSet:
    if include_simulated is None:
        include_simulated = settings.ENV != "production"
    snaps = FeatureSnapshot.objects.filter(viewer__is_minor=False, candidate__is_minor=False)
    if not include_simulated:
        snaps = snaps.filter(viewer__is_simulated=False)
    rows = list(
        snaps.order_by("viewer_id", "surface", "shown_on", "position", "id").values_list(
            "id", "viewer_id", "candidate_id", "surface", "shown_on", "shown_at", "features", "rule_score",
            "viewer__is_simulated", "candidate__college",
        )
    )  # fmt: skip
    label_of = credit_labels([(r[0], r[1], r[2], r[5]) for r in rows])
    out = TrainingSet()
    key = None
    pending: list[tuple] = []

    def flush() -> None:
        if len(pending) >= 2:  # a list of one cannot teach an order
            for sid, viewer, f, rule, sim, college in pending:
                out.features.append(f)
                out.labels.append(label_of.get(sid, 0))
                out.rule_scores.append(rule)
                out.tiers.append(tier_of(college))
                out.viewers.append(viewer)
                out.simulated.append(sim)
                out.snapshot_ids.append(sid)
            out.sizes.append(len(pending))
        pending.clear()

    for sid, viewer, _cand, surface, day, _shown_at, f, rule, sim, college in rows:
        if (viewer, surface, day) != key:
            flush()
            key = (viewer, surface, day)
        pending.append((sid, viewer, f, rule, sim, college))
    flush()
    return out


# -- metrics ---------------------------------------------------------------------------------------------
def ndcg(labels: list[int], scores: list[float], k: int = NDCG_AT) -> float | None:
    """NDCG@k of one list, or None when nothing in it was wanted (nothing to rank)."""
    import math

    def dcg(order: list[int]) -> float:
        return sum((2 ** labels[j] - 1) / math.log2(rank + 2) for rank, j in enumerate(order[:k]))

    if not any(labels):
        return None
    ranked = sorted(range(len(labels)), key=lambda j: (-scores[j], j))  # ties keep the shown order
    ideal = sorted(range(len(labels)), key=lambda j: (-labels[j], j))
    return dcg(ranked) / dcg(ideal)


def mean_ndcg(ds: TrainingSet, scores: list[float]) -> float:
    vals = [v for sl in ds.group_slices() if (v := ndcg(ds.labels[sl], scores[sl])) is not None]
    return round(sum(vals) / len(vals), 4) if vals else 0.0


def acceptance_at(ds: TrainingSet, scores: list[float], k: int = ACCEPT_TOP) -> float:
    """Of the top-k places in each list, the share that were accepted or better (label 2+): the acceptance-rate proxy."""
    hits = slots = 0
    for sl in ds.group_slices():
        labels, sc = ds.labels[sl], scores[sl]
        top = sorted(range(len(labels)), key=lambda j: (-sc[j], j))[:k]
        hits += sum(labels[j] >= 2 for j in top)
        slots += len(top)
    return round(hits / slots, 4) if slots else 0.0


def eval_set_scores(model_predict) -> tuple[float, float]:
    """(model agreement, rule agreement) on the hand-labelled pairs in tests/eval/pairs.json."""
    data = evaluation.load_pairs()
    sides = evaluation.build_sides(data["profiles"])
    links = {k: tuple(v) for k, v in data.get("links", {}).items()}

    def row(member: str, other: str) -> dict:
        hops = links.get(f"{member}|{other}") or links.get(f"{other}|{member}")
        ps = scoring.score_pair(sides[member], sides[other], hops, settings.MATCH_WEIGHTS, settings.MATCH_MIN_SIMILARITY)
        prof = lambda key: feat.Profile(data["profiles"][key]["role"], 1)  # noqa: E731 - role only: that is all Profile holds
        f = feat.build(
            sides[member], sides[other], ps, prof(member), prof(other), 0, 1, hops[1] if hops else 0.0, feat.Extras({}, {})
        )  # fmt: skip
        return {**f, "rule_score": ps.score}

    better_rows, worse_rows = [], []
    for p in data["pairs"]:
        better_rows.append(row(p["member"], p["better"]))
        worse_rows.append(row(p["member"], p["worse"]))
    mb, mw = model_predict(better_rows), model_predict(worse_rows)
    total = len(data["pairs"]) or 1
    model = sum(b > w for b, w in zip(mb, mw)) / total
    rule = sum(r["rule_score"] > w["rule_score"] for r, w in zip(better_rows, worse_rows)) / total
    return round(model, 4), round(rule, 4)


def within_list_percentiles(ds: TrainingSet, scores: list[float]) -> list[float]:
    """Each row's place in its own list, 0 (lowest) to 1 (highest); tied rows share the average."""
    out = [0.5] * len(scores)
    for sl in ds.group_slices():
        sc = scores[sl]
        n = len(sc)
        if n < 2:
            continue
        for j, s in enumerate(sc):
            below, equal = sum(x < s for x in sc), sum(x == s for x in sc)
            out[sl.start + j] = (below + (equal - 1) / 2) / (n - 1)
    return out


def fairness(ds: TrainingSet, scores: list[float]) -> dict:
    """Do candidates from some college tiers, or Bridge vs local, get systematically lower places in their lists?

    The gap is the spread (max - min) of the mean within-list percentile across groups with at least
    RANKER_FAIRNESS_MIN_GROUP rows. A dimension with fewer than two such groups cannot be checked, which counts as a fail.
    """
    pct = within_list_percentiles(ds, scores)

    def spread(labels: list) -> dict:
        buckets: dict = {}
        for g, p in zip(labels, pct):
            if g is not None:
                buckets.setdefault(g, []).append(p)
        means = {
            str(g): round(sum(v) / len(v), 4) for g, v in sorted(buckets.items()) if len(v) >= settings.RANKER_FAIRNESS_MIN_GROUP
        }
        gap = round(max(means.values()) - min(means.values()), 4) if len(means) >= 2 else None
        return {"means": means, "gap": gap}

    by_tier = spread(ds.tiers)
    by_bridge = spread([bool(f["is_bridge"]) for f in ds.features])
    gaps = [by_tier["gap"], by_bridge["gap"]]
    passed = all(g is not None and g <= settings.RANKER_FAIRNESS_MAX_GAP for g in gaps)
    return {"college_tier": by_tier, "bridge_vs_local": by_bridge, "passed": passed}


# -- training --------------------------------------------------------------------------------------------
@dataclass
class Trained:
    model_text: str
    metrics: dict
    beats_rule: bool
    fairness_passed: bool


def train(ds: TrainingSet) -> Trained:
    import lightgbm as lgb
    import numpy as np

    train_ds, test_ds = ds.split()
    if not train_ds.groups or not test_ds.groups:
        raise ValueError("not enough members to hold some out for testing")
    X = np.array([feat.to_row(f) for f in train_ds.features], dtype=float)
    booster = lgb.train(
        PARAMS,
        lgb.Dataset(X, np.array(train_ds.labels), group=train_ds.sizes, feature_name=list(feat.FEATURE_NAMES)),
        num_boost_round=ROUNDS,
    )

    def predict(rows: list[dict]) -> list[float]:
        return [float(x) for x in booster.predict(np.array([feat.to_row(r) for r in rows], dtype=float))]

    model_scores = predict(test_ds.features)
    rule_scores = test_ds.rule_scores
    m_agree, r_agree = eval_set_scores(predict)
    fair = fairness(test_ds, model_scores)
    metrics = {
        "model": {"ndcg@10": mean_ndcg(test_ds, model_scores), "acceptance@3": acceptance_at(test_ds, model_scores), "eval_agreement": m_agree},
        "rule": {"ndcg@10": mean_ndcg(test_ds, rule_scores), "acceptance@3": acceptance_at(test_ds, rule_scores), "eval_agreement": r_agree},
        "fairness": fair,
        "rule_fairness": fairness(test_ds, rule_scores),
        "rows": {"train": len(train_ds.labels), "test": len(test_ds.labels)},
        "groups": {"train": train_ds.groups, "test": test_ds.groups},
        "labels": ds.histogram(),
    }  # fmt: skip
    m, r = metrics["model"], metrics["rule"]
    beats = (
        m["ndcg@10"] > r["ndcg@10"]
        and m["acceptance@3"] > r["acceptance@3"]
        and m["eval_agreement"] >= r["eval_agreement"] - 1e-9
    )
    return Trained(booster.model_to_string(), metrics, beats, fair["passed"])
