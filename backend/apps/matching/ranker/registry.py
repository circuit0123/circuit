"""The model life cycle. This is the only code that changes a model's status.

    candidate -> shadow -> ab -> active -> retired     (any step can go straight to retired)

shadow: scores are logged next to the rule's, members see the rule. ab: the model orders the list for a share of
members. active: the model orders everyone's list. A new model entering a slot retires the one that held it.

Every step is checked against the production guard (guard.py). Going to ab or active also needs the quality gate: the
model beat the rule on NDCG@10 and the acceptance proxy without lowering eval-set agreement, and it passed fairness
(training.py decides those and records them on the row). Done by a super admin in Django admin; audit-logged.
"""

import structlog
from django.db import transaction

from apps.events.services import record
from apps.matching.models import ModelVersion
from apps.matching.ranker.guard import refusal
from apps.moderation.models import AuditLog

log = structlog.get_logger("ranker")
S = ModelVersion.Status
NEXT: dict[str, tuple[str, ...]] = {
    S.CANDIDATE: (S.SHADOW, S.RETIRED),
    S.SHADOW: (S.AB, S.RETIRED),
    S.AB: (S.ACTIVE, S.RETIRED),
    S.ACTIVE: (S.RETIRED,),
    S.RETIRED: (),
}


class PromotionRefused(Exception):
    """The reason is a sentence an admin can read."""


def promote(mv: ModelVersion, to: str, actor=None) -> ModelVersion:
    with transaction.atomic():
        mv = ModelVersion.objects.select_for_update().get(pk=mv.pk)
        frm = mv.status
        if to not in NEXT[frm]:
            raise PromotionRefused(f"{mv.version}: cannot go from {frm} to {to}")
        mv.status = to
        reason = refusal(mv)  # the production guard, before anything is written
        if reason:
            raise PromotionRefused(reason)
        if to in (S.AB, S.ACTIVE):
            if not mv.beats_rule:
                raise PromotionRefused(f"{mv.version}: it does not beat the rule ranker on every metric")
            if not mv.fairness_passed:
                raise PromotionRefused(f"{mv.version}: it failed the fairness check")
        if to in (S.SHADOW, S.AB, S.ACTIVE):
            for old in ModelVersion.objects.select_for_update().filter(status=to).exclude(pk=mv.pk):
                old.status = S.RETIRED
                old.save(update_fields=["status", "updated_at"])
                _log(old, S.RETIRED, to, actor, "ranker.retired", replaced_by=mv.version)
        mv.save(update_fields=["status", "updated_at"])
        _log(mv, to, frm, actor, "ranker.retired" if to == S.RETIRED else "ranker.promoted")
    return mv


def _log(mv: ModelVersion, to: str, frm: str, actor, event: str, **extra) -> None:
    AuditLog.objects.create(
        actor=actor if getattr(actor, "pk", None) else None,
        action=f"ranker.{to}",
        target_type="matching.modelversion",
        target_id=str(mv.pk),
        payload={"version": mv.version, "from": frm, "to": to, **extra},
    )
    record(event, target_type="model_version", target_id=mv.pk, version=mv.version, status_from=frm, status_to=to, **extra)
    log.info("ranker_status", version=mv.version, status_from=frm, status_to=to)
