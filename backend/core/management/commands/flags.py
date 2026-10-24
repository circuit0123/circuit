from django.core.management.base import BaseCommand, CommandError

from core import flags


class Command(BaseCommand):
    help = "List feature flags and their audience (off / testers / everyone), or change one: flags set <name> <audience>"

    def add_arguments(self, parser):
        parser.add_argument("action", nargs="?", choices=["list", "set"], default="list")
        parser.add_argument("name", nargs="?")
        parser.add_argument("audience", nargs="?")

    def handle(self, *args, action, name, audience, **options):
        if action == "set":
            if not (name and audience):
                raise CommandError("usage: manage.py flags set <name> <audience>")
            try:
                flags.set_audience(name, audience, via="cli")
            except ValueError as exc:
                raise CommandError(str(exc)) from exc
            self.stdout.write(f"{name} -> {audience}")
            return
        current, default, needs = flags.audiences(), flags.defaults(), flags.FLAGS
        for flag in flags.FLAGS:
            source = "default" if current[flag] == default[flag] and flag not in flags.overrides() else "override"
            dep = f"  (needs {needs[flag]})" if needs[flag] else ""
            self.stdout.write(f"{flag:<15} {current[flag]:<9} {source}{dep}")
