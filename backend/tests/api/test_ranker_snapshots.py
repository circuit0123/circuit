"""feature_snapshots: what the matcher showed, with the exact features it saw (CLAUDE.md "Matching ML")."""

from datetime import timedelta

import pytest
from django.db import DatabaseError
from django.utils import timezone

from apps.accounts import deletion, export, retention
from apps.accounts.models import Member
from apps.matching import services
from apps.matching.models import FeatureSnapshot, MatchResult
from apps.matching.ranker import features as feat
from apps.social import drop as drop_service
from tests.api.test_matches import need, offer, trait
from tests.unit.ranker_helpers import make_model, store_booster

pytestmark = pytest.mark.django_db


@pytest.fixture
def network(lists, make_member):
    """A seeker and five mentors who offer what the seeker needs."""
    seeker = make_member("founder")
    need(seeker, "seo")
    givers = []
    for _ in range(5):
        g = make_member("mentor", open_intro_slots=3)
        offer(g, "seo")
        givers.append(g)
    services.compute_all()
    return seeker, givers


@pytest.fixture
def strong_pair(lists, make_member):
    """Two members who each offer what the other needs and share traits: a Strong match in both directions."""
    a, b = make_member("founder", open_intro_slots=3), make_member("mentor", open_intro_slots=3)
    for m, n, o in ((a, "seo", "fundraising"), (b, "fundraising", "seo")):
        need(m, n)
        offer(m, o)
        trait(m, "long-sales-cycle")
        trait(m, "technical-buyers")
    services.compute_all()
    return a, b


def snaps(viewer, surface=None):
    qs = FeatureSnapshot.objects.filter(viewer=viewer)
    return qs.filter(surface=surface) if surface else qs


# -- /api/matches ----------------------------------------------------------------------------------------
def test_listing_matches_logs_one_snapshot_per_card_with_the_stored_features(network, client_for):
    seeker, givers = network
    items = client_for(seeker).get("/api/matches").json()["items"]
    rows = list(snaps(seeker, "matches").order_by("position"))
    assert [r.candidate_id for r in rows] == [i["candidate_id"] for i in items] and len(rows) == 5
    assert [r.position for r in rows] == [0, 1, 2, 3, 4]
    stored = MatchResult.objects.get(member=seeker, candidate=rows[0].candidate)
    assert rows[0].features == stored.features and rows[0].rule_score == stored.score and rows[0].arm == "rule"
    assert set(rows[0].features) == set(feat.FEATURE_NAMES)


def test_positions_follow_the_page_offset_and_a_refresh_adds_nothing(network, client_for):
    seeker, _ = network
    c = client_for(seeker)
    c.get("/api/matches?limit=2&offset=2")
    assert sorted(snaps(seeker).values_list("position", flat=True)) == [2, 3]
    c.get("/api/matches?limit=2&offset=2")
    c.get("/api/matches")  # the full list on the same day: the two already logged keep their first position
    assert snaps(seeker).count() == 5


def test_a_next_day_refresh_is_a_new_snapshot(network, client_for):
    seeker, _ = network
    client_for(seeker).get("/api/matches")
    FeatureSnapshot.objects.update(shown_on=timezone.now().date() - timedelta(days=1))
    client_for(seeker).get("/api/matches")
    assert snaps(seeker).count() == 10


def test_a_logging_failure_never_breaks_the_page(network, client_for, monkeypatch):
    seeker, _ = network

    def boom(*a, **k):
        raise DatabaseError("disk full")

    monkeypatch.setattr(FeatureSnapshot.objects, "bulk_create", boom)
    r = client_for(seeker).get("/api/matches")
    assert r.status_code == 200 and len(r.json()["items"]) == 5


def test_matches_stored_before_stage_4c_have_no_features_and_are_not_logged(network, client_for):
    seeker, _ = network
    MatchResult.objects.filter(member=seeker).update(features={})
    assert client_for(seeker).get("/api/matches").status_code == 200
    assert not snaps(seeker).exists()


def test_nothing_is_logged_about_under_18s(lists, make_member, client_for):
    kid = make_member("student", is_minor=True)
    adult = make_member("mentor")
    other = make_member("mentor")
    for m in (kid, adult, other):
        need(m, "seo") if m is kid else offer(m, "seo")
    services.compute_all()
    # a minor viewer
    client_for(kid).get("/api/matches")
    assert not FeatureSnapshot.objects.exists()
    # an adult viewer whose match list holds a minor (the row is forced; matching normally keeps strangers apart)
    MatchResult.objects.create(
        member=adult, candidate=kid, score=0.9, reason="r", features={k: 0 for k in feat.FEATURE_NAMES}, position=0
    )
    client_for(adult).get("/api/matches")
    assert not snaps(adult).filter(candidate=kid).exists()


def test_every_snapshot_belongs_to_the_caller_and_never_to_someone_elses_list(network, client_for):
    seeker, givers = network
    client_for(givers[0]).get("/api/matches")
    client_for(seeker).get("/api/matches")
    assert set(FeatureSnapshot.objects.filter(surface="matches").values_list("viewer_id", flat=True)) <= {seeker.pk, givers[0].pk}
    assert not snaps(givers[1]).exists()  # someone who never opened the app has nothing logged


def test_the_serving_models_version_and_score_are_in_the_snapshot(network, client_for, settings):
    from apps.matching.ranker import registry

    seeker, _ = network
    settings.ENV = "dev"
    mv = store_booster(make_model(trained_env="dev"))
    for step in ("shadow", "ab", "active"):
        mv = registry.promote(mv, step)
    settings.RANKER_AB_PERCENT = 100
    services.compute_all()
    client_for(seeker).get("/api/matches")
    row = snaps(seeker).first()
    assert row.arm == "model" and row.model_version == mv.version and row.model_score is not None


# -- Daily Drop --------------------------------------------------------------------------------------------
def test_the_daily_drop_logs_the_features_the_ranker_saw_when_the_cards_are_shown(strong_pair, client_for):
    a, b = strong_pair
    drop_service.build_all()
    assert not snaps(a).exists()  # building the drop shows nothing to anyone
    cards = client_for(a).get("/api/drop/today").json()["cards"]
    assert len(cards) == 1
    row = snaps(a, "daily_drop").get()
    assert row.candidate_id == b.pk and row.position == 0
    assert row.features == MatchResult.objects.get(member=a, candidate=b).features
    client_for(a).get("/api/drop/today")
    client_for(a).post(f"/api/drop/today/{b.pk}/swipe", {"direction": "skip"})
    assert snaps(a, "daily_drop").count() == 1


def test_a_card_never_seen_is_never_logged(strong_pair, client_for):
    a, b = strong_pair
    drop_service.build_all()
    client_for(b).get("/api/drop/today")
    assert not snaps(a).exists() and snaps(b).count() == 1


# -- deletion, retention, export ----------------------------------------------------------------------------
def test_deleting_an_account_removes_snapshots_on_both_sides(network, client_for):
    seeker, givers = network
    client_for(seeker).get("/api/matches")
    client_for(givers[0]).get("/api/matches")
    assert FeatureSnapshot.objects.filter(candidate=givers[0]).exists() and snaps(givers[0]).exists()
    deletion.request_deletion(givers[0])
    deletion.erase(givers[0])
    assert not FeatureSnapshot.objects.filter(viewer=givers[0]).exists()
    assert not FeatureSnapshot.objects.filter(candidate=givers[0]).exists()
    assert FeatureSnapshot.objects.filter(viewer=seeker).exists()  # everyone else's lists keep their other rows


def test_retention_removes_old_snapshots_but_keeps_recent_and_simulated_ones(network, client_for):
    seeker, givers = network
    client_for(seeker).get("/api/matches")
    sim = Member.objects.create(auth_user_id="00000000-0000-4000-8000-000000000001", is_simulated=True)
    old = timezone.now() - timedelta(days=400)
    FeatureSnapshot.objects.filter(candidate=givers[0]).update(shown_at=old)
    FeatureSnapshot.objects.create(
        viewer=sim, candidate=givers[1], surface="simulation", features={}, rule_score=0.5, shown_at=old, shown_on=old.date()
    )
    counts = retention.run()
    assert counts["ranker_snapshots"] == 1
    assert not FeatureSnapshot.objects.filter(candidate=givers[0], viewer=seeker).exists()
    assert FeatureSnapshot.objects.filter(viewer=seeker).count() == 4 and FeatureSnapshot.objects.filter(viewer=sim).exists()


def test_the_unverified_account_purge_leaves_simulated_members_alone():
    sim = Member.objects.create(auth_user_id="00000000-0000-4000-8000-000000000002", is_simulated=True)
    Member.objects.filter(pk=sim.pk).update(created_at=timezone.now() - timedelta(days=90))
    assert retention.purge_unverified() == 0
    assert Member.objects.get(pk=sim.pk).deleted_at is None


def test_the_data_export_does_not_include_snapshots(network, client_for):
    import json

    seeker, _ = network
    client_for(seeker).get("/api/matches")
    assert FeatureSnapshot.objects.exists()
    data = json.dumps(export.member_data(seeker), default=str)
    assert "rule_score" not in data and "embedding_similarity" not in data
