from django.core.management.base import BaseCommand

from apps.beta.funnel import funnel, render


class Command(BaseCommand):
    help = "Sign-up funnel per source: clicks, signed up, beta access, onboarding done, first match action. Counts under 5 are hidden."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=None, help="only the last N days (default: all time)")

    def handle(self, *args, **opts):
        self.stdout.write(render(funnel(opts["days"])))
