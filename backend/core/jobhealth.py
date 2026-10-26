"""Is every scheduled job still running? (PRODUCTION.md §8: "Jobs: any job fails twice in a row" and RUNBOOK "A job is overdue".)

A job is OVERDUE when it has had no success for twice its interval. The interval comes from the deploy file: scripts/gcp.py reads each
job's cron in deploy/gcp/app.toml and hands the result to the app as JOB_INTERVALS ("compute_matches:1440,expire_items:5,..."), so
the schedule is written down once. In dev and tests JOB_INTERVALS is empty and nothing is expected.

Failure is not the only way a job goes wrong: a run killed for memory logs nothing, and a dead Scheduler trigger runs nothing. Both look the same
from here: the last success gets old. `check_jobs` (every 5 minutes) logs `job.overdue` for each, and the alert policy in
infra/monitoring/ turns that line into a phone alert.

A job whose feature flag is off is not expected to run and is never overdue.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.core.management import get_commands, load_command_class
from django.utils import timezone

from core import flags
from core.models import JobRun

OVERDUE_FACTOR = 2


@dataclass
class JobStatus:
    name: str
    interval_minutes: int
    last_status: str
    last_started_at: datetime | None
    last_finished_at: datetime | None
    last_success_at: datetime | None
    last_error: str
    overdue: bool
    reason: str  # "" | "flag off" | "never ran" | "no success for 3h 10m (expected every 5m)"


def expected_intervals() -> dict[str, int]:
    return dict(settings.JOB_INTERVALS)


def _flag_of(job: str) -> str | None:
    app = get_commands().get(job)
    if app is None:
        return None
    return getattr(load_command_class(app, job), "flag", None)


def ensure_rows() -> int:
    """Make sure every expected job has a row, so a job that has NEVER run is noticed too (its clock starts when first seen)."""
    created = 0
    for name in expected_intervals():
        _, was_created = JobRun.objects.get_or_create(
            name=name, defaults={"running_until": timezone.now() - timedelta(seconds=1)}
        )
        created += was_created
    return created


def _ago(delta: timedelta) -> str:
    minutes = int(delta.total_seconds() // 60)
    days, rest = divmod(minutes, 1440)
    hours, mins = divmod(rest, 60)
    if days:
        return f"{days}d {hours}h"
    return f"{hours}h {mins}m" if hours else f"{mins}m"


def _every(minutes: int) -> str:
    return f"{minutes // 1440}d" if minutes % 1440 == 0 else f"{minutes // 60}h" if minutes % 60 == 0 else f"{minutes}m"


def status(now: datetime | None = None) -> list[JobStatus]:
    if not expected_intervals():
        return []  # a laptop: nothing is scheduled, so there is nothing to be late (and no query to run)
    now = now or timezone.now()
    rows = {r.name: r for r in JobRun.objects.all()}
    out = []
    for name, minutes in sorted(expected_intervals().items()):
        row = rows.get(name)
        flag = _flag_of(name)
        overdue, reason = False, ""
        if flag and not flags.enabled(flag):
            reason = "flag off"
        elif row is None:
            reason = "never ran"  # no row yet: check_jobs creates it on its next run and starts the clock
        else:
            since = row.last_success_at or row.first_seen_at
            if now - since > timedelta(minutes=OVERDUE_FACTOR * minutes):
                overdue = True
                reason = (
                    f"no success for {_ago(now - since)} (expected every {_every(minutes)})"
                    if row.last_success_at
                    else f"never succeeded in {_ago(now - since)} (expected every {_every(minutes)})"
                )
        out.append(
            JobStatus(
                name=name,
                interval_minutes=minutes,
                last_status=row.last_status if row else "",
                last_started_at=row.last_started_at if row else None,
                last_finished_at=row.last_finished_at if row else None,
                last_success_at=row.last_success_at if row else None,
                last_error=row.last_error if row else "",
                overdue=overdue,
                reason=reason,
            )
        )
    return out


def overdue() -> list[JobStatus]:
    return [s for s in status() if s.overdue]
