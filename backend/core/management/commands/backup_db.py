from core import backup
from core.jobs import JobCommand


class Command(JobCommand):
    help = (
        "Encrypted pg_dump of the database to the private backup bucket (or backend/.backups/ on a laptop). Nightly at 02:30 IST."
    )
    lock_minutes = 60

    def run(self) -> dict:
        result = backup.backup()
        return {"megabytes": round(result.bytes / 1_000_000, 1), "tables": result.tables}

    def summary(self, result: dict) -> str:
        return f"backup written: {result['megabytes']} MB, {result['tables']} tables"
