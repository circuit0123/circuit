"""Log what was shown, with the exact features the ranker saw (feature_snapshots).

Best effort: a failure here is logged and swallowed, because showing the page matters more than the log. Nothing is
logged when either person is under 18: behavioural training data is never collected about children.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import structlog
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.matching.models import FeatureSnapshot, MatchResult

log = structlog.get_logger("ranker")


def ist_day(now: datetime) -> date:
    return now.astimezone(ZoneInfo(settings.DROP_TZ)).date()


def _write(rows: list[FeatureSnapshot]) -> None:
    if rows:
        with transaction.atomic():  # a savepoint when already inside a request transaction
            FeatureSnapshot.objects.bulk_create(rows, ignore_conflicts=True)  # same viewer, candidate, surface, day: one row


def log_matches(viewer, shown: list[tuple[int, int]], now: datetime | None = None) -> None:
    """`shown` is (candidate id, position on screen). Features come from the MatchResult the ranker stored."""
    if viewer.is_minor or not shown:
        return
    try:
        now = now or timezone.now()
        place = dict(shown)
        results = MatchResult.objects.filter(member=viewer, candidate_id__in=place, candidate__is_minor=False)
        _write(
            [
                FeatureSnapshot(
                    viewer=viewer, candidate_id=r.candidate_id, surface="matches", model_version=r.model_version, arm=r.arm,
                    features=r.features, position=place[r.candidate_id], rule_score=r.score, model_score=r.model_score,
                    shown_at=now, shown_on=ist_day(now),
                )
                for r in results
                if r.features  # rows computed before Stage 4c have none
            ]
        )  # fmt: skip
    except Exception as exc:  # noqa: BLE001
        log.warning("snapshot_failed", surface="matches", error=type(exc).__name__)


def log_drop(viewer, cards: list[tuple[int, int, dict]], day: date, now: datetime | None = None) -> None:
    """`cards` is (candidate id, card position, snap) where snap was copied from the MatchResult when the drop was built."""
    if viewer.is_minor or not cards:
        return
    try:
        now = now or timezone.now()
        _write(
            [
                FeatureSnapshot(
                    viewer=viewer, candidate_id=cid, surface="daily_drop", model_version=snap.get("model_version", ""),
                    arm=snap.get("arm", "rule"), features=snap["features"], position=pos, rule_score=snap["rule_score"],
                    model_score=snap.get("model_score"), shown_at=now, shown_on=day,
                )
                for cid, pos, snap in cards
                if snap.get("features")
            ]
        )  # fmt: skip
    except Exception as exc:  # noqa: BLE001
        log.warning("snapshot_failed", surface="daily_drop", error=type(exc).__name__)
