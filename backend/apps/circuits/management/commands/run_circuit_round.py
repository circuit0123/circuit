from django.core.management.base import BaseCommand

from apps.circuits.services import run_round


class Command(BaseCommand):
    help = "Run this week's circuit round: find loops of three, propose the best ones. Safe to run again."

    def handle(self, *args, **options):
        r = run_round(triggered_by="schedule")
        self.stdout.write(
            f"{r['week']}: {r['edges']} possible handovers, {r['loops_found']} loops, {r['circuits_created']} proposed"
        )
