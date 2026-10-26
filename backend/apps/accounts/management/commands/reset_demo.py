from django.conf import settings
from django.core.management.base import CommandError

from core.jobs import JobCommand
from seed.build import run


class Command(JobCommand):
    help = "Wipe and reseed demo data (dev and demo only). Idempotent: same input, same rows."

    def run(self) -> dict:
        if settings.ENV not in ("dev", "demo"):
            raise CommandError(f"reset_demo refuses to run when ENV={settings.ENV}")
        return {"counts": run(settings.SEED_CITY)}

    def summary(self, result: dict) -> str:
        return self.style.SUCCESS(f"Seeded: {result['counts']}")
