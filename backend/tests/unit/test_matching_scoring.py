"""Matching maths on hand-built examples: no database."""

import pytest

from apps.matching import scoring
from apps.matching.scoring import PairScore, Side

W = {"complementarity": 0.5, "affinity": 0.2, "trust_path": 0.15, "timing": 0.1, "load_penalty": 0.05}


def ps(score, bridge=False):
    return PairScore(score, {}, bridge, None, None, (), None)


# -- one_way and complementarity -------------------------------------------------------------------
def test_one_way_exact_capability_is_full_marks():
    assert scoring.one_way({"seo": None}, {"seo": None}, 0.8) == (1.0, ("seo", "seo"))


def test_one_way_is_the_mean_over_needs():
    score, pair = scoring.one_way({"seo": None, "sales": None}, {"seo": None}, 0.8)
    assert score == 0.5 and pair == ("seo", "seo")


def test_one_way_similar_text_counts_partially_above_the_threshold_only():
    needs = {"x": [1.0, 0.0]}
    assert scoring.one_way(needs, {"y": [1.0, 0.0]}, 0.8) == (0.8, ("x", "y"))
    assert scoring.one_way(needs, {"y": [0.0, 1.0]}, 0.8) == (0.0, None)
    assert scoring.one_way(needs, {"y": None}, 0.8) == (0.0, None)  # no vector, no partial credit


def test_one_way_with_no_needs_is_zero():
    assert scoring.one_way({}, {"seo": None}, 0.8) == (0.0, None)


def test_complementarity_rewards_two_way_help():
    assert scoring.complementarity(1, 1) == 1
    assert scoring.complementarity(1, 0) == scoring.complementarity(0, 1) == 0.6
    assert scoring.complementarity(0, 0) == 0
    assert scoring.complementarity(1, 0.5) > scoring.complementarity(1, 0)


# -- the other components --------------------------------------------------------------------------
def test_affinity_is_jaccard():
    assert scoring.affinity(frozenset("ab"), frozenset("bc")) == pytest.approx(1 / 3)
    assert scoring.affinity(frozenset("ab"), frozenset("ab")) == 1
    assert scoring.affinity(frozenset(), frozenset()) == 0


def test_trust_path_direct_beats_friend_of_friend_beats_stranger():
    assert scoring.trust_path(1, 1.0) == 1.0 and scoring.trust_path(1, 0.0) == 0.5
    assert scoring.trust_path(2, 1.0) == 0.5
    assert scoring.trust_path(1, 0.2) == 0.6 > scoring.trust_path(2, 1.0)  # even a weak direct link beats a strong 2-hop
    assert scoring.trust_path(None, 1.0) == 0


def test_timing_decays_to_zero_after_90_days():
    assert scoring.timing(0) == 1 and scoring.timing(45) == 0.5 and scoring.timing(200) == 0


def test_load_penalty_only_bites_below_three_free_slots():
    assert scoring.load_penalty(3) == 0 and scoring.load_penalty(5) == 0
    assert scoring.load_penalty(0) == 1
    assert scoring.load_penalty(1) == pytest.approx(2 / 3)


def test_bridge_needs_two_different_known_sectors_and_a_real_fit():
    assert scoring.is_bridge("biotech", "deeptech", 0.6)
    assert not scoring.is_bridge("biotech", "biotech", 0.6)
    assert not scoring.is_bridge("biotech", None, 0.6)  # a mentor or student has no sector: never a Bridge match
    assert not scoring.is_bridge("biotech", "deeptech", 0)


# -- score_pair ------------------------------------------------------------------------------------
def test_score_pair_combines_components_with_the_weights():
    me = Side(needs={"seo": None}, traits=frozenset({"a"}), sector="biotech")
    other = Side(offers={"seo": None}, traits=frozenset({"a"}), sector="deeptech", open_slots=3, active_days=0)
    p = scoring.score_pair(me, other, None, W, 0.8)
    # complementarity 0.6 (one way), affinity 1, no connection, fresh, no load penalty
    assert p.components == {"complementarity": 0.6, "affinity": 1.0, "trust_path": 0.0, "timing": 1.0, "load_penalty": 0.0}
    assert p.score == pytest.approx(0.5 * 0.6 + 0.2 * 1 + 0.1 * 1)
    assert p.is_bridge and p.they_give == ("seo", "seo") and p.i_give is None and p.shared_traits == ("a",)


def test_score_pair_two_way_beats_one_way_and_connection_helps():
    me = Side(needs={"seo": None}, offers={"sales": None})
    one = Side(offers={"seo": None})
    two = Side(offers={"seo": None}, needs={"sales": None})
    s1, s2 = (scoring.score_pair(me, o, None, W, 0.8).score for o in (one, two))
    assert s2 > s1
    assert scoring.score_pair(me, two, (1, 0.9), W, 0.8).score > s2


def test_score_pair_is_clamped_and_load_penalty_subtracts():
    me = Side(needs={"seo": None})
    full = Side(offers={"seo": None}, open_slots=1)
    roomy = Side(offers={"seo": None}, open_slots=3)
    assert scoring.score_pair(me, full, None, W, 0.8).score < scoring.score_pair(me, roomy, None, W, 0.8).score
    nothing = scoring.score_pair(Side(), Side(open_slots=0, active_days=999), None, W, 0.8)
    assert nothing.score == 0


# -- reasons ---------------------------------------------------------------------------------------
NAMES = {"seo": "SEO", "sales": "Sales"}


def test_reason_says_who_helps_whom():
    base = dict(components={}, is_bridge=False, shared_traits=(), hops=None)
    assert scoring.reason(PairScore(0.5, they_give=("seo", "seo"), i_give=None, **base), NAMES, {}) == (
        "They offer seo, which you need."
    )
    assert scoring.reason(PairScore(0.5, they_give=None, i_give=("sales", "sales"), **base), NAMES, {}) == (
        "You offer sales, which they need."
    )
    both = scoring.reason(PairScore(0.5, they_give=("seo", "seo"), i_give=("sales", "sales"), **base), NAMES, {})
    assert both.startswith("You can help each other")


def test_reason_mentions_shared_traits_and_connection_and_stays_short():
    p = PairScore(0.5, {}, True, ("seo", "seo"), None, ("long-sales-cycle", "technical-buyers"), 2)
    text = scoring.reason(p, NAMES, {"long-sales-cycle": "Long sales cycle", "technical-buyers": "Technical buyers"})
    assert "long sales cycle, technical buyers" in text and "mutual connection" in text
    assert len(text) <= scoring.MAX_REASON


# -- ranking ---------------------------------------------------------------------------------------
def test_rank_orders_by_score_with_id_as_tiebreak():
    out = scoring.rank([(3, ps(0.5), None), (1, ps(0.5), None), (2, ps(0.9), None)], 10, 0.25, 5)
    assert [c for c, _ in out] == [2, 1, 3]


def test_rank_keeps_a_bridge_share_even_when_local_scores_are_higher():
    local = [(i, ps(0.9 - i * 0.01), None) for i in range(1, 7)]
    bridge = [(i, ps(0.3 - i * 0.01, True), None) for i in range(10, 14)]
    out = scoring.rank(local + bridge, 4, 0.25, 5)
    assert len(out) == 4 and sum(p.is_bridge for _, p in out) == 1  # 25% of 4
    assert [c for c, p in out if p.is_bridge] == [10]  # the best bridge match


def test_rank_fills_with_bridge_matches_when_there_are_few_local_ones():
    out = scoring.rank([(1, ps(0.9), None)] + [(i, ps(0.5, True), None) for i in range(10, 20)], 4, 0.25, 5)
    assert len(out) == 4 and sum(p.is_bridge for _, p in out) == 3


def test_rank_limits_how_many_come_from_one_sector():
    scored = [(i, ps(0.9 - i * 0.01), "saas") for i in range(1, 6)] + [(9, ps(0.1), "d2c"), (8, ps(0.05), None)]
    out = scoring.rank(scored, 10, 0.25, 2)
    assert [c for c, _ in out] == [1, 2, 9, 8]  # two saas, then the others; people without a sector are never capped


def test_haversine_known_distance():
    assert scoring.haversine_km(13.0827, 80.2707, 13.0827, 80.2707) == 0
    assert scoring.haversine_km(13.0827, 80.2707, 12.9716, 77.5946) == pytest.approx(290, abs=5)  # Chennai - Bengaluru
