from apps.circuits import services as circuits
from apps.intros import services as intros
from core.jobs import JobCommand


class Command(JobCommand):
    help = "Mark past-deadline items expired (introductions, circuits). Run every 15 minutes; safe to run again."
    lock_minutes = 10
    # No flag on purpose: a circuit already in flight still expires when `circuits` is switched off (CLAUDE.md "Feature flags").

    def run(self) -> dict:
        return {"introductions_expired": intros.expire_due(), "circuits_expired": circuits.expire_due()}

    def summary(self, result: dict) -> str:
        return f"introductions expired: {result['introductions_expired']}\ncircuits expired: {result['circuits_expired']}"
