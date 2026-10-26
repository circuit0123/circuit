from apps.accounts import retention
from core.jobs import JobCommand


class Command(JobCommand):
    help = (
        "Daily clean-up: purge accounts that never accepted the terms (30 days), delete expired export files and old rejected "
        "waitlist entries. Logs counts only. Safe to run again. Request logs are kept 30 days in Cloud Logging, not here."
    )

    def run(self) -> dict:
        return retention.run()
