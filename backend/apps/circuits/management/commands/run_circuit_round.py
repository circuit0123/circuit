from apps.circuits.services import run_round
from core.jobs import JobCommand


class Command(JobCommand):
    help = "Run this week's circuit round: find loops of three, propose the best ones. Safe to run again."
    flag = "circuits"

    def run(self) -> dict:
        return run_round(triggered_by="schedule")

    def summary(self, result: dict) -> str:
        return f"{result['week']}: {result['edges']} possible handovers, {result['loops_found']} loops, {result['circuits_created']} proposed"
