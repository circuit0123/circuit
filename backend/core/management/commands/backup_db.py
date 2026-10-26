from django.conf import settings

from core import backup
from core.jobs import JobCommand


class Command(JobCommand):
    help = (
        "Encrypted pg_dump of the database to the private backup bucket (or backend/.backups/ on a laptop). Nightly at 02:30 IST."
    )
    lock_minutes = 60

    def run(self) -> dict:
        if not settings.BACKUP_DATABASE_URL:  # beta week 1: Supabase's own daily backups; switch this on before real data matters
            return {"skip_reason": "not configured"}
        result = backup.backup()
        return {"megabytes": round(result.bytes / 1_000_000, 1), "tables": result.tables}

    def summary(self, result: dict) -> str:
        if result.get("skip_reason"):
            return f"skipped: {result['skip_reason']}"
        return f"backup written: {result['megabytes']} MB, {result['tables']} tables"
