from django.core.management.base import BaseCommand

from apps.matching.ranker.report import arm_report


class Command(BaseCommand):
    help = "Acceptance-rate comparison per ranker arm and model version (real members only)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=28)

    def handle(self, *args, **opts):
        rows = arm_report(opts["days"])
        if not rows:
            self.stdout.write("no snapshots in this period")
        for r in rows:
            self.stdout.write(
                f"{r['arm']:<6} {r['model_version'] or '-':<24} shown={r['shown']} requested={r['requested']} ({r['request_rate']:.1%}) "
                f"accepted={r['accepted']} ({r['accept_rate']:.1%})"
            )
