"""Features, RuleRanker, ModelRanker, shadow and A/B in compute_matches. A model changes the ORDER of a list, nothing else."""

import ast
import dataclasses
from pathlib import Path

import pytest
from django.conf import settings as django_settings

from apps.accounts.models import Member
from apps.matching import scoring, services
from apps.matching.models import MatchResult
from apps.matching.ranker import features as feat
from apps.matching.ranker import registry
from apps.matching.ranker.model import ModelRanker
from apps.matching.ranker.rule import RuleRanker
from tests.api.test_matches import need, offer, trait
from tests.unit.ranker_helpers import make_model, store_booster

pytestmark = pytest.mark.django_db
RANKER_DIR = Path(django_settings.BASE_DIR) / "apps" / "matching" / "ranker"


@pytest.fixture
def network(lists, make_member):
    """One seeker who needs SEO and six mentors who offer it, differing in free slots and shared traits."""
    seeker = make_member("founder")
    need(seeker, "seo")
    trait(seeker, "long-sales-cycle")
    givers = []
    for i in range(6):
        g = make_member("mentor", open_intro_slots=1 + i % 3)
        offer(g, "seo")
        if i % 2:
            trait(g, "long-sales-cycle")
        givers.append(g)
    return seeker, givers


def serve(mv, status, settings, percent=100):
    settings.ENV = "dev"
    settings.RANKER_AB_PERCENT = percent
    mv = store_booster(mv)
    for step in ("shadow", "ab", "active"):
        mv = registry.promote(mv, step)
        if step == status:
            return mv
    return mv


def rows_for(member):
    return list(MatchResult.objects.filter(member=member).order_by("position"))


# -- banned features -----------------------------------------------------------------------------------
def test_no_feature_or_profile_field_names_a_banned_thing():
    names = {*feat.FEATURE_NAMES, *(f.name for f in dataclasses.fields(feat.Profile))}
    for name in names:
        assert not set(name.split("_")) & set(feat.BANNED_TERMS), name


def test_the_feature_builder_never_reads_the_college_tier_file():
    tree = ast.parse((RANKER_DIR / "features.py").read_text())
    imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    }
    assert not any("training" in m or "tier" in m for m in imported)
    assert "college_tiers" not in (RANKER_DIR / "features.py").read_text()


def test_college_organisation_name_and_email_do_not_change_any_feature(network, make_org):
    seeker, givers = network
    services.compute_all()
    before = {r.candidate_id: r.features for r in rows_for(seeker)}
    org = make_org()
    for m in [seeker, *givers]:
        Member.objects.filter(pk=m.pk).update(
            college="Madras School of Engineering", display_name="Someone Else", email="x@elite.example", organisation=org
        )
    services.compute_all()
    assert {r.candidate_id: r.features for r in rows_for(seeker)} == before and before


def test_features_come_in_the_contracted_order_and_are_json_safe(network):
    seeker, _ = network
    services.compute_all()
    for r in rows_for(seeker):
        assert set(r.features) == set(feat.FEATURE_NAMES)  # (jsonb does not keep key order; to_row restores the contracted order)
        assert all(v is None or isinstance(v, int | float) for v in r.features.values())
    assert len(feat.to_row(rows_for(seeker)[0].features)) == len(feat.FEATURE_NAMES)


# -- RuleRanker ----------------------------------------------------------------------------------------
def test_without_a_model_the_rule_orders_and_nothing_extra_is_stored(network):
    seeker, _ = network
    services.compute_all()
    rows = rows_for(seeker)
    assert [r.position for r in rows] == list(range(len(rows)))
    assert [r.score for r in rows] == sorted((r.score for r in rows), reverse=True)
    assert (
        {r.arm for r in rows} == {"rule"} and {r.model_version for r in rows} == {""} and {r.model_score for r in rows} == {None}
    )
    assert RuleRanker().score([{"rule_score": 0.4}, {"rule_score": 0.9}]) == [0.4, 0.9]


def test_rank_with_an_order_reorders_but_keeps_the_same_rules(network):
    ps = scoring.score_pair(scoring.Side(), scoring.Side(), None, django_settings.MATCH_WEIGHTS, 0.8)
    scored = [(1, ps, None), (2, ps, None), (3, ps, None)]
    assert [c for c, _ in scoring.rank(scored, 3, 0.25, 5)] == [1, 2, 3]
    assert [c for c, _ in scoring.rank(scored, 3, 0.25, 5, {1: 0.1, 2: 0.2, 3: 0.3})] == [3, 2, 1]
    assert [c for c, _ in scoring.rank(scored, 2, 0.25, 5, {1: 0.1, 2: 0.2, 3: 0.3})] == [3, 2]  # limit still applies


# -- shadow, A/B, active ----------------------------------------------------------------------------------
def test_shadow_logs_the_models_scores_but_the_rule_orders(network, settings):
    seeker, _ = network
    services.compute_all()
    rule_order = [r.candidate_id for r in rows_for(seeker)]
    mv = serve(make_model(trained_env="dev"), "shadow", settings)
    stats = services.compute_all()
    rows = rows_for(seeker)
    assert [r.candidate_id for r in rows] == rule_order and stats["model_lists"] == 0
    assert {r.arm for r in rows} == {"rule"} and {r.model_version for r in rows} == {mv.version}
    assert all(r.model_score is not None for r in rows)


def test_active_model_orders_every_list_by_its_own_score(network, settings):
    seeker, _ = network
    mv = serve(make_model(trained_env="dev"), "active", settings)
    services.compute_all()
    rows = rows_for(seeker)
    assert {r.arm for r in rows} == {"model"} and {r.model_version for r in rows} == {mv.version}
    scores = [r.model_score for r in rows]
    assert scores == sorted(scores, reverse=True)


def test_the_model_never_changes_strength_words_or_who_is_eligible(network, settings, client_for):
    seeker, _ = network
    services.compute_all()
    rule_rows = {r.candidate_id: r.score for r in rows_for(seeker)}
    serve(make_model(trained_env="dev"), "active", settings)
    services.compute_all()
    assert {r.candidate_id: r.score for r in rows_for(seeker)} == rule_rows  # same people, same rule scores
    for item in client_for(seeker).get("/api/matches").json()["items"]:
        assert item["strength"] == services.strength_for(rule_rows[item["candidate_id"]])


def test_ab_share_is_stable_and_about_the_configured_percent(settings):
    from apps.matching.ranker.serving import in_ab_share

    settings.RANKER_AB_PERCENT = 20
    first = [in_ab_share("v1", i) for i in range(2000)]
    assert first == [in_ab_share("v1", i) for i in range(2000)]
    assert 0.15 < sum(first) / 2000 < 0.25
    settings.RANKER_AB_PERCENT = 0
    assert not any(in_ab_share("v1", i) for i in range(200))
    settings.RANKER_AB_PERCENT = 100
    assert all(in_ab_share("v1", i) for i in range(200))


def test_ab_only_orders_the_members_in_the_share(network, settings):
    seeker, _ = network
    serve(make_model(trained_env="dev"), "ab", settings, percent=0)
    services.compute_all()
    assert {r.arm for r in rows_for(seeker)} == {"rule"}
    serve(make_model(trained_env="dev"), "ab", settings, percent=100)
    services.compute_all()
    assert {r.arm for r in rows_for(seeker)} == {"model"}


# -- any error means the rule ---------------------------------------------------------------------------
def rule_result(seeker):
    services.compute_all()
    return [(r.candidate_id, r.score, r.position) for r in rows_for(seeker)]


def test_a_model_file_that_does_not_match_its_hash_is_not_used(network, settings):
    seeker, _ = network
    expected = rule_result(seeker)
    mv = serve(make_model(trained_env="dev"), "active", settings)
    type(mv).objects.filter(pk=mv.pk).update(sha256="f" * 64)
    services.compute_all()
    assert [(r.candidate_id, r.score, r.position) for r in rows_for(seeker)] == expected
    assert {r.arm for r in rows_for(seeker)} == {"rule"}


def test_a_missing_model_file_is_not_fatal(network, settings):
    seeker, _ = network
    mv = serve(make_model(trained_env="dev"), "active", settings)
    type(mv).objects.filter(pk=mv.pk).update(file_path="ml/models/gone/model.txt")
    services.compute_all()
    assert {r.arm for r in rows_for(seeker)} == {"rule"}


def test_a_model_that_errors_while_scoring_falls_back_to_the_rule(network, settings, monkeypatch):
    seeker, _ = network
    expected = rule_result(seeker)
    serve(make_model(trained_env="dev"), "active", settings)

    def boom(self, rows):
        raise RuntimeError("predict failed")

    monkeypatch.setattr(ModelRanker, "score", boom)
    services.compute_all()
    assert [(r.candidate_id, r.score, r.position) for r in rows_for(seeker)] == expected
    assert {r.arm for r in rows_for(seeker)} == {"rule"}


def test_a_model_trained_on_other_features_is_not_used(network, settings):
    seeker, _ = network
    settings.ENV = "dev"
    mv = store_booster(make_model(trained_env="dev"), names=[f"x{i}" for i in range(len(feat.FEATURE_NAMES))])
    for step in ("shadow", "ab", "active"):
        mv = registry.promote(mv, step)
    services.compute_all()
    assert {r.arm for r in rows_for(seeker)} == {"rule"}


def test_the_fast_similarity_index_gives_the_same_numbers_as_the_plain_version():
    import random

    rng = random.Random(3)

    def side():
        def vecs():
            return {f"cap{i}": [rng.uniform(-1, 1) for _ in range(8)] for i in range(rng.randint(0, 3))} | {"none": None}

        return scoring.Side(needs=vecs(), offers=vecs())

    sides = {i: side() for i in range(12)}
    index = feat.SimilarityIndex(sides)
    for a in sides:
        for b in sides:
            if a != b:
                assert index.best(a, b) == pytest.approx(feat._best_similarity(sides[a], sides[b]), abs=1e-9)
