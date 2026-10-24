import structlog
from django.core.management.base import BaseCommand

from apps.accounts import export

log = structlog.get_logger("jobs")


class Command(BaseCommand):
    help = "Build the data exports members asked for and email their download links. Run every 5 minutes; safe to run again."

    def handle(self, *args, **options):
        result = export.build_pending()
        log.info("build_exports", **result)
        self.stdout.write(" ".join(f"{k}={v}" for k, v in result.items()))
