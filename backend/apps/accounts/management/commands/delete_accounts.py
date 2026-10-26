from apps.accounts import deletion
from core.jobs import JobCommand


class Command(JobCommand):
    help = (
        "Finish the account deletions members asked for: sign-in, files, profile and personal data removed, content shown as "
        "'Deleted member'. Run every 5 minutes; safe to run again (a finished account is skipped, a failed one is retried)."
    )
    lock_minutes = 10

    def run(self) -> dict:
        return deletion.erase_requested()
