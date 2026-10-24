"""Model life cycle and the production guard (CLAUDE.md "Matching ML": a simulation-only model is NEVER served to real users)."""

import pytest
from django.contrib import admin, messages
from django.db import IntegrityError, transaction

from apps.matching import services
from apps.matching.models import MatchResult, ModelVersion
from apps.matching.ranker import registry
from apps.matching.ranker.serving import load_serving
from apps.moderation.models import AuditLog
from tests.unit.ranker_helpers import make_model, store_booster

pytestmark = pytest.mark.django_db
SIMULATED = dict(data_source="simulated", real_rows=0, simulated_rows=900, trained_env="dev")
MIXED = dict(data_source="mixed", real_rows=100, simulated_rows=800, trained_env="dev")


# -- the life cycle -------------------------------------------------------------------------------------
def test_order_is_candidate_shadow_ab_active_retired(settings):
    settings.ENV = "dev"
    mv = make_model(trained_env="dev")
    for step in ("shadow", "ab", "active", "retired"):
        mv = registry.promote(mv, step)
        assert mv.status == step


@pytest.mark.parametrize("to", ["ab", "active"])
def test_a_candidate_cannot_skip_shadow(to, settings):
    settings.ENV = "dev"
    with pytest.raises(registry.PromotionRefused, match="cannot go from candidate"):
        registry.promote(make_model(trained_env="dev"), to)


def test_ab_and_active_need_to_beat_the_rule_and_pass_fairness(settings):
    settings.ENV = "dev"
    weak = registry.promote(make_model(trained_env="dev", beats_rule=False), "shadow")
    with pytest.raises(registry.PromotionRefused, match="does not beat the rule"):
        registry.promote(weak, "ab")
    unfair = registry.promote(make_model(trained_env="dev", fairness_passed=False), "shadow")  # replaces the weak one in the slot
    with pytest.raises(registry.PromotionRefused, match="fairness"):
        registry.promote(unfair, "ab")
    assert ModelVersion.objects.get(pk=weak.pk).status == "retired"


def test_a_new_model_retires_the_one_in_its_slot_but_not_other_slots(settings):
    settings.ENV = "dev"
    active = make_model(trained_env="dev")
    for step in ("shadow", "ab", "active"):
        active = registry.promote(active, step)
    first = registry.promote(make_model(trained_env="dev"), "shadow")  # shadows next to the active model
    assert ModelVersion.objects.get(pk=active.pk).status == "active"
    second = registry.promote(make_model(trained_env="dev"), "shadow")
    assert ModelVersion.objects.get(pk=first.pk).status == "retired" and second.status == "shadow"


def test_the_database_allows_one_model_per_serving_slot(settings):
    settings.ENV = "dev"
    make_model(trained_env="dev", status="shadow")
    with pytest.raises(IntegrityError), transaction.atomic():
        make_model(trained_env="dev", status="shadow")


def test_every_status_change_is_audit_logged_and_recorded(settings, staff_request):
    from apps.events.models import Event

    settings.ENV = "dev"
    _, staff = staff_request
    mv = registry.promote(make_model(trained_env="dev"), "shadow", staff)
    log = AuditLog.objects.get(action="ranker.shadow")
    assert log.actor == staff and log.target_id == str(mv.pk) and log.payload["from"] == "candidate"
    assert Event.objects.filter(type="ranker.promoted", target_id=mv.pk).exists()


# -- the production guard: the required proof ---------------------------------------------------------------
@pytest.mark.parametrize(
    "trained_on", [SIMULATED, MIXED, dict(data_source="real", simulated_rows=5), dict(trained_env="staging")]
)
@pytest.mark.parametrize("to", ["shadow", "ab", "active"])
def test_a_model_not_trained_on_real_production_data_can_never_be_promoted_in_production(settings, trained_on, to):
    settings.ENV = "dev"  # the model is trained and saved in dev, where simulation is allowed
    mv = make_model(
        **{**dict(trained_env="dev"), **trained_on}, beats_rule=True, fairness_passed=True
    )  # even with perfect metrics
    settings.ENV = "production"
    if to != "shadow":  # walk it as far as the order allows, to prove each step refuses
        mv.status = "shadow"
        ModelVersion.objects.filter(pk=mv.pk).update(status="shadow")  # forced by hand, bypassing save()
        if to == "active":
            ModelVersion.objects.filter(pk=mv.pk).update(status="ab")
        mv.refresh_from_db()
    with pytest.raises(registry.PromotionRefused, match="can never serve members in production"):
        registry.promote(mv, to)
    assert ModelVersion.objects.get(pk=mv.pk).status != to


def test_the_admin_action_cannot_promote_a_simulated_model_in_production(settings, staff_request):
    settings.ENV = "dev"
    mv = make_model(**SIMULATED)
    settings.ENV = "production"
    request, _ = staff_request
    model_admin = admin.site._registry[ModelVersion]
    model_admin.to_shadow(request, ModelVersion.objects.filter(pk=mv.pk))
    sent = list(messages.get_messages(request))
    assert any(m.level == messages.ERROR and "trained on simulated data" in m.message for m in sent)
    assert ModelVersion.objects.get(pk=mv.pk).status == "candidate"
    assert not AuditLog.objects.filter(action__startswith="ranker.").exists()


def test_save_refuses_a_simulated_model_in_a_serving_status_in_production(settings):
    settings.ENV = "dev"
    mv = make_model(**SIMULATED)
    settings.ENV = "production"
    mv.status = "active"
    with pytest.raises(ValueError, match="simulated"):
        mv.save()
    with pytest.raises(ValueError, match="simulated"):
        make_model(**SIMULATED, status="shadow")
    assert ModelVersion.objects.get(pk=mv.pk).status == "candidate"


def test_even_a_status_forced_in_the_database_is_not_served_in_production(settings, make_member, lists):
    """queryset.update skips save(). compute_matches checks the guard again when it loads models, and uses the rule."""
    settings.ENV = "dev"
    mv = store_booster(make_model(**SIMULATED, file_path="ml/models/forced/model.txt"))
    settings.ENV = "production"
    ModelVersion.objects.filter(pk=mv.pk).update(status="active")
    serving = load_serving()
    assert serving.active is None and serving.ab is None and serving.shadow is None


def test_a_forced_simulated_model_leaves_production_matches_on_the_rule(settings, make_member, lists):
    from tests.api.test_matches import need, offer

    settings.ENV = "dev"
    mv = store_booster(make_model(**SIMULATED, file_path="ml/models/forced2/model.txt"))
    seeker, giver = make_member("founder"), make_member("mentor")
    need(seeker, "seo")
    offer(giver, "seo")
    settings.ENV = "production"
    ModelVersion.objects.filter(pk=mv.pk).update(status="active")
    services.compute_all()
    row = MatchResult.objects.get(member=seeker)
    assert row.arm == "rule" and row.model_version == "" and row.model_score is None


def test_a_model_trained_on_real_production_data_can_be_promoted_in_production(settings):
    """The positive control: the guard blocks the wrong models, not every model."""
    settings.ENV = "production"
    mv = make_model()  # real data, trained in production, beats the rule, passes fairness
    for step in ("shadow", "ab", "active"):
        mv = registry.promote(mv, step)
        assert mv.status == step


def test_other_environments_may_serve_a_simulated_model(settings):
    settings.ENV = "staging"
    mv = registry.promote(make_model(**{**SIMULATED, "trained_env": "staging"}), "shadow")
    assert mv.status == "shadow"


# -- the admin ---------------------------------------------------------------------------------------------------
def test_the_admin_action_moves_a_model_and_is_audit_logged(settings, staff_request):
    settings.ENV = "dev"
    request, staff = staff_request
    mv = make_model(trained_env="dev")
    admin.site._registry[ModelVersion].to_shadow(request, ModelVersion.objects.filter(pk=mv.pk))
    assert ModelVersion.objects.get(pk=mv.pk).status == "shadow"
    assert AuditLog.objects.get(action="ranker.shadow").actor == staff
    assert any(m.level == messages.SUCCESS for m in messages.get_messages(request))


def test_model_versions_cannot_be_added_edited_or_deleted_by_hand(rf):
    model_admin = admin.site._registry[ModelVersion]
    request = rf.get("/")
    assert not model_admin.has_add_permission(request) and not model_admin.has_change_permission(request)
    assert not model_admin.has_delete_permission(request)


def test_the_admin_report_shows_how_members_saw_a_model():
    mv = make_model(trained_env="dev")
    assert admin.site._registry[ModelVersion].ab_report(mv) == "Nothing shown yet."
