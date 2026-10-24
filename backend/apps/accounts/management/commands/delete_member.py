from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts import deletion
from apps.accounts.models import Member


class Command(BaseCommand):
    help = "DEV ONLY: delete one member's account right now, the way the delete_accounts job does. Use: make delete-account MEMBER=<id>."

    def add_arguments(self, parser):
        parser.add_argument("--member", type=int, required=True)
        parser.add_argument("--yes", action="store_true", help="do not ask for confirmation")

    def handle(self, *args, **options):
        if settings.ENV != "dev":
            raise CommandError("delete_member is for local development only. Members delete their account in the app.")
        member = Member.objects.filter(pk=options["member"]).first()
        if member is None:
            raise CommandError(f"No member with id {options['member']}")
        if (
            not options["yes"]
            and input(f"Delete member {member.pk} ({member.role}) for good? Type DELETE to confirm: ") != "DELETE"
        ):
            raise CommandError("Cancelled. Nothing was deleted.")
        deletion.request_deletion(member)
        self.stdout.write(f"member {member.pk}: {deletion.erase(member)}")
