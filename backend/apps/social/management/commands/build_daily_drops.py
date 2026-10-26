from apps.social.drop import build_all
from core.jobs import JobCommand


class Command(JobCommand):
    help = "Build today's Daily Drop (3 people per member) from the precomputed matches. Run at 08:00 IST. Safe to run again."
    flag = "daily_drop"

    def run(self) -> dict:
        return build_all()

    def summary(self, result: dict) -> str:
        return f"Drop day {result['day']}: {result['built']} drops built, {result['skipped']} members skipped"
