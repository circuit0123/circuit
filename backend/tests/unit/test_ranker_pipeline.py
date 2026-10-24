"""simulate_network -> build_training_set -> train_ranker, the metrics, the fairness check and the A/B report."""

import hashlib
import io
import json
from datetime import timedelta

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.accounts.models import Member
from apps.events.models import Event
from apps.intros.models import IntroRequest
from apps.matching import services
from apps.matching.models import FeatureSnapshot, MatchResult, ModelVersion
from apps.matching.ranker import features as feat
from apps.matching.ranker import registry, training
from apps.matching.ranker.report import arm_report
from core.storage import get_storage
from tests.api.test_matches import need, offer

pytestmark = pytest.mark.django_db
SMALL = ["--members", "80", "--rounds", "8"]


def run(name, *args):
    out = io.StringIO()
    call_command(name, *args, stdout=out)
    return out.getvalue()


@pytest.fixture
def sim(lists):
    run("simulate_network", *SMALL)


# -- simulate_network ------------------------------------------------------------------------------------
def test_simulate_network_refuses_in_production(lists, settings):
    settings.ENV = "production"
    with pytest.raises(CommandError, match="never runs in production"):
        run("simulate_network", *SMALL)
    assert not Member.objects.filter(is_simulated=True).exists()


def test_simulate_network_creates_labelled_data_and_is_idempotent(sim):
    members = Member.objects.filter(is_simulated=True)
    assert members.count() == 80
    snaps, intros = FeatureSnapshot.objects.count(), IntroRequest.objects.count()
    assert snaps > 500 and intros > 20
    assert set(FeatureSnapshot.objects.values_list("surface", flat=True)) == {"simulation"}
    assert IntroRequest.objects.filter(status__in=["accepted", "completed"]).exists()
    assert IntroRequest.objects.filter(status="declined").exists()
    assert "skipped" in run("simulate_network", *SMALL)
    assert (members.count(), FeatureSnapshot.objects.count(), IntroRequest.objects.count()) == (80, snaps, intros)


def test_reset_rebuilds_the_same_simulation(sim):
    before = FeatureSnapshot.objects.count()
    run("simulate_network", *SMALL, "--reset")
    assert Member.objects.filter(is_simulated=True).count() == 80 and FeatureSnapshot.objects.count() == before


def test_simulation_writes_no_events_and_no_notifications(lists):
    before = Event.objects.count()
    run("simulate_network", *SMALL)
    assert Event.objects.count() == before


def test_simulated_members_never_reach_real_matching_or_circuits(sim, make_member, lists):
    seeker = make_member("founder")
    need(seeker, "seo")
    assert Member.objects.filter(is_simulated=True, offers__capability__slug="seo").exists()  # someone simulated could help
    stats = services.compute_all()
    assert not MatchResult.objects.filter(member=seeker).exists()
    assert (
        not MatchResult.objects.filter(member__is_simulated=True).exists()
        and not MatchResult.objects.filter(candidate__is_simulated=True).exists()
    )
    assert stats["members"] == 1
    assert not set(services.load_world(timezone.now()).members) & set(
        Member.objects.filter(is_simulated=True).values_list("pk", flat=True)
    )
    from apps.circuits import services as circuits

    Member.objects.filter(is_simulated=True).update(circuits_opt_in=True)  # opted in, with matching needs and offers
    assert circuits.build_edges(timezone.now())[0] == {}


# -- labels ------------------------------------------------------------------------------------------------
@pytest.fixture
def shown(lists, make_member):
    """One viewer shown five people at 08:00 on one day; returns (viewer, [candidates], shown_at)."""
    viewer, cands = make_member("founder"), [make_member("mentor") for _ in range(5)]
    at = timezone.now() - timedelta(days=3)
    for pos, c in enumerate(cands):
        FeatureSnapshot.objects.create(
            viewer=viewer, candidate=c, surface="matches", features={k: 0.5 for k in feat.FEATURE_NAMES}, position=pos,
            rule_score=0.9 - pos * 0.1, shown_at=at, shown_on=at.date(),
        )  # fmt: skip
    return viewer, cands, at


def intro(viewer, target, at, status="pending", rating=None):
    i = IntroRequest.objects.create(
        requester=viewer, target=target, status=status, outcome_rating=rating, expires_at=at + timedelta(days=7)
    )
    IntroRequest.objects.filter(pk=i.pk).update(created_at=at)
    return i


def test_labels_are_graded_from_what_happened_after_the_card_was_shown(shown):
    viewer, c, at = shown
    intro(viewer, c[0], at + timedelta(hours=1))  # asked: 1
    intro(viewer, c[1], at + timedelta(hours=1), "accepted")  # said yes: 2
    intro(viewer, c[2], at + timedelta(hours=1), "completed", 5)  # met and rated 5: 3
    intro(viewer, c[3], at + timedelta(hours=1), "completed", 3)  # met but only 3 stars: 2
    # c[4]: nothing happened: 0
    ds = training.build_training_set()
    by_candidate = dict(zip([FeatureSnapshot.objects.get(pk=s).candidate_id for s in ds.snapshot_ids], ds.labels))
    assert by_candidate == {c[0].pk: 1, c[1].pk: 2, c[2].pk: 3, c[3].pk: 2, c[4].pk: 0}
    assert ds.groups == 1 and ds.sizes == [5] and ds.histogram() == {0: 1, 1: 1, 2: 2, 3: 1}


def test_an_intro_is_credited_to_the_latest_snapshot_before_it_and_only_within_the_window(shown, settings):
    viewer, c, at = shown
    later = at + timedelta(days=1)
    FeatureSnapshot.objects.create(
        viewer=viewer, candidate=c[0], surface="daily_drop", features={k: 0.1 for k in feat.FEATURE_NAMES}, position=0,
        rule_score=0.8, shown_at=later, shown_on=later.date(),
    )  # fmt: skip
    intro(viewer, c[0], later + timedelta(hours=2), "accepted")
    intro(viewer, c[1], at + timedelta(days=settings.RANKER_LABEL_WINDOW_DAYS + 1))  # too long after: not credited
    intro(viewer, c[2], at - timedelta(hours=1))  # before it was shown: not credited
    labelled = training.credit_labels([(s.pk, s.viewer_id, s.candidate_id, s.shown_at) for s in FeatureSnapshot.objects.all()])
    credited = {FeatureSnapshot.objects.get(pk=k).surface: v for k, v in labelled.items()}
    assert credited == {"daily_drop": 2}


def test_under_18s_and_lists_of_one_stay_out_of_training(shown, make_member):
    viewer, c, at = shown
    kid = make_member("student", is_minor=True)
    FeatureSnapshot.objects.create(
        viewer=kid, candidate=c[0], surface="matches", features={}, rule_score=0.5, shown_at=at, shown_on=at.date()
    )
    FeatureSnapshot.objects.create(
        viewer=make_member("founder"), candidate=c[0], surface="matches", features={k: 0 for k in feat.FEATURE_NAMES},
        rule_score=0.5, shown_at=at, shown_on=at.date(),
    )  # fmt: skip
    ds = training.build_training_set()
    assert ds.sizes == [5] and kid.pk not in ds.viewers  # the minor's row and the list of one are both left out


def test_the_data_hash_changes_only_when_the_data_does(shown):
    viewer, c, at = shown
    a = training.build_training_set().data_hash()
    assert a == training.build_training_set().data_hash()
    intro(viewer, c[0], at + timedelta(hours=1))
    assert training.build_training_set().data_hash() != a


def test_in_production_simulated_people_are_not_in_the_training_set(sim, settings):
    assert training.build_training_set(include_simulated=True).groups > 0
    settings.ENV = "production"
    assert training.build_training_set().groups == 0


# -- metrics -------------------------------------------------------------------------------------------------
def test_ndcg_is_one_for_the_ideal_order_and_lower_for_a_bad_one():
    assert training.ndcg([3, 2, 0], [0.9, 0.5, 0.1]) == pytest.approx(1.0)
    assert training.ndcg([3, 2, 0], [0.1, 0.5, 0.9]) < 0.7
    assert training.ndcg([0, 0, 0], [0.3, 0.2, 0.1]) is None  # nothing wanted: nothing to rank


def test_acceptance_proxy_counts_accepted_in_the_top_places():
    ds = training.TrainingSet(labels=[2, 0, 0, 0, 3, 1], sizes=[4, 2])
    assert training.acceptance_at(ds, [0.9, 0.8, 0.7, 0.6, 0.9, 0.1], k=1) == 1.0  # both lists put an accepted card first
    assert training.acceptance_at(ds, [0.1, 0.8, 0.7, 0.6, 0.1, 0.9], k=1) == 0.0


def make_scored(groups):
    """groups: list of (tier, bridge, [percentile-driving score]) rows in one big list."""
    ds = training.TrainingSet()
    scores = []
    for tier, bridge, score in groups:
        ds.features.append({"is_bridge": bridge})
        ds.tiers.append(tier)
        ds.labels.append(0)
        scores.append(score)
    ds.sizes = [len(groups)]
    return ds, scores


def test_fairness_passes_when_every_group_is_ranked_alike(settings):
    settings.RANKER_FAIRNESS_MIN_GROUP = 3
    rows = [(t, b, s) for s in range(12) for t in (1, 2, 3) for b in (0, 1)]
    ds, scores = make_scored(rows)
    result = training.fairness(ds, [float(x) for x in scores[: len(rows)]])
    assert result["passed"] and result["college_tier"]["gap"] <= 0.1


def test_fairness_fails_when_a_college_tier_is_pushed_down(settings):
    settings.RANKER_FAIRNESS_MIN_GROUP = 3
    rows = [(1 if i % 2 else 3, i % 3 == 0, float(i + (100 if i % 2 else 0))) for i in range(60)]  # tier 1 always scores higher
    ds, scores = make_scored(rows)
    result = training.fairness(ds, [r[2] for r in rows])
    assert not result["passed"] and result["college_tier"]["gap"] > 0.3


def test_fairness_that_cannot_be_checked_fails(settings):
    settings.RANKER_FAIRNESS_MIN_GROUP = 3
    ds, _ = make_scored([(1, 0, float(i)) for i in range(10)])  # one tier, no Bridge rows: nothing to compare
    result = training.fairness(ds, [float(i) for i in range(10)])
    assert result["college_tier"]["gap"] is None and not result["passed"]


def test_tiers_come_from_the_file_and_unknown_colleges_are_left_out():
    assert training.tier_of("kaveri institute of technology") == 3 and training.tier_of("Madras School of Engineering") == 1
    assert training.tier_of("Somewhere Unlisted") is None and training.tier_of("") is None


# -- train_ranker ---------------------------------------------------------------------------------------------
def test_train_skips_when_there_is_too_little_data(lists, settings):
    assert "not enough data" in run("train_ranker")
    assert not ModelVersion.objects.exists()


def test_train_skips_when_nobody_has_asked_for_an_intro(shown):
    FeatureSnapshot.objects.update(shown_at=timezone.now())
    from django.test import override_settings

    with override_settings(RANKER_MIN_GROUPS=1):
        assert "nothing to learn from" in run("train_ranker")
    assert not ModelVersion.objects.exists()


def test_the_pipeline_runs_end_to_end_on_simulated_data(sim, settings):
    settings.RANKER_MIN_GROUPS = 10
    settings.RANKER_FAIRNESS_MIN_GROUP = 5
    out = run("train_ranker")
    mv = ModelVersion.objects.get()
    assert mv.status == "candidate" and mv.data_source == "simulated" and mv.simulated_rows > 0 and mv.real_rows == 0
    assert mv.trained_env == "dev" and mv.version in out
    data = get_storage().get("private", mv.file_path)
    assert hashlib.sha256(data).hexdigest() == mv.sha256
    saved = json.loads(get_storage().get("private", f"ml/models/{mv.version}/metrics.json"))
    assert set(saved["model"]) == {"ndcg@10", "acceptance@3", "eval_agreement"} and saved["labels"]
    assert saved["groups"]["test"] > 0 and "college_tier" in saved["fairness"]
    assert Event.objects.filter(type="ranker.trained", target_id=mv.pk).exists()
    assert "already trained" in run("train_ranker")  # same data: no second model
    assert ModelVersion.objects.count() == 1


def test_a_trained_model_can_be_put_in_shadow_and_then_logs_scores_in_compute_matches(sim, settings, make_member):
    settings.RANKER_MIN_GROUPS = 10
    run("train_ranker")
    mv = registry.promote(ModelVersion.objects.get(), "shadow")  # dev: allowed for a simulated model
    seeker, giver = make_member("founder"), make_member("mentor")
    need(seeker, "seo")
    offer(giver, "seo")
    services.compute_all()
    row = MatchResult.objects.get(member=seeker)
    assert row.arm == "rule" and row.model_version == mv.version and row.model_score is not None


def test_in_production_a_simulated_only_history_trains_nothing(sim, settings):
    settings.ENV = "production"
    settings.RANKER_MIN_GROUPS = 10
    assert "not enough data" in run("train_ranker")
    assert not ModelVersion.objects.exists()


def test_build_training_set_command_reports_counts_and_writes_a_csv(sim, tmp_path):
    out = run("build_training_set", "--out", str(tmp_path / "t.csv"))
    assert "simulated" in out and (tmp_path / "t.csv").read_text().startswith("snapshot_id,label,comp_they_give")


# -- the A/B report ----------------------------------------------------------------------------------------------
def test_arm_report_counts_shown_requested_and_accepted_per_arm(shown):
    viewer, c, at = shown
    FeatureSnapshot.objects.filter(candidate__in=c[3:]).update(
        arm="model", model_version="v9", shown_at=timezone.now() - timedelta(days=1)
    )
    intro(viewer, c[0], at + timedelta(hours=1), "accepted")
    intro(viewer, c[3], timezone.now() - timedelta(hours=20), "declined")
    report = {(r["arm"], r["model_version"]): r for r in arm_report(28)}
    assert report[("rule", "")]["shown"] == 3 and report[("rule", "")]["accepted"] == 1
    assert (
        report[("model", "v9")]["shown"] == 2
        and report[("model", "v9")]["requested"] == 1
        and report[("model", "v9")]["accepted"] == 0
    )
    assert "model" in run("ranker_report")


def test_arm_report_leaves_out_the_simulation(sim):
    assert arm_report(28) == []
    assert "no snapshots" in run("ranker_report")
