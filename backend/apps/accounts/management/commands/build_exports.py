from apps.accounts import export
from core.jobs import JobCommand


class Command(JobCommand):
    help = "Build the data exports members asked for and email their download links. Run every 5 minutes; safe to run again."
    lock_minutes = 10

    def run(self) -> dict:
        return export.build_pending()
