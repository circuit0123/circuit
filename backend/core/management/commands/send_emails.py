import structlog
from django.core.management.base import BaseCommand

from core.email import send_due

log = structlog.get_logger("jobs")


class Command(BaseCommand):
    help = (
        "Send pending emails that are due (retries with backoff) and delete finished ones older than EMAIL_KEEP_DAYS. Idempotent."
    )

    def handle(self, *args, **options):
        result = send_due()
        log.info("send_emails", **result)
        self.stdout.write(f"due={result['due']} sent={result['sent']} purged={result['purged']}")
