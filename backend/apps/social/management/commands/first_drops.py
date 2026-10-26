from apps.social.drop import build_first_drops
from core.jobs import JobCommand


class Command(JobCommand):
    help = (
        "Give members who just finished sign-up their first Daily Drop now instead of at 08:00 tomorrow: match just them, then build "
        "their drop. Runs every 5 minutes with the other frequent jobs. Each member is tried once. Safe to run again."
    )
    flag = "daily_drop"

    def run(self) -> dict:
        return build_first_drops()

    def summary(self, result: dict) -> str:
        return f"First drops: {result['waiting']} waiting, {result['built']} built"
