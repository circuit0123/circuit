from django.core.management.base import BaseCommand

from apps.intros import services as intros


class Command(BaseCommand):
    help = "Mark past-deadline items expired (introductions, circuits). Run every 15 minutes; safe to run again."

    def handle(self, *args, **options):
        self.stdout.write(f"introductions expired: {intros.expire_due()}")
