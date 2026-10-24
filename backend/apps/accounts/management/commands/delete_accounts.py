import structlog
from django.core.management.base import BaseCommand

from apps.accounts import deletion

log = structlog.get_logger("jobs")


class Command(BaseCommand):
    help = (
        "Finish the account deletions members asked for: sign-in, files, profile and personal data removed, content shown as "
        "'Deleted member'. Run every 5 minutes; safe to run again (a finished account is skipped, a failed one is retried)."
    )

    def handle(self, *args, **options):
        result = deletion.erase_requested()
        log.info("delete_accounts", **result)
        self.stdout.write(" ".join(f"{k}={v}" for k, v in result.items()))
