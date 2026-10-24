"""A/B report: for each ranker arm and model version, how many cards were shown and how many led to an intro or a yes.

Real members only (never the simulation), and never under-18s (their snapshots are not written).
"""

from datetime import timedelta

from django.utils import timezone

from apps.matching.models import FeatureSnapshot
from apps.matching.ranker.training import credit_labels


def arm_report(days: int = 28) -> list[dict]:
    since = timezone.now() - timedelta(days=days)
    rows = list(
        FeatureSnapshot.objects.filter(shown_at__gte=since, viewer__is_simulated=False)
        .exclude(surface="simulation")
        .values_list("id", "viewer_id", "candidate_id", "shown_at", "arm", "model_version")
    )
    labels = credit_labels([(r[0], r[1], r[2], r[3]) for r in rows])
    groups: dict[tuple[str, str], dict[str, int]] = {}
    for sid, _v, _c, _t, arm, version in rows:
        g = groups.setdefault((arm, version), {"shown": 0, "requested": 0, "accepted": 0})
        g["shown"] += 1
        label = labels.get(sid, 0)
        g["requested"] += label >= 1
        g["accepted"] += label >= 2
    return [
        {
            "arm": arm, "model_version": version, **g,
            "request_rate": round(g["requested"] / g["shown"], 4), "accept_rate": round(g["accepted"] / g["shown"], 4),
        }
        for (arm, version), g in sorted(groups.items())
    ]  # fmt: skip
