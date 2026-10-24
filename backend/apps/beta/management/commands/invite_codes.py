from django.core.management.base import BaseCommand, CommandError

from apps.beta import services
from apps.beta.models import InviteCode
from apps.moderation.models import AuditLog
from apps.organisations.models import Organisation


class Command(BaseCommand):
    help = "Create invite codes for the beta and print them with their one-tap links. Audit-logged."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=1)
        parser.add_argument("--uses", type=int, default=1, help="how many people may use each code")
        parser.add_argument("--days", type=int, default=None, help="expire after this many days (default: never)")
        parser.add_argument("--org", type=int, default=None, help="organisation id: whoever redeems the code joins it")
        parser.add_argument("--note", default="", help="who or what the codes are for")

    def handle(self, *args, count, uses, days, org, note, **options):
        if not 1 <= count <= 500:
            raise CommandError("--count must be between 1 and 500")
        if uses < 1:
            raise CommandError("--uses must be at least 1")
        if days is not None and days < 1:
            raise CommandError("--days must be at least 1")
        organisation = None
        if org is not None:
            organisation = Organisation.objects.filter(pk=org).first()
            if organisation is None:
                raise CommandError(f"No organisation with id {org}")
        codes = [
            services.create_code(kind=InviteCode.Kind.ADMIN, max_uses=uses, days=days, organisation=organisation, note=note)
            for _ in range(count)
        ]
        AuditLog.objects.create(
            actor=None,
            action="invite.create",
            target_type="beta.invitecode",
            target_id=",".join(str(c.pk) for c in codes)[:40],
            payload={"count": count, "uses": uses, "days": days, "organisation_id": org, "via": "cli"},
        )
        for c in codes:
            self.stdout.write(f"{c.code}  {services.invite_link(c.code)}")
