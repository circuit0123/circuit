from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.matching.ranker import simulation


class Command(BaseCommand):
    help = (
        "Create a synthetic network (members with hidden tastes, who see lists and answer intros) to test the ML pipeline end to "
        "end. Never in production. Does nothing if a simulation already exists, unless --reset."
    )

    def add_arguments(self, parser):
        parser.add_argument("--members", type=int, default=400)
        parser.add_argument("--rounds", type=int, default=14, help="days of simulated activity")
        parser.add_argument("--seed", type=int, default=7)
        parser.add_argument("--reset", action="store_true", help="delete the existing simulation first")

    def handle(self, *args, **opts):
        if settings.ENV == "production":
            raise CommandError("simulate_network never runs in production")
        if opts["reset"]:
            self.stdout.write(f"removed {simulation.remove()} rows (simulated members and what hangs off them)")
        elif simulation.exists():
            self.stdout.write("skipped: a simulation already exists (use --reset to rebuild it)")
            return
        stats = simulation.simulate(opts["members"], opts["rounds"], opts["seed"])
        self.stdout.write(
            f"simulated {stats['members']} members over {stats['rounds']} days: {stats['snapshots']} snapshots, {stats['intros']} intros"
        )
