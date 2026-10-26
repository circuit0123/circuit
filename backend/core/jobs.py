"""Scheduled jobs: one base class, so every job starts, skips, runs, ends and fails the same way.

A job is a management command that subclasses JobCommand and implements `run()`. The base class adds what every job needs and
nobody should rewrite (PRODUCTION.md §14 rows 10 and 20):

  1. one JSON log line when it starts (job.start);
  2. if its feature flag is off for everyone: `job.skipped` with reason "flag off", prints "skipped: flag off", exits 0
     (CLAUDE.md "Feature flags": nothing is deleted, nothing runs);
  3. a lease in the database (core.models.JobRun): if another run holds it, `job.skipped` "already running", exit 0;
  4. `run()`;
  5. `job.end` with how long it took and its counts, or `job.failed` and a non-zero exit so Cloud Run retries it.

Counts and durations only, never names, emails or tokens (CLAUDE.md privacy rules).
"""

import time
from datetime import timedelta

import structlog
from django.core.management.base import BaseCommand
from django.utils import timezone

from core import flags
from core.models import JobRun

log = structlog.get_logger("jobs")


def acquire(name: str, minutes: int) -> bool:
    """Take the job's lease for `minutes`. True for exactly one of any number of simultaneous callers.

    The UPDATE ... WHERE running_until <= now is a single statement, so Postgres lets one caller change the row and the other
    sees it already moved. Not a read followed by a write: that would let two callers both read "free"."""
    now = timezone.now()
    JobRun.objects.get_or_create(name=name, defaults={"running_until": now - timedelta(seconds=1)})
    taken = JobRun.objects.filter(name=name, running_until__lte=now).update(
        running_until=now + timedelta(minutes=minutes), last_started_at=now, last_status="running"
    )
    return taken == 1


def release(name: str, status: str) -> None:
    now = timezone.now()
    JobRun.objects.filter(name=name).update(running_until=now, last_finished_at=now, last_status=status)


class JobCommand(BaseCommand):
    """Subclass, set `flag` / `lock_minutes` if needed, and implement `run()` (return a dict of counts)."""

    flag: str | None = None  # a name from core/flags.py; the job does nothing while that feature is off for everyone
    lock_minutes = 30  # longer than the job ever takes, shorter than "stuck": a killed run frees itself after this

    def run(self) -> dict:
        """Do the work; return counts. Return {"skip_reason": "..."} (plus a "message" if you override summary) when there was nothing to do."""
        raise NotImplementedError

    def summary(self, result: dict) -> str:
        """The one line printed when the job ends. Override to keep a friendlier sentence."""
        return " ".join(f"{k}={v}" for k, v in result.items())

    @property
    def job_name(self) -> str:
        return type(self).__module__.rsplit(".", 1)[-1]  # the command's file name, e.g. "compute_matches"

    def handle(self, *args, **options):
        name = self.job_name
        started = time.monotonic()
        log.info("job.start", job=name)
        if self.flag and not flags.enabled(self.flag):
            log.info("job.skipped", job=name, reason="flag off", flag=self.flag)
            self.stdout.write("skipped: flag off")
            return
        if not acquire(name, self.lock_minutes):
            log.info("job.skipped", job=name, reason="already running")
            self.stdout.write("skipped: already running")
            return
        try:
            result = self.run()
        except BaseException as exc:  # includes a timeout signal: free the lease so the retry is not turned away
            release(name, "failed")
            log.error("job.failed", job=name, error=type(exc).__name__, ms=round((time.monotonic() - started) * 1000))
            raise
        ms = round((time.monotonic() - started) * 1000)
        if result.get("skip_reason"):  # the job looked and found nothing to do (e.g. not enough data to train on)
            release(name, "skipped")
            log.info("job.skipped", job=name, reason=result["skip_reason"], ms=ms)
        else:
            release(name, "ok")
            log.info("job.end", job=name, ms=ms, **{k: v for k, v in result.items() if isinstance(v, int | float | bool)})
        self.stdout.write(self.summary(result))
