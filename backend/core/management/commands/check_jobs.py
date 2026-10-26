import structlog

from core import jobhealth
from core.jobs import JobCommand

log = structlog.get_logger("jobs")


class Command(JobCommand):
    help = "Log job.overdue for every scheduled job with no success for twice its interval. Part of the every-5-min bundle."
    lock_minutes = 4
    # No flag, and its own `job.end` line is the heartbeat the "job watcher has stopped" alert waits for (infra/monitoring/).

    def run(self) -> dict:
        new = jobhealth.ensure_rows()
        late = jobhealth.overdue()
        for job in late:  # ERROR level: this line is what the overdue alert counts. Counts and names of jobs only, never data
            log.error("job.overdue", job=job.name, reason=job.reason, last_status=job.last_status)
        return {"jobs_watched": len(jobhealth.expected_intervals()), "overdue": len(late), "new_rows": new}
