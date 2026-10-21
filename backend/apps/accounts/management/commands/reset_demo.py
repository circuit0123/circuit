from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from seed.build import run


class Command(BaseCommand):
    help = "Wipe and reseed demo data (dev and demo only). Idempotent: same input, same rows."

    def handle(self, *args, **options):
        if settings.ENV not in ("dev", "demo"):
            raise CommandError(f"reset_demo refuses to run when ENV={settings.ENV}")
        counts = run(settings.SEED_CITY)
        self.stdout.write(self.style.SUCCESS(f"Seeded: {counts}"))
