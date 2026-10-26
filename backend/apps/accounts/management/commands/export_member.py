from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts import export
from apps.accounts.models import DataExport, Member
from core.devguard import require_local_database
from core.storage import LocalStorage, get_storage


class Command(BaseCommand):
    help = "DEV ONLY: build one member's data export right now and print where the zip is. Use: make export MEMBER=<id>."

    def add_arguments(self, parser):
        parser.add_argument("--member", type=int, required=True)

    def handle(self, *args, **options):
        if settings.ENV != "dev":
            raise CommandError("export_member is for local development only. Members request exports in the app.")
        require_local_database("export_member")
        member = Member.objects.filter(pk=options["member"]).first()
        if member is None:
            raise CommandError(f"No member with id {options['member']}")
        DataExport.objects.filter(member=member, status__in=["pending", "building"]).delete()
        row = DataExport.objects.create(member=member)
        status = export.build_one(row.pk)
        row.refresh_from_db()
        if status != "ready":
            raise CommandError(f"Export {status}. See the log for the reason.")
        where = row.path
        if isinstance(get_storage(), LocalStorage):
            where = str(LocalStorage()._file(settings.STORAGE_BUCKETS["export"], row.path))
        self.stdout.write(f"Export ready: {where} ({row.size_bytes} bytes). Link emailed (console) with a 24-hour token.")
