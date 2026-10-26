from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Member
from core.auth import issue_demo_token


class Command(BaseCommand):
    help = "DEV/DEMO ONLY. Write demo sign-in tokens for seeded members, one per line, for `make load-test`."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=200)
        parser.add_argument("--out", required=True)

    def handle(self, *args, **opts):
        if not settings.DEMO_AUTH or settings.ENV not in ("dev", "demo"):
            raise CommandError(
                "load_test_tokens only works with DEMO_AUTH on in dev or demo. Staging needs real test accounts (RUNBOOK.md)."
            )
        members = Member.objects.filter(is_simulated=False, deleted_at__isnull=True, is_minor=False)
        others = list(
            members.filter(role__in=("founder", "mentor"))
            .order_by("pk")
            .values_list("auth_user_id", flat=True)[: max(opts["count"] // 5, 1)]
        )
        students = list(
            members.filter(role="student").order_by("pk").values_list("auth_user_id", flat=True)[: opts["count"] - len(others)]
        )
        ids = students + others
        if not ids:
            raise CommandError("No seeded members: run `make reset-demo` first.")
        with open(opts["out"], "w") as fh:
            fh.writelines(issue_demo_token(i) + "\n" for i in ids)
        self.stdout.write(f"wrote {len(ids)} tokens to {opts['out']} (valid 12 hours)")
