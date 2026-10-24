"""Which ranker orders which member's list, decided once per `compute_matches` run.

Rule: a member in the A/B share is ordered by the ab model; everyone else by the active model; with neither, by the
rule. A shadow model never orders anyone: its score is only logged. Any model that fails to load, fails the production
guard again (a status forced by hand), or errors while scoring is dropped and the rule is used instead.
"""

import hashlib
from dataclasses import dataclass

import structlog
from django.conf import settings

from apps.matching.models import ModelVersion
from apps.matching.ranker.guard import refusal
from apps.matching.ranker.model import ModelRanker
from apps.matching.ranker.rule import RuleRanker

log = structlog.get_logger("ranker")
RULE = RuleRanker()


@dataclass
class Serving:
    shadow: ModelRanker | None = None
    ab: ModelRanker | None = None
    active: ModelRanker | None = None

    def orders(self, member_id: int) -> ModelRanker | None:
        """The model that orders this member's list, or None for the rule."""
        if self.ab and in_ab_share(self.ab.version, member_id):
            return self.ab
        return self.active


def in_ab_share(version: str, member_id: int) -> bool:
    """Stable per model and member: the same member stays in the same arm for the life of a model."""
    h = int(hashlib.sha256(f"{version}:{member_id}".encode()).hexdigest()[:8], 16)
    return h % 100 < settings.RANKER_AB_PERCENT


def load_serving() -> Serving:
    out = Serving()
    for mv in ModelVersion.objects.filter(status__in=("shadow", "ab", "active")):
        reason = refusal(mv)
        if reason:
            log.error("ranker_refused", version=mv.version, status=mv.status, reason=reason)
            continue
        try:
            setattr(out, mv.status, ModelRanker.load(mv))
        except Exception as exc:  # noqa: BLE001 - any failure means the rule serves; never a broken page
            log.error("ranker_load_failed", version=mv.version, error=type(exc).__name__)
    return out
