from apps.matching.services import compute_all
from core.jobs import JobCommand


class Command(JobCommand):
    help = "Recompute every member's matches into match_results and the Redis cache. Safe to run again."
    lock_minutes = 40  # no flag: matching is identical whatever the flags (tested)

    def run(self) -> dict:
        return compute_all()

    def summary(self, result: dict) -> str:
        return (
            f"{result['members']} members, {result['matches']} matches ({result['bridge_matches']} bridge), "
            f"{result['embedded']} embeddings filled, {result['seconds']}s"
        )
