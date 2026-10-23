from django.core.management.base import BaseCommand

from apps.matching.services import compute_all


class Command(BaseCommand):
    help = "Recompute every member's matches into match_results and the Redis cache. Safe to run again."

    def handle(self, *args, **options):
        stats = compute_all()
        self.stdout.write(
            f"{stats['members']} members, {stats['matches']} matches ({stats['bridge_matches']} bridge), "
            f"{stats['embedded']} embeddings filled, {stats['seconds']}s"
        )
