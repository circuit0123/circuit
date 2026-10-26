from core.email import send_due
from core.jobs import JobCommand


class Command(JobCommand):
    help = (
        "Send pending emails that are due (retries with backoff) and delete finished ones older than EMAIL_KEEP_DAYS. Idempotent."
    )
    lock_minutes = 10

    def run(self) -> dict:
        return send_due()

    def summary(self, result: dict) -> str:
        return f"due={result['due']} sent={result['sent']} purged={result['purged']}"
