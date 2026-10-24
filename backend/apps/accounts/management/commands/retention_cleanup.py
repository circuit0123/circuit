from django.core.management.base import BaseCommand

from apps.accounts import retention


class Command(BaseCommand):
    help = (
        "Daily clean-up: purge accounts that never accepted the terms (30 days), delete expired export files and old rejected "
        "waitlist entries. Logs counts only. Safe to run again. Request logs are kept 30 days in Cloud Logging, not here."
    )

    def handle(self, *args, **options):
        result = retention.run()
        self.stdout.write(" ".join(f"{k}={v}" for k, v in result.items()))
