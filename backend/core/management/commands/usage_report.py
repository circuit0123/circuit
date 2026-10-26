from core import usage_report
from core.jobs import JobCommand


class Command(JobCommand):
    help = "Weekly free-tier usage: database, storage, emails, Redis, AI calls. Logs usage.warning at 70% of a limit. Mondays 09:00 IST."
    lock_minutes = 10

    def run(self) -> dict:
        self.readings, result = usage_report.run()
        return result

    def summary(self, result: dict) -> str:
        return usage_report.render(self.readings)
