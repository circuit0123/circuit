"""The production rule for learned rankers, in one place with no heavy imports.

A model trained on simulated people tells us how the pipeline behaves, not what real members want. In production only a
model trained there, on real data alone, may be in front of members (shadow, A/B or active). Everything that can change
a model's status or serve one calls this: the registry, `ModelVersion.save()`, and the loader used by `compute_matches`.
"""

from django.conf import settings


def refusal(mv) -> str | None:
    """Why this model may not be in its current status here, or None if that is fine."""
    if mv.status in ("candidate", "retired") or settings.ENV != "production":
        return None
    if mv.data_source != "real" or mv.simulated_rows:
        return f"{mv.version}: trained on simulated data, so it can never serve members in production"
    if mv.trained_env != "production":
        return f"{mv.version}: trained in {mv.trained_env}, so it can never serve members in production"
    return None
