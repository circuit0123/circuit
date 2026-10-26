import structlog
from django.core.management import call_command, get_commands, load_command_class
from django.core.management.base import BaseCommand, CommandError

from core.jobs import JobCommand

log = structlog.get_logger("jobs")


class Command(BaseCommand):
    help = (
        "Run several jobs one after another in one container, e.g. `run_jobs expire_items send_emails`. This is what the "
        "every-5-minutes Cloud Scheduler trigger starts: one container instead of one per job (deploy/gcp/app.toml). Each job still "
        "logs its own start/end/skipped lines and takes its own lease. One failing job does not stop the others, but the exit code "
        "is then non-zero so Cloud Run retries and alerts. A job whose code does not exist yet is skipped, not an error."
    )

    def add_arguments(self, parser):
        parser.add_argument("commands", nargs="+", help="management commands to run, in this order")

    def handle(self, *args, commands, **options):
        known = get_commands()
        for name in commands:  # check everything before running anything
            if name in known and not isinstance(load_command_class(known[name], name), JobCommand):
                raise CommandError(
                    f"{name} is not a job (it does not extend core.jobs.JobCommand), so it has no lease or flag check"
                )
        failed: list[str] = []
        not_built = 0
        for name in commands:
            if name not in known:
                not_built += 1
                log.info("job.skipped", job=name, reason="not built")
                self.stdout.write(f"[{name}] skipped: not built")
                continue
            self.stdout.write(f"[{name}]")
            try:
                call_command(name, stdout=self.stdout)
            except Exception:  # the job has already logged job.failed with its error type
                failed.append(name)
        log.info("jobs.bundle", jobs=len(commands), not_built=not_built, failed=len(failed))
        if failed:
            raise CommandError(f"failed: {', '.join(failed)}")
