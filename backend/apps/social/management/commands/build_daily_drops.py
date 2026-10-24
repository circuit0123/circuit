from django.core.management.base import BaseCommand

from apps.social.drop import build_all
from core import flags


class Command(BaseCommand):
    help = "Build today's Daily Drop (3 people per member) from the precomputed matches. Run at 08:00 IST. Safe to run again."

    def handle(self, *args, **options):
        if not flags.enabled("daily_drop"):
            self.stdout.write("skipped: flag off")
            return
        stats = build_all()
        self.stdout.write(f"Drop day {stats['day']}: {stats['built']} drops built, {stats['skipped']} members skipped")
